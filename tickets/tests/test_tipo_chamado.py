from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket
from tickets.services.sla import fechar_ticket


class FiltroTipoNaFilaTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_tipo", is_staff=True, password="senha-teste-123",
        )
        self.categoria_incidente = Categoria.objects.create(
            nome="Impressora não liga", grupo=Categoria.Grupo.IMPRESSORA,
            tipo=Categoria.Tipo.INCIDENTE, peso_categoria=3, sla_horas=4,
        )
        self.categoria_requisicao = Categoria.objects.create(
            nome="Instalar impressora", grupo=Categoria.Grupo.IMPRESSORA,
            tipo=Categoria.Tipo.REQUISICAO, peso_categoria=2, sla_horas=48,
        )
        self.setor = Setor.objects.create(nome="Setor teste tipo", peso_setor=3)
        self.ticket_incidente = abrir_ticket(
            categoria_sugerida=self.categoria_incidente, setor=self.setor,
            descricao="Impressora não liga", solicitante_nome="Fulano",
            solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.ticket_requisicao = abrir_ticket(
            categoria_sugerida=self.categoria_requisicao, setor=self.setor,
            descricao="Preciso de uma impressora nova", solicitante_nome="Ciclana",
            solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        self.client.login(username="tecnico_teste_tipo", password="senha-teste-123")

    def test_sem_filtro_mostra_os_dois(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        ids = {t.pk for t in resposta.context["tickets"]}
        self.assertEqual(ids, {self.ticket_incidente.pk, self.ticket_requisicao.pk})

    def test_filtro_incidente_mostra_so_o_incidente(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"tipo": "incidente"})
        ids = {t.pk for t in resposta.context["tickets"]}
        self.assertEqual(ids, {self.ticket_incidente.pk})

    def test_filtro_requisicao_mostra_so_a_requisicao(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"tipo": "requisicao"})
        ids = {t.pk for t in resposta.context["tickets"]}
        self.assertEqual(ids, {self.ticket_requisicao.pk})


class FiltroTipoNoHistoricoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_tipo_hist", is_staff=True, password="senha-teste-123",
        )
        self.categoria_incidente = Categoria.objects.create(
            nome="Rede fora do ar", grupo=Categoria.Grupo.REDE,
            tipo=Categoria.Tipo.INCIDENTE, peso_categoria=4, sla_horas=2,
        )
        self.categoria_requisicao = Categoria.objects.create(
            nome="Criar acesso", grupo=Categoria.Grupo.ACESSO,
            tipo=Categoria.Tipo.REQUISICAO, peso_categoria=1, sla_horas=24,
        )
        self.setor = Setor.objects.create(nome="Setor teste tipo hist", peso_setor=2)

        self.ticket_incidente = Ticket.objects.create(
            categoria_sugerida=self.categoria_incidente, categoria_final=self.categoria_incidente,
            codigo_tipo=Categoria.Tipo.INCIDENTE, codigo_numero=1,
            tecnico_responsavel=self.tecnico, movimentacao_confirmada=True,
            setor=self.setor, descricao="Rede caiu", solicitante_nome="Fulano",
            solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        fechar_ticket(self.ticket_incidente)

        self.ticket_requisicao = Ticket.objects.create(
            categoria_sugerida=self.categoria_requisicao, categoria_final=self.categoria_requisicao,
            codigo_tipo=Categoria.Tipo.REQUISICAO, codigo_numero=1,
            tecnico_responsavel=self.tecnico, movimentacao_confirmada=True,
            setor=self.setor, descricao="Novo acesso", solicitante_nome="Ciclana",
            solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        fechar_ticket(self.ticket_requisicao)

        self.client.login(username="tecnico_teste_tipo_hist", password="senha-teste-123")

    def test_filtro_incidente_mostra_so_o_incidente(self):
        resposta = self.client.get(reverse("tickets:historico_tickets"), {"tipo": "incidente"})
        ids = {t.pk for t in resposta.context["pagina"]}
        self.assertEqual(ids, {self.ticket_incidente.pk})

    def test_filtro_requisicao_mostra_so_a_requisicao(self):
        resposta = self.client.get(reverse("tickets:historico_tickets"), {"tipo": "requisicao"})
        ids = {t.pk for t in resposta.context["pagina"]}
        self.assertEqual(ids, {self.ticket_requisicao.pk})

    def test_mostrar_todos_mostra_os_dois(self):
        resposta = self.client.get(reverse("tickets:historico_tickets"), {"todos": "1"})
        ids = {t.pk for t in resposta.context["pagina"]}
        self.assertEqual(ids, {self.ticket_incidente.pk, self.ticket_requisicao.pk})
