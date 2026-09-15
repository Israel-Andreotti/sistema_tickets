"""Antes só o técnico via prazo/SLA na fila — o solicitante não tinha como
saber se o próprio chamado "está demorando" ou não. Agora a tela de detalhe
do chamado (visão do solicitante) mostra uma previsão de atendimento."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket, confirmar_classificacao_final
from tickets.services.sla import fechar_ticket


class PrazoVisivelAoSolicitanteTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_teste_prazo", password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste prazo solicitante", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste prazo solicitante", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Chamado teste prazo",
            solicitante=self.usuario, solicitante_nome="Fulano",
            solicitante_ramal="1", solicitante_sala="",
        )
        self.client.login(username="solicitante_teste_prazo", password="senha-teste-123")

    def test_chamado_ativo_mostra_previsao_de_atendimento(self):
        resposta = self.client.get(reverse("tickets:meu_ticket_detalhe", args=[self.ticket.pk]))
        self.assertIsNotNone(resposta.context["prazo_sla"])
        self.assertContains(resposta, "Previsão de atendimento")

    def test_chamado_fechado_nao_mostra_previsao(self):
        tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_prazo_solicitante", is_staff=True,
        )
        self.ticket.tecnico_responsavel = tecnico
        self.ticket.movimentacao_confirmada = True
        self.ticket.save(update_fields=["tecnico_responsavel", "movimentacao_confirmada"])
        confirmar_classificacao_final(self.ticket, self.categoria)
        fechar_ticket(self.ticket)

        resposta = self.client.get(reverse("tickets:meu_ticket_detalhe", args=[self.ticket.pk]))
        self.assertIsNone(resposta.context["prazo_sla"])
        self.assertNotContains(resposta, "Previsão de atendimento")
