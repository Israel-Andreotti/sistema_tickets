from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


class OrdenarFilaTests(TestCase):
    """`ordenar` reordena a lista já materializada (prazo é calculado em
    Python, ajustado por pausa — ver fila_tickets_view), não uma coluna do
    banco, daí testar via a página inteira em vez de só o queryset."""

    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_ordenar_fila", is_staff=True, password="senha-teste-123",
        )
        self.setor = Setor.objects.create(nome="Setor teste ordenar fila", peso_setor=3)

        self.categoria_urgente = Categoria.objects.create(
            nome="Categoria urgente teste ordenar", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=5, sla_horas=1,
        )
        self.categoria_tranquila = Categoria.objects.create(
            nome="Categoria tranquila teste ordenar", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=1, sla_horas=100,
        )

        self.ticket_urgente = abrir_ticket(
            categoria_sugerida=self.categoria_urgente, setor=self.setor, descricao="Urgente",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.ticket_tranquilo = abrir_ticket(
            categoria_sugerida=self.categoria_tranquila, setor=self.setor, descricao="Tranquilo",
            solicitante_nome="Ciclana", solicitante_ramal="2", solicitante_sala="Sala 2",
        )

        agora = timezone.now()
        Ticket.objects.filter(pk=self.ticket_urgente.pk).update(data_abertura=agora - timedelta(days=1))
        Ticket.objects.filter(pk=self.ticket_tranquilo.pk).update(data_abertura=agora)

        self.client.login(username="tecnico_teste_ordenar_fila", password="senha-teste-123")

    def test_ordenar_por_sla_coloca_mais_perto_do_estouro_primeiro(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"ordenar": "sla"})
        ids = [t.pk for t in resposta.context["tickets"]]
        self.assertEqual(ids, [self.ticket_urgente.pk, self.ticket_tranquilo.pk])

    def test_ordenar_por_mais_recente(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"ordenar": "recente"})
        ids = [t.pk for t in resposta.context["tickets"]]
        self.assertEqual(ids, [self.ticket_tranquilo.pk, self.ticket_urgente.pk])

    def test_ordenar_por_mais_antigo(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"ordenar": "antigo"})
        ids = [t.pk for t in resposta.context["tickets"]]
        self.assertEqual(ids, [self.ticket_urgente.pk, self.ticket_tranquilo.pk])

    def test_valor_invalido_cai_para_prioridade(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"ordenar": "chutando_qualquer_coisa"})
        self.assertEqual(resposta.context["ordenar_selecionado"], "prioridade")

    def test_ordenar_diferente_de_prioridade_conta_como_filtro_ativo(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"ordenar": "sla"})
        self.assertTrue(resposta.context["algum_filtro"])


class VisualizacaoKanbanTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_kanban", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste kanban", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste kanban", peso_setor=3)

        self.ticket_aberto = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Aberto",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.ticket_em_atendimento = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Em atendimento",
            solicitante_nome="Ciclana", solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        atribuir_tecnico(self.ticket_em_atendimento, self.tecnico)

        self.client.login(username="tecnico_teste_kanban", password="senha-teste-123")

    def test_agrupa_tickets_por_status(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        por_status = resposta.context["tickets_por_status"]
        self.assertEqual([t.pk for t in por_status["aberto"]], [self.ticket_aberto.pk])
        self.assertEqual([t.pk for t in por_status["em_atendimento"]], [self.ticket_em_atendimento.pk])
        self.assertEqual(por_status["pausado"], [])

    def test_lista_e_kanban_renderizam_juntos_alternancia_e_so_visual(self):
        """Lista e kanban ficam sempre os dois no HTML — a troca é só CSS/JS
        no navegador (localStorage), pra restaurar a preferência sem viagem
        ao servidor, igual ao tema claro/escuro (ver tema-inicial.js)."""
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        self.assertContains(resposta, 'id="filaLista"')
        self.assertContains(resposta, 'id="filaKanban"')
        self.assertContains(
            resposta, reverse("tickets:detalhe_ticket", args=[self.ticket_aberto.pk])
        )
