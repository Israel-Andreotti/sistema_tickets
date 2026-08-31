from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, MovimentacaoEquipamento, Setor, Ticket
from tickets.services.classificacao import abrir_ticket
from tickets.services.equipamento import remover_movimentacao_pendente


class RemoverMovimentacaoPendenteTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_equip", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste equip", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste equip", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )

    def test_remove_a_unica_pendente_e_desmarca_confirmada(self):
        mov = MovimentacaoEquipamento.objects.create(
            ticket=self.ticket, autor=self.tecnico, aplicada=False,
        )
        self.ticket.movimentacao_confirmada = True
        self.ticket.save(update_fields=["movimentacao_confirmada"])

        remover_movimentacao_pendente(mov)

        self.assertFalse(MovimentacaoEquipamento.objects.filter(pk=mov.pk).exists())
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.movimentacao_confirmada)

    def test_remove_uma_de_duas_mantem_confirmada(self):
        mov1 = MovimentacaoEquipamento.objects.create(
            ticket=self.ticket, autor=self.tecnico, aplicada=False,
        )
        MovimentacaoEquipamento.objects.create(
            ticket=self.ticket, autor=self.tecnico, aplicada=False,
        )
        self.ticket.movimentacao_confirmada = True
        self.ticket.save(update_fields=["movimentacao_confirmada"])

        remover_movimentacao_pendente(mov1)

        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.movimentacao_confirmada)

    def test_nao_remove_movimentacao_ja_aplicada(self):
        mov = MovimentacaoEquipamento.objects.create(
            ticket=self.ticket, autor=self.tecnico, aplicada=True,
        )
        with self.assertRaises(ValueError):
            remover_movimentacao_pendente(mov)
        self.assertTrue(MovimentacaoEquipamento.objects.filter(pk=mov.pk).exists())


class RemoverMovimentacaoViewTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_equip_view", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste equip view", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste equip view", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.client.login(username="tecnico_teste_equip_view", password="senha-teste-123")

    def test_post_remove_movimentacao_pendente(self):
        mov = MovimentacaoEquipamento.objects.create(
            ticket=self.ticket, autor=self.tecnico, aplicada=False,
        )
        resposta = self.client.post(
            reverse("tickets:remover_movimentacao", args=[self.ticket.pk, mov.pk])
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertFalse(MovimentacaoEquipamento.objects.filter(pk=mov.pk).exists())

    def test_post_com_ticket_errado_da_404(self):
        outro_ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Outro chamado",
            solicitante_nome="Ciclana", solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        mov = MovimentacaoEquipamento.objects.create(
            ticket=self.ticket, autor=self.tecnico, aplicada=False,
        )
        resposta = self.client.post(
            reverse("tickets:remover_movimentacao", args=[outro_ticket.pk, mov.pk])
        )
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(MovimentacaoEquipamento.objects.filter(pk=mov.pk).exists())
