from django.test import TestCase

from tickets.models import Categoria, ExcecaoPrioridade, Setor
from tickets.services.prioridade import calcular_prioridade


class CalcularPrioridadeTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(
            nome="Categoria teste", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=3, sla_horas=8,
        )
        self.setor = Setor.objects.create(
            nome="Setor teste", peso_setor=4,
        )

    def test_prioridade_padrao_e_produto_dos_pesos(self):
        self.assertEqual(calcular_prioridade(self.categoria, self.setor), 12)

    def test_excecao_sobrescreve_calculo_padrao(self):
        ExcecaoPrioridade.objects.create(
            categoria=self.categoria, setor=self.setor, peso_override=25,
        )
        self.assertEqual(calcular_prioridade(self.categoria, self.setor), 25)
