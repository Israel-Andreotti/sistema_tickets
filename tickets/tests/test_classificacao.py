from django.test import TestCase

from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import (
    abrir_ticket,
    confirmar_classificacao_final,
    registrar_classificacao_ia,
)


class ClassificacaoTests(TestCase):
    def setUp(self):
        self.categoria_usuario = Categoria.objects.create(
            nome="Wi-Fi teste", grupo=Categoria.Grupo.REDE,
            peso_categoria=2, sla_horas=8,
        )
        self.categoria_ia = Categoria.objects.create(
            nome="Internet teste", grupo=Categoria.Grupo.REDE,
            peso_categoria=3, sla_horas=4,
        )
        self.setor = Setor.objects.create(
            nome="Setor teste", peso_setor=5,
        )

    def test_abrir_ticket_grava_categoria_sugerida_pelo_usuario(self):
        ticket = abrir_ticket(
            categoria_sugerida=self.categoria_usuario,
            setor=self.setor,
            descricao="Não consigo acessar a internet",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        self.assertEqual(ticket.categoria_sugerida, self.categoria_usuario)
        self.assertIsNone(ticket.categoria_ia)
        self.assertIsNone(ticket.categoria_final)
        self.assertEqual(ticket.status, Ticket.Status.ABERTO)

    def test_registrar_classificacao_ia_independe_da_escolha_do_usuario(self):
        ticket = abrir_ticket(
            categoria_sugerida=self.categoria_usuario,
            setor=self.setor,
            descricao="Não consigo acessar a internet",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        registrar_classificacao_ia(ticket, self.categoria_ia)
        ticket.refresh_from_db()
        self.assertEqual(ticket.categoria_ia, self.categoria_ia)
        self.assertEqual(ticket.categoria_sugerida, self.categoria_usuario)

    def test_confirmar_classificacao_final_calcula_prioridade(self):
        ticket = abrir_ticket(
            categoria_sugerida=self.categoria_usuario,
            setor=self.setor,
            descricao="Não consigo acessar a internet",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        confirmar_classificacao_final(ticket, self.categoria_ia)
        ticket.refresh_from_db()
        self.assertEqual(ticket.categoria_final, self.categoria_ia)
        self.assertEqual(ticket.prioridade_calculada, 3 * 5)
        self.assertEqual(ticket.status, Ticket.Status.EM_ATENDIMENTO)
