import io
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from tickets.models import Categoria, Setor
from tickets.services.classificacao import (
    abrir_ticket,
    confirmar_classificacao_final,
    registrar_classificacao_ia,
)


class AvaliarClassificadorIaTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste avaliar ia", peso_setor=3)
        self.categoria_impressora = Categoria.objects.create(
            nome="Impressora teste avaliar", grupo=Categoria.Grupo.IMPRESSORA,
            peso_categoria=2, sla_horas=8,
        )
        self.categoria_prontuario = Categoria.objects.create(
            nome="Prontuário teste avaliar", grupo=Categoria.Grupo.CLINICO,
            peso_categoria=4, sla_horas=1,
        )

    def _abrir(self):
        return abrir_ticket(
            categoria_sugerida=self.categoria_impressora, setor=self.setor, descricao="teste",
            solicitante_nome="X", solicitante_ramal="1", solicitante_sala="Y",
        )

    def test_sem_tickets_comparaveis_nao_quebra(self):
        saida = io.StringIO()
        call_command("avaliar_classificador_ia", stdout=saida)
        self.assertIn("Nenhum chamado", saida.getvalue())

    def test_calcula_acuracia_e_confusoes(self):
        # Um acerto: IA e técnico concordam.
        ticket_certo = self._abrir()
        registrar_classificacao_ia(ticket_certo, self.categoria_impressora, confianca=Decimal("0.80"))
        confirmar_classificacao_final(ticket_certo, self.categoria_impressora)

        # Um erro: IA chutou impressora, técnico confirmou prontuário.
        ticket_errado = self._abrir()
        registrar_classificacao_ia(ticket_errado, self.categoria_impressora, confianca=Decimal("0.40"))
        confirmar_classificacao_final(ticket_errado, self.categoria_prontuario)

        saida = io.StringIO()
        call_command("avaliar_classificador_ia", stdout=saida)
        texto = saida.getvalue()

        self.assertIn("1 de 2", texto)
        self.assertIn("50.0%", texto)
        self.assertIn("Impressora teste avaliar", texto)
        self.assertIn("Prontuário teste avaliar", texto)

    def test_ignora_tickets_sem_categoria_ia_ou_sem_final(self):
        # Só categoria_ia, sem categoria_final confirmada ainda — não entra na conta.
        ticket = self._abrir()
        registrar_classificacao_ia(ticket, self.categoria_impressora, confianca=Decimal("0.90"))

        saida = io.StringIO()
        call_command("avaliar_classificador_ia", stdout=saida)
        self.assertIn("Nenhum chamado", saida.getvalue())
