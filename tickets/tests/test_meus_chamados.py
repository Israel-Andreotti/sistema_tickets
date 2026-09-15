"""A tela "Meus chamados" mostra os chamados em andamento de quem está
logado sem precisar de busca — antes exigia digitar o código ou um intervalo
de datas. A regra de visibilidade não mudou: cada um vê só os seus.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket, confirmar_classificacao_final
from tickets.services.sla import fechar_ticket


class MeusChamadosAtivosTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_meus", password="senha-teste-123",
        )
        self.outro = get_user_model().objects.create_user(
            username="outro_solicitante_meus", password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste meus chamados", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste meus chamados", peso_setor=3)

    def _abrir(self, solicitante, descricao):
        return abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao=descricao,
            solicitante=solicitante, solicitante_nome=solicitante.username,
            solicitante_ramal="1", solicitante_sala="",
        )

    def test_lista_chamados_ativos_sem_precisar_buscar(self):
        ticket = self._abrir(self.usuario, "Meu chamado em andamento")
        self.client.login(username="solicitante_meus", password="senha-teste-123")

        resposta = self.client.get(reverse("tickets:meus_tickets"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([t.pk for t in resposta.context["ativos"]], [ticket.pk])
        self.assertContains(resposta, ticket.codigo)

    def test_nao_mostra_chamado_de_outro_usuario(self):
        self._abrir(self.outro, "Chamado do outro")
        self.client.login(username="solicitante_meus", password="senha-teste-123")

        resposta = self.client.get(reverse("tickets:meus_tickets"))

        self.assertEqual(list(resposta.context["ativos"]), [])

    def test_chamado_fechado_sai_da_lista_de_ativos(self):
        ticket = self._abrir(self.usuario, "Chamado que sera fechado")
        tecnico = get_user_model().objects.create_user(
            username="tecnico_meus_chamados", is_staff=True,
        )
        ticket.tecnico_responsavel = tecnico
        ticket.movimentacao_confirmada = True
        ticket.save(update_fields=["tecnico_responsavel", "movimentacao_confirmada"])
        confirmar_classificacao_final(ticket, self.categoria)
        fechar_ticket(ticket)

        self.client.login(username="solicitante_meus", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:meus_tickets"))

        self.assertEqual(list(resposta.context["ativos"]), [])

    def test_sem_chamado_nenhum_mostra_estado_vazio(self):
        self.client.login(username="solicitante_meus", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:meus_tickets"))
        self.assertContains(resposta, "Você não tem chamados em andamento")

    def test_busca_por_data_substitui_a_lista_de_ativos(self):
        """Buscando por data, a tela mostra o resultado da busca (que pode
        incluir fechados) no lugar da lista de ativos, pra não ficar com duas
        listas concorrendo na mesma tela."""
        ticket = self._abrir(self.usuario, "Chamado buscavel")
        self.client.login(username="solicitante_meus", password="senha-teste-123")

        # Data no fuso local, que é o que o filtro __date__gte do Django usa —
        # em UTC isso pode cair no dia seguinte e a busca não achar nada.
        data = timezone.localtime(ticket.data_abertura).date().isoformat()
        resposta = self.client.get(reverse("tickets:meus_tickets"), {"data_de": data})

        self.assertIsNone(resposta.context["ativos"])
        self.assertEqual([t.pk for t in resposta.context["resultados"]], [ticket.pk])
