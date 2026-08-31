from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, RespostaRapida, RespostaRapidaEdicao, Setor
from tickets.services.classificacao import abrir_ticket


class RespostasRapidasNoDetalheTicketTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_resposta_rapida", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste resposta rapida", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste resposta rapida", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.client.login(username="tecnico_teste_resposta_rapida", password="senha-teste-123")

    def test_seed_criou_os_dois_templates_de_exemplo(self):
        titulos = set(RespostaRapida.objects.values_list("titulo", flat=True))
        self.assertIn("Limpeza de cache", titulos)
        self.assertIn("Reset de senha", titulos)

    def test_detalhe_ticket_expoe_respostas_rapidas_no_contexto(self):
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        titulos = {item["titulo"] for item in resposta.context["respostas_rapidas"]}
        self.assertIn("Limpeza de cache", titulos)

    def test_campo_de_busca_de_resposta_rapida_aparece_na_pagina(self):
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "buscaRespostaRapida")
        self.assertContains(resposta, "dados-respostas-rapidas")
        self.assertContains(resposta, "Limpeza de cache")


class ListarRespostasRapidasViewTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_listar_resposta", is_staff=True, password="senha-teste-123",
        )
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_listar_resposta", password="senha-teste-123",
        )

    def test_tecnico_ve_os_modelos_semeados(self):
        self.client.login(username="tecnico_teste_listar_resposta", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:listar_respostas_rapidas"))
        self.assertContains(resposta, "Limpeza de cache")
        self.assertContains(resposta, "Reset de senha")

    def test_busca_filtra_por_titulo(self):
        self.client.login(username="tecnico_teste_listar_resposta", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:listar_respostas_rapidas"), {"busca": "cache"})
        self.assertContains(resposta, "Limpeza de cache")
        self.assertNotContains(resposta, "Reset de senha")

    def test_solicitante_nao_acessa(self):
        self.client.login(username="solicitante_teste_listar_resposta", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:listar_respostas_rapidas"))
        self.assertNotEqual(resposta.status_code, 200)


class EditarRespostaRapidaSemAdminTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_editar_resposta", is_staff=True, is_superuser=False,
            password="senha-teste-123",
        )
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_editar_resposta", password="senha-teste-123",
        )
        self.resposta = RespostaRapida.objects.create(
            titulo="Modelo teste edicao", texto="Texto original",
        )

    def test_tecnico_nao_superuser_cria_modelo_e_gera_log(self):
        self.client.login(username="tecnico_teste_editar_resposta", password="senha-teste-123")
        resposta = self.client.post(reverse("tickets:criar_resposta_rapida"), {
            "titulo": "Modelo criado pelo tecnico", "texto": "Passo a passo...",
        })
        self.assertEqual(resposta.status_code, 302)
        nova = RespostaRapida.objects.get(titulo="Modelo criado pelo tecnico")
        edicoes = RespostaRapidaEdicao.objects.filter(resposta=nova)
        self.assertEqual(edicoes.count(), 1)
        self.assertEqual(edicoes.first().autor, self.tecnico)

    def test_tecnico_nao_superuser_edita_modelo_e_gera_log(self):
        self.client.login(username="tecnico_teste_editar_resposta", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:editar_resposta_rapida", args=[self.resposta.pk]),
            {"titulo": "Modelo teste edicao", "texto": "Texto atualizado"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.resposta.refresh_from_db()
        self.assertEqual(self.resposta.texto, "Texto atualizado")
        edicoes = RespostaRapidaEdicao.objects.filter(resposta=self.resposta)
        self.assertEqual(edicoes.count(), 1)
        self.assertEqual(edicoes.first().autor, self.tecnico)

    def test_editar_duas_vezes_gera_dois_registros_de_log(self):
        self.client.login(username="tecnico_teste_editar_resposta", password="senha-teste-123")
        url = reverse("tickets:editar_resposta_rapida", args=[self.resposta.pk])
        self.client.post(url, {"titulo": "Modelo teste edicao", "texto": "Primeira edição"})
        self.client.post(url, {"titulo": "Modelo teste edicao", "texto": "Segunda edição"})
        self.assertEqual(RespostaRapidaEdicao.objects.filter(resposta=self.resposta).count(), 2)

    def test_solicitante_nao_acessa_criar(self):
        self.client.login(username="solicitante_teste_editar_resposta", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:criar_resposta_rapida"))
        self.assertNotEqual(resposta.status_code, 200)

    def test_solicitante_nao_acessa_editar(self):
        self.client.login(username="solicitante_teste_editar_resposta", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:editar_resposta_rapida", args=[self.resposta.pk]))
        self.assertNotEqual(resposta.status_code, 200)
