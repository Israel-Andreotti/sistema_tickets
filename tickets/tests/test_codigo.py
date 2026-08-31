from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor
from tickets.services.classificacao import abrir_ticket
from tickets.services.codigo import proximo_numero_sequencial


class ProximoNumeroSequencialTests(TestCase):
    def test_incrementa_por_tipo_independentemente(self):
        self.assertEqual(proximo_numero_sequencial(Categoria.Tipo.INCIDENTE), 1)
        self.assertEqual(proximo_numero_sequencial(Categoria.Tipo.INCIDENTE), 2)
        self.assertEqual(proximo_numero_sequencial(Categoria.Tipo.REQUISICAO), 1)
        self.assertEqual(proximo_numero_sequencial(Categoria.Tipo.INCIDENTE), 3)
        self.assertEqual(proximo_numero_sequencial(Categoria.Tipo.REQUISICAO), 2)


class TicketCodigoTests(TestCase):
    def setUp(self):
        self.categoria_incidente = Categoria.objects.create(
            nome="Categoria incidente teste codigo", grupo=Categoria.Grupo.SUPORTE,
            tipo=Categoria.Tipo.INCIDENTE, peso_categoria=2, sla_horas=8,
        )
        self.categoria_requisicao = Categoria.objects.create(
            nome="Categoria requisicao teste codigo", grupo=Categoria.Grupo.SUPORTE,
            tipo=Categoria.Tipo.REQUISICAO, peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste codigo", peso_setor=3)

    def _abrir(self, categoria):
        return abrir_ticket(
            categoria_sugerida=categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )

    def test_primeiro_incidente_e_primeira_requisicao_comecam_em_1(self):
        ticket_incidente = self._abrir(self.categoria_incidente)
        ticket_requisicao = self._abrir(self.categoria_requisicao)
        self.assertEqual(ticket_incidente.codigo, "INC1")
        self.assertEqual(ticket_requisicao.codigo, "REQ1")

    def test_sequencias_sao_independentes_por_tipo(self):
        self._abrir(self.categoria_incidente)
        self._abrir(self.categoria_incidente)
        ticket_requisicao = self._abrir(self.categoria_requisicao)
        ticket_incidente = self._abrir(self.categoria_incidente)

        self.assertEqual(ticket_requisicao.codigo, "REQ1")
        self.assertEqual(ticket_incidente.codigo, "INC3")


class BuscaPorCodigoEmMeusTicketsTests(TestCase):
    def setUp(self):
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_busca_codigo", password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste busca codigo", grupo=Categoria.Grupo.SUPORTE,
            tipo=Categoria.Tipo.INCIDENTE, peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste busca codigo", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
            solicitante=self.solicitante,
        )
        self.client.login(username="solicitante_teste_busca_codigo", password="senha-teste-123")

    def test_busca_pelo_codigo_correto_redireciona_pro_chamado(self):
        resposta = self.client.get(reverse("tickets:meus_tickets"), {"numero": self.ticket.codigo})
        self.assertRedirects(resposta, reverse("tickets:meu_ticket_detalhe", args=[self.ticket.pk]))

    def test_busca_case_insensitive(self):
        resposta = self.client.get(reverse("tickets:meus_tickets"), {"numero": self.ticket.codigo.lower()})
        self.assertRedirects(resposta, reverse("tickets:meu_ticket_detalhe", args=[self.ticket.pk]))

    def test_busca_com_prefixo_errado_nao_encontra(self):
        # o chamado é INC1, buscar REQ1 não deve encontrar
        resposta = self.client.get(reverse("tickets:meus_tickets"), {"numero": "REQ1"})
        self.assertContains(resposta, "Nenhum chamado seu encontrado com o código REQ1")

    def test_formato_invalido_da_erro_amigavel(self):
        resposta = self.client.get(reverse("tickets:meus_tickets"), {"numero": "42"})
        self.assertContains(resposta, "Digite o código do chamado no formato INC42 ou REQ7.")
