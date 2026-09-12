"""Testes da integração com o classificador de IA (RN02).

O modelo real não é exercitado aqui — o que se testa é a ponte: o contrato
HTTP, o limiar de confiança vindo do banco, e a garantia de que nenhuma falha
do classificador atrapalha a abertura do chamado.
"""
import io
import json
import urllib.error
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from tickets.models import Categoria, ParametroSistema, Setor, Ticket
from tickets.services.classificacao import abrir_ticket
from tickets.services.ia import (
    ClassificadorIndisponivel,
    classificador_configurado,
    classificar_ticket,
    classificar_ticket_em_segundo_plano,
    consultar_classificador,
)

URL_FALSA = "http://ia.teste/classificar"


def resposta_http(corpo: dict):
    """Imita o objeto de contexto que urlopen devolve."""
    class RespostaFalsa(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return RespostaFalsa(json.dumps(corpo).encode("utf-8"))


@override_settings(IA_CLASSIFICADOR_URL=URL_FALSA)
class ClassificarTicketTests(TestCase):
    def setUp(self):
        self.categoria_usuario = Categoria.objects.create(
            nome="Wi-Fi teste", grupo=Categoria.Grupo.REDE, peso_categoria=2, sla_horas=8,
        )
        self.categoria_ia = Categoria.objects.create(
            nome="Impressora teste", grupo=Categoria.Grupo.IMPRESSORA,
            peso_categoria=3, sla_horas=4,
        )
        self.setor = Setor.objects.create(nome="Setor teste", peso_setor=5)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria_usuario,
            setor=self.setor,
            descricao="A impressora não puxa papel",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        ParametroSistema.objects.update_or_create(
            chave="ia_confianca_minima", defaults={"valor": "0.30"}
        )

    def _com_resposta(self, corpo):
        return patch(
            "tickets.services.ia.urllib.request.urlopen", return_value=resposta_http(corpo)
        )

    def test_grava_categoria_e_confianca_quando_acima_do_limiar(self):
        with self._com_resposta({"categoria_id": self.categoria_ia.pk, "confianca": 0.87}):
            categoria = classificar_ticket(self.ticket)

        self.assertEqual(categoria, self.categoria_ia)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.categoria_ia, self.categoria_ia)
        self.assertEqual(self.ticket.confianca_ia, Decimal("0.8700"))

    def test_nao_grava_palpite_abaixo_do_limiar(self):
        with self._com_resposta({"categoria_id": self.categoria_ia.pk, "confianca": 0.10}):
            categoria = classificar_ticket(self.ticket)

        self.assertIsNone(categoria)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.categoria_ia)

    def test_limiar_vem_do_banco_e_nao_do_codigo(self):
        """O requisito central do projeto: mexer no limiar é configuração,
        não alteração de código."""
        ParametroSistema.objects.update_or_create(
            chave="ia_confianca_minima", defaults={"valor": "0.95"}
        )
        with self._com_resposta({"categoria_id": self.categoria_ia.pk, "confianca": 0.87}):
            self.assertIsNone(classificar_ticket(self.ticket))

        ParametroSistema.objects.update_or_create(
            chave="ia_confianca_minima", defaults={"valor": "0.50"}
        )
        with self._com_resposta({"categoria_id": self.categoria_ia.pk, "confianca": 0.87}):
            self.assertEqual(classificar_ticket(self.ticket), self.categoria_ia)

    def test_ignora_categoria_que_nao_existe_no_catalogo(self):
        with self._com_resposta({"categoria_id": 999999, "confianca": 0.99}):
            self.assertIsNone(classificar_ticket(self.ticket))
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.categoria_ia)

    def test_ignora_resposta_sem_categoria(self):
        with self._com_resposta({"confianca": 0.9}):
            self.assertIsNone(classificar_ticket(self.ticket))

    def test_ignora_confianca_ilegivel(self):
        with self._com_resposta({"categoria_id": self.categoria_ia.pk, "confianca": "muito alta"}):
            self.assertIsNone(classificar_ticket(self.ticket))

    def test_servico_fora_do_ar_levanta_indisponivel(self):
        with patch(
            "tickets.services.ia.urllib.request.urlopen",
            side_effect=urllib.error.URLError("conexão recusada"),
        ):
            with self.assertRaises(ClassificadorIndisponivel):
                classificar_ticket(self.ticket)

    def test_resposta_ilegivel_levanta_indisponivel(self):
        class Lixo(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("tickets.services.ia.urllib.request.urlopen", return_value=Lixo(b"<html>502")):
            with self.assertRaises(ClassificadorIndisponivel):
                consultar_classificador("qualquer coisa", [{"id": 1, "nome": "X"}])

    def test_envia_o_catalogo_como_candidatas(self):
        """O serviço não tem catálogo próprio: quem manda as categorias é o
        Django, para que uma categoria criada no Admin já seja classificável."""
        with patch(
            "tickets.services.ia.urllib.request.urlopen",
            return_value=resposta_http({"categoria_id": self.categoria_ia.pk, "confianca": 0.9}),
        ) as urlopen:
            classificar_ticket(self.ticket)

        enviado = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(enviado["descricao"], "A impressora não puxa papel")
        ids_enviados = {c["id"] for c in enviado["categorias"]}
        self.assertIn(self.categoria_ia.pk, ids_enviados)
        self.assertIn(self.categoria_usuario.pk, ids_enviados)
        # O grupo acompanha o nome, porque o nome sozinho é ambíguo pro modelo.
        self.assertTrue(all("grupo" in c for c in enviado["categorias"]))


class ClassificadorDesligadoTests(TestCase):
    """Sem IA_CLASSIFICADOR_URL, o sistema tem que rodar normalmente — a
    classificação é um extra, não um pré-requisito."""

    @override_settings(IA_CLASSIFICADOR_URL="")
    def test_nao_configurado(self):
        self.assertFalse(classificador_configurado())
        with self.assertRaises(ClassificadorIndisponivel):
            consultar_classificador("teste", [{"id": 1, "nome": "X"}])

    @override_settings(IA_CLASSIFICADOR_URL="")
    def test_segundo_plano_nao_dispara_thread_sem_configuracao(self):
        setor = Setor.objects.create(nome="Setor teste", peso_setor=3)
        categoria = Categoria.objects.create(
            nome="Categoria teste", grupo=Categoria.Grupo.SUPORTE, peso_categoria=2, sla_horas=8,
        )
        ticket = abrir_ticket(
            categoria_sugerida=categoria, setor=setor, descricao="teste",
            solicitante_nome="X", solicitante_ramal="1", solicitante_sala="Y",
        )
        with patch("tickets.services.ia.threading.Thread") as thread:
            classificar_ticket_em_segundo_plano(ticket)
        thread.assert_not_called()


class AberturaDeChamadoComIATests(TestCase):
    """A abertura do chamado não pode depender da IA."""

    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste", peso_setor=3)
        self.categoria = Categoria.objects.create(
            nome="Categoria teste", grupo=Categoria.Grupo.SUPORTE, peso_categoria=2, sla_horas=8,
        )
        self.usuario = get_user_model().objects.create_user(
            username="solicitante", password="senha-de-teste-123"
        )
        self.client.force_login(self.usuario)

    def _abrir(self):
        return self.client.post(
            reverse("tickets:abrir_ticket"),
            {
                "solicitante_nome": "Maria Teste",
                "solicitante_ramal": "1234",
                "solicitante_sala": "Sala 10",
                "setor": self.setor.pk,
                "grupo": self.categoria.grupo,
                "categoria_sugerida": self.categoria.pk,
                "impacto": Ticket.Impacto.APENAS_EU,
                "descricao": "O computador não liga de jeito nenhum",
            },
        )

    @override_settings(IA_CLASSIFICADOR_URL=URL_FALSA)
    def test_chamado_abre_mesmo_com_o_classificador_fora_do_ar(self):
        with patch(
            "tickets.services.ia.urllib.request.urlopen",
            side_effect=urllib.error.URLError("conexão recusada"),
        ):
            resposta = self._abrir()

        self.assertEqual(resposta.status_code, 302)
        ticket = Ticket.objects.get()
        self.assertIsNone(ticket.categoria_ia)

    @override_settings(IA_CLASSIFICADOR_URL="")
    def test_chamado_abre_com_a_integracao_desligada(self):
        resposta = self._abrir()
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Ticket.objects.count(), 1)


