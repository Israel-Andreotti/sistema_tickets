from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from tickets.models import Categoria, Recomendacao, RegraRecomendacao, Setor, Ticket
from tickets.services.recomendacao import gerar_recomendacoes
from tickets.services.sla import fechar_ticket


class GerarRecomendacoesTests(TestCase):
    """Usa min_tickets_para_recomendacao=5 e desvio_critico_pct=50, semeados em
    0003_seed_parametros_e_regras."""

    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_recomendacao", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Sistema de agendamento/regulação teste", grupo=Categoria.Grupo.CLINICO,
            peso_categoria=4, sla_horas=10,
        )
        self.setor = Setor.objects.create(
            nome="Setor teste", peso_setor=5,
        )

    def _fechar_ticket_com_horas(self, horas_reais):
        ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            categoria_final=self.categoria,
            tecnico_responsavel=self.tecnico,
            movimentacao_confirmada=True,
            setor=self.setor,
            descricao="ticket de teste",
            solicitante_nome="Maria Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        ticket.refresh_from_db()
        data_fechamento = ticket.data_abertura + timedelta(hours=horas_reais)
        return fechar_ticket(ticket, data_fechamento=data_fechamento)

    def test_gera_recomendacao_critica_com_volume_e_desvio_suficientes(self):
        for _ in range(5):
            self._fechar_ticket_com_horas(15)  # sla=10h, desvio 5h => 50% => critico

        geradas = gerar_recomendacoes()

        self.assertEqual(len(geradas), 1)
        recomendacao = Recomendacao.objects.get()
        self.assertEqual(recomendacao.categoria, self.categoria)
        self.assertEqual(recomendacao.setor, self.setor)
        self.assertEqual(recomendacao.regra.tipo_desvio, "critico")

    def test_nao_gera_recomendacao_com_volume_insuficiente(self):
        for _ in range(4):  # abaixo de min_tickets_para_recomendacao=5
            self._fechar_ticket_com_horas(15)

        geradas = gerar_recomendacoes()

        self.assertEqual(geradas, [])
        self.assertEqual(Recomendacao.objects.count(), 0)

    def test_nao_duplica_recomendacao_ja_gerada_na_janela(self):
        for _ in range(5):
            self._fechar_ticket_com_horas(15)

        primeira_execucao = gerar_recomendacoes()
        segunda_execucao = gerar_recomendacoes()

        self.assertEqual(len(primeira_execucao), 1)
        self.assertEqual(segunda_execucao, [])
        self.assertEqual(Recomendacao.objects.count(), 1)
