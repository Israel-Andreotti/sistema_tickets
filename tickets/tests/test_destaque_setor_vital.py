"""Destaque de criticidade clínica na fila: chamados de setor com peso alto
(CTI, UTI etc.) ganham um selo visual, tanto no kanban quanto na lista —
mesmo critério (peso_setor >= peso_setor_vital) já usado no indicador
"setores vitais" do dashboard. O limiar vem de ParametroSistema, não fixo
no código (era PESO_SETOR_VITAL = 4 antes da migração 0058)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, ParametroSistema, Setor
from tickets.services.classificacao import abrir_ticket


class DestaqueSetorVitalTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_setor_vital", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste setor vital", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor_vital = Setor.objects.create(nome="UTI teste", peso_setor=5)
        self.setor_comum = Setor.objects.create(nome="Setor comum teste vital", peso_setor=2)
        self.client.login(username="tecnico_teste_setor_vital", password="senha-teste-123")

    def _abrir(self, setor, descricao):
        return abrir_ticket(
            categoria_sugerida=self.categoria, setor=setor, descricao=descricao,
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="",
        )

    def test_parametro_foi_semeado_pela_migracao(self):
        parametro = ParametroSistema.objects.get(chave="peso_setor_vital")
        self.assertEqual(parametro.valor, "4")

    def test_chamado_de_setor_vital_mostra_selo(self):
        ticket = self._abrir(self.setor_vital, "Chamado em setor vital")
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        tickets_ctx = {t.pk: t for t in resposta.context["tickets"]}
        self.assertTrue(tickets_ctx[ticket.pk].setor_vital)
        self.assertContains(resposta, "Setor vital")

    def test_chamado_de_setor_comum_nao_mostra_selo(self):
        self._abrir(self.setor_comum, "Chamado em setor comum")
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        tickets_ctx = list(resposta.context["tickets"])
        self.assertFalse(any(t.setor_vital for t in tickets_ctx))
        self.assertNotContains(resposta, "Setor vital")

    def test_limiar_e_configuravel_via_parametro_sistema(self):
        """Subindo o limiar pra 5, um setor de peso 4 deixa de ser vital —
        prova que o valor não está mais fixo no código."""
        # .save() (não .update()) pra disparar o signal que invalida o
        # cache do parâmetro — ver tickets/signals.py.
        parametro = ParametroSistema.objects.get(chave="peso_setor_vital")
        parametro.valor = "5"
        parametro.save()
        setor_peso_4 = Setor.objects.create(nome="Setor peso 4 teste", peso_setor=4)
        self._abrir(setor_peso_4, "Chamado peso 4")

        resposta = self.client.get(reverse("tickets:fila_tickets"))
        tickets_ctx = list(resposta.context["tickets"])
        self.assertFalse(any(t.setor_vital for t in tickets_ctx))
