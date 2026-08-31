from django.core.cache import cache
from django.test import TestCase

from tickets.models import Categoria, ExcecaoPrioridade, ParametroSistema, Setor
from tickets.services.prioridade import calcular_prioridade


class CalcularPrioridadeTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(
            nome="Categoria teste", grupo=Categoria.Grupo.SUPORTE,
            tipo=Categoria.Tipo.INCIDENTE, peso_categoria=3, sla_horas=8,
        )
        self.setor = Setor.objects.create(
            nome="Setor teste", peso_setor=4,
        )

    def tearDown(self):
        # get_parametro usa cache de processo (LocMemCache) que não é
        # revertido pelo rollback de transação do TestCase — sem isso, um
        # fator customizado num teste vaza pro próximo que ler a mesma chave.
        cache.clear()

    def test_prioridade_padrao_e_produto_dos_pesos(self):
        # Fatores de tipo entram com 1.0 na migration de seed, então o
        # comportamento padrão continua sendo só peso_categoria x peso_setor.
        self.assertEqual(calcular_prioridade(self.categoria, self.setor), 12)

    def test_excecao_sobrescreve_calculo_padrao(self):
        ExcecaoPrioridade.objects.create(
            categoria=self.categoria, setor=self.setor, peso_override=25,
        )
        self.assertEqual(calcular_prioridade(self.categoria, self.setor), 25)

    def test_fator_de_incidente_multiplica_a_prioridade(self):
        ParametroSistema.objects.update_or_create(
            chave="fator_prioridade_incidente", defaults={"valor": "1.5"}
        )
        # 3 x 4 x 1.5 = 18
        self.assertEqual(calcular_prioridade(self.categoria, self.setor), 18)

    def test_fator_de_requisicao_multiplica_a_prioridade(self):
        categoria_requisicao = Categoria.objects.create(
            nome="Categoria requisicao teste", grupo=Categoria.Grupo.SUPORTE,
            tipo=Categoria.Tipo.REQUISICAO, peso_categoria=3, sla_horas=8,
        )
        ParametroSistema.objects.update_or_create(
            chave="fator_prioridade_requisicao", defaults={"valor": "0.5"}
        )
        # 3 x 4 x 0.5 = 6
        self.assertEqual(calcular_prioridade(categoria_requisicao, self.setor), 6)

    def test_excecao_ignora_o_fator_de_tipo(self):
        ParametroSistema.objects.update_or_create(
            chave="fator_prioridade_incidente", defaults={"valor": "1.5"}
        )
        ExcecaoPrioridade.objects.create(
            categoria=self.categoria, setor=self.setor, peso_override=25,
        )
        self.assertEqual(calcular_prioridade(self.categoria, self.setor), 25)
