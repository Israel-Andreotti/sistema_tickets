from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket, atribuir_tecnico, confirmar_classificacao_final
from tickets.services.equipamento import obter_setor_ti


class PermissaoGerenciarChamadoTests(TestCase):
    """Classificar e fechar são ações de dono do chamado: só o técnico
    responsável (ou o gestor da TI / superusuário, que são administradores)
    pode. Ver _pode_gerenciar_chamado em views.py."""

    def setUp(self):
        self.tecnico_a = get_user_model().objects.create_user(
            username="tecnico_a_permissao", is_staff=True, password="senha-teste-123",
        )
        self.tecnico_b = get_user_model().objects.create_user(
            username="tecnico_b_permissao", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste permissao gerenciar", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste permissao gerenciar", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(self.ticket, self.tecnico_a)

    def test_tecnico_nao_responsavel_nao_consegue_classificar(self):
        self.client.login(username="tecnico_b_permissao", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:classificar_ticket", args=[self.ticket.pk]),
            {"categoria_final": self.categoria.pk},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.categoria_final)

    def test_tecnico_responsavel_consegue_classificar(self):
        self.client.login(username="tecnico_a_permissao", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:classificar_ticket", args=[self.ticket.pk]),
            {"categoria_final": self.categoria.pk},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.categoria_final, self.categoria)

    def test_gestor_da_ti_consegue_classificar_mesmo_sem_ser_responsavel(self):
        gestor = get_user_model().objects.create_user(
            username="gestor_permissao_classificar", password="senha-teste-123",
        )
        setor_ti = obter_setor_ti()
        setor_ti.gestor = gestor
        setor_ti.save(update_fields=["gestor"])
        self.client.login(username="gestor_permissao_classificar", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:classificar_ticket", args=[self.ticket.pk]),
            {"categoria_final": self.categoria.pk},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.categoria_final, self.categoria)

    def test_tecnico_nao_responsavel_nao_consegue_fechar(self):
        confirmar_classificacao_final(self.ticket, self.categoria)
        self.client.login(username="tecnico_b_permissao", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:fechar_ticket", args=[self.ticket.pk]),
            {"confirmar_sem_movimentacao": "on"},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.EM_ATENDIMENTO)
        self.assertFalse(self.ticket.movimentacao_confirmada)

    def test_tecnico_responsavel_consegue_fechar(self):
        confirmar_classificacao_final(self.ticket, self.categoria)
        self.client.login(username="tecnico_a_permissao", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:fechar_ticket", args=[self.ticket.pk]),
            {"confirmar_sem_movimentacao": "on"},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.FECHADO)

    def test_gestor_da_ti_consegue_fechar_mesmo_sem_ser_responsavel(self):
        confirmar_classificacao_final(self.ticket, self.categoria)
        gestor = get_user_model().objects.create_user(
            username="gestor_permissao_fechar", password="senha-teste-123",
        )
        setor_ti = obter_setor_ti()
        setor_ti.gestor = gestor
        setor_ti.save(update_fields=["gestor"])
        self.client.login(username="gestor_permissao_fechar", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:fechar_ticket", args=[self.ticket.pk]),
            {"confirmar_sem_movimentacao": "on"},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.FECHADO)

    def test_tecnico_nao_responsavel_ve_botoes_desabilitados(self):
        confirmar_classificacao_final(self.ticket, self.categoria)
        self.client.login(username="tecnico_b_permissao", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Só o técnico responsável pode fechar o chamado.")
        self.assertContains(resposta, 'id="botaoFecharChamado"')
        # o botão de fechar deve estar desabilitado nesse estado
        self.assertRegex(
            resposta.content.decode(),
            r'id="botaoFecharChamado"[^>]*disabled',
        )

    def test_tecnico_responsavel_nao_ve_aviso_de_restricao(self):
        self.client.login(username="tecnico_a_permissao", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertNotContains(resposta, "Só o técnico responsável pode confirmar a classificação.")
        self.assertNotContains(resposta, "Só o técnico responsável pode fechar o chamado.")