@override_settings(IA_CLASSIFICADOR_URL=URL_FALSA)
class ComandoClassificarPendentesTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste", peso_setor=3)
        self.categoria = Categoria.objects.create(
            nome="Categoria teste", grupo=Categoria.Grupo.SUPORTE, peso_categoria=2, sla_horas=8,
        )
        ParametroSistema.objects.update_or_create(
            chave="ia_confianca_minima", defaults={"valor": "0.30"}
        )

    def _abrir(self, descricao="teste"):
        return abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao=descricao,
            solicitante_nome="X", solicitante_ramal="1", solicitante_sala="Y",
        )

    def test_classifica_os_pendentes(self):
        ticket = self._abrir()
        with patch(
            "tickets.services.ia.urllib.request.urlopen",
            return_value=resposta_http({"categoria_id": self.categoria.pk, "confianca": 0.8}),
        ):
            call_command("classificar_pendentes", verbosity=0)

        ticket.refresh_from_db()
        self.assertEqual(ticket.categoria_ia, self.categoria)

    def test_nao_reclassifica_quem_ja_tem_palpite(self):
        ticket = self._abrir()
        ticket.categoria_ia = self.categoria
        ticket.save(update_fields=["categoria_ia"])

        with patch("tickets.services.ia.urllib.request.urlopen") as urlopen:
            call_command("classificar_pendentes", verbosity=0)
        urlopen.assert_not_called()

    def test_ignora_fechados_por_padrao(self):
        ticket = self._abrir()
        ticket.status = Ticket.Status.FECHADO
        ticket.save(update_fields=["status"])

        with patch("tickets.services.ia.urllib.request.urlopen") as urlopen:
            call_command("classificar_pendentes", verbosity=0)
        urlopen.assert_not_called()

    def test_aborta_quando_o_servico_esta_fora_do_ar(self):
        self._abrir()
        with patch(
            "tickets.services.ia.urllib.request.urlopen",
            side_effect=urllib.error.URLError("conexão recusada"),
        ):
            with self.assertRaises(CommandError):
                call_command("classificar_pendentes", verbosity=0)

    @override_settings(IA_CLASSIFICADOR_URL="")
    def test_avisa_quando_a_integracao_nao_esta_configurada(self):
        with self.assertRaises(CommandError):
            call_command("classificar_pendentes", verbosity=0)
