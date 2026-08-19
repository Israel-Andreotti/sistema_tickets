from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from tickets.models import Categoria, Setor, Ticket
from tickets.services.sla import fechar_ticket


class FecharTicketTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_sla", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Impressora teste", grupo=Categoria.Grupo.IMPRESSORA,
            peso_categoria=3, sla_horas=8,
        )
        self.setor = Setor.objects.create(
            nome="Setor teste", peso_setor=3,
        )
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            categoria_final=self.categoria,
            tecnico_responsavel=self.tecnico,
            movimentacao_confirmada=True,
            setor=self.setor,
            descricao="Impressora não liga",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )

    def test_fechar_sem_categoria_final_levanta_erro(self):
        ticket_sem_final = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            tecnico_responsavel=self.tecnico,
            movimentacao_confirmada=True,
            setor=self.setor,
            descricao="sem categoria final",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        with self.assertRaises(ValueError):
            fechar_ticket(ticket_sem_final)

    def test_fechar_sem_tecnico_responsavel_levanta_erro(self):
        ticket_sem_tecnico = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            categoria_final=self.categoria,
            movimentacao_confirmada=True,
            setor=self.setor,
            descricao="sem tecnico responsavel",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        with self.assertRaises(ValueError):
            fechar_ticket(ticket_sem_tecnico)

    def test_fechar_sem_movimentacao_confirmada_levanta_erro(self):
        ticket_sem_movimentacao = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            categoria_final=self.categoria,
            tecnico_responsavel=self.tecnico,
            setor=self.setor,
            descricao="sem movimentacao confirmada",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        with self.assertRaises(ValueError):
            fechar_ticket(ticket_sem_movimentacao)

    def test_fechar_ticket_calcula_tempo_real_e_desvio(self):
        self.ticket.refresh_from_db()
        data_fechamento = self.ticket.data_abertura + timedelta(hours=12)

        historico = fechar_ticket(self.ticket, data_fechamento=data_fechamento)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.FECHADO)
        self.assertEqual(historico.tempo_esperado, Decimal("8.00"))
        self.assertEqual(historico.tempo_real, Decimal("12.00"))
        self.assertEqual(historico.desvio, Decimal("4.00"))

    def test_fechar_ticket_dentro_do_sla_gera_desvio_negativo(self):
        self.ticket.refresh_from_db()
        data_fechamento = self.ticket.data_abertura + timedelta(hours=2)

        historico = fechar_ticket(self.ticket, data_fechamento=data_fechamento)

        self.assertEqual(historico.tempo_real, Decimal("2.00"))
        self.assertEqual(historico.desvio, Decimal("-6.00"))
