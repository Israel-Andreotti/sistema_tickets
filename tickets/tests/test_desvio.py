from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tickets.models import Categoria, Setor, Ticket
from tickets.services.desvio import (
    agregar_desvios_por_categoria_setor,
    classificar_desvio,
)
from tickets.services.sla import fechar_ticket


class ClassificarDesvioTests(TestCase):
    """Usa os limiares padrão semeados em 0003_seed_parametros_e_regras
    (desvio_atencao_pct=20, desvio_critico_pct=50)."""

    def test_dentro_do_sla_nao_gera_desvio(self):
        self.assertIsNone(classificar_desvio(10))

    def test_percentual_no_limiar_de_atencao(self):
        self.assertEqual(classificar_desvio(20), "atencao")

    def test_percentual_intermediario_e_atencao(self):
        self.assertEqual(classificar_desvio(35), "atencao")

    def test_percentual_no_limiar_critico(self):
        self.assertEqual(classificar_desvio(50), "critico")

    def test_percentual_acima_do_critico(self):
        self.assertEqual(classificar_desvio(80), "critico")


class AgregarDesviosTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_desvio", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Sistema de laboratório/exames teste", grupo=Categoria.Grupo.CLINICO,
            peso_categoria=5, sla_horas=10,
        )
        self.setor = Setor.objects.create(
            nome="Setor teste", peso_setor=5,
        )

    def _fechar_ticket_com_horas(self, horas_reais, dias_atras=0):
        ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            categoria_final=self.categoria,
            tecnico_responsavel=self.tecnico,
            movimentacao_confirmada=True,
            setor=self.setor,
            descricao="ticket de teste",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        ticket.refresh_from_db()
        data_fechamento = ticket.data_abertura + timedelta(hours=horas_reais)
        if dias_atras:
            data_fechamento = timezone.now() - timedelta(days=dias_atras)
        return fechar_ticket(ticket, data_fechamento=data_fechamento)

    def test_agrega_percentual_medio_por_categoria_e_setor(self):
        self._fechar_ticket_com_horas(13)  # desvio 3h => 30%
        self._fechar_ticket_com_horas(11)  # desvio 1h => 10%

        resultado = agregar_desvios_por_categoria_setor(janela_dias=30)

        self.assertEqual(len(resultado), 1)
        linha = resultado[0]
        self.assertEqual(linha["categoria_id"], self.categoria.id)
        self.assertEqual(linha["setor_id"], self.setor.id)
        self.assertEqual(linha["quantidade_tickets"], 2)
        self.assertAlmostEqual(linha["percentual_medio"], 20.0, places=2)
        self.assertEqual(linha["tipo_desvio"], "atencao")

    def test_ticket_fora_da_janela_nao_entra_na_agregacao(self):
        self._fechar_ticket_com_horas(13)
        self._fechar_ticket_com_horas(30, dias_atras=60)  # fora da janela de 30 dias

        resultado = agregar_desvios_por_categoria_setor(janela_dias=30)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["quantidade_tickets"], 1)
