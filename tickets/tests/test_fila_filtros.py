from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket, atribuir_tecnico


class FiltroAtribuidosAMimTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_fila_filtro", is_staff=True, password="senha-teste-123",
        )
        self.outro_tecnico = get_user_model().objects.create_user(
            username="outro_tecnico_teste_fila_filtro", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste fila filtro", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste fila filtro", peso_setor=3)

        self.ticket_meu = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Meu chamado",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(self.ticket_meu, self.tecnico)

        self.ticket_do_outro = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Chamado do outro",
            solicitante_nome="Ciclana", solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        atribuir_tecnico(self.ticket_do_outro, self.outro_tecnico)

        self.ticket_sem_tecnico = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Sem tecnico",
            solicitante_nome="Beltrana", solicitante_ramal="3", solicitante_sala="Sala 3",
        )

        self.client.login(username="tecnico_teste_fila_filtro", password="senha-teste-123")

    def test_sem_filtro_mostra_todos(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        ids = {t.pk for t in resposta.context["tickets"]}
        self.assertEqual(
            ids, {self.ticket_meu.pk, self.ticket_do_outro.pk, self.ticket_sem_tecnico.pk}
        )

    def test_filtro_atribuidos_a_mim_mostra_so_os_meus(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"atribuidos_a_mim": "on"})
        ids = {t.pk for t in resposta.context["tickets"]}
        self.assertEqual(ids, {self.ticket_meu.pk})


class TecnicoInativoNaoAparecePraAtribuicaoTests(TestCase):
    def setUp(self):
        self.tecnico_ativo = get_user_model().objects.create_user(
            username="tecnico_ativo_teste", is_staff=True, is_active=True, password="senha-teste-123",
        )
        self.tecnico_inativo = get_user_model().objects.create_user(
            username="tecnico_inativo_teste", is_staff=True, is_active=False,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste tecnico inativo", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste tecnico inativo", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Chamado teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.client.login(username="tecnico_ativo_teste", password="senha-teste-123")

    def test_tecnico_inativo_nao_aparece_na_lista_de_atribuicao(self):
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        tecnicos = list(resposta.context["tecnicos"])
        self.assertIn(self.tecnico_ativo, tecnicos)
        self.assertNotIn(self.tecnico_inativo, tecnicos)

    def test_nao_e_possivel_atribuir_a_um_tecnico_inativo(self):
        resposta = self.client.post(
            reverse("tickets:atribuir_tecnico", args=[self.ticket.pk]),
            {"tecnico_id": self.tecnico_inativo.pk},
        )
        self.assertEqual(resposta.status_code, 404)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.tecnico_responsavel)
