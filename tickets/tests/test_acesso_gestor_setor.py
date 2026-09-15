"""Gestor de setor que não é a TI é um usuário comum dentro do sistema.

Antes, qualquer `Setor.gestor` ganhava acesso operacional pleno (fila,
equipamentos, dashboard, histórico). Hoje só o gestor do setor de TI — que na
prática é o administrador do sistema — tem isso. Ver _tem_acesso_operacional
e _e_gestor_da_ti em views.py.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, ItemConfiguracao, Setor
from tickets.services.equipamento import obter_setor_ti


class AcessoOperacionalDoGestorTests(TestCase):
    def setUp(self):
        self.setor_comum = Setor.objects.create(nome="Setor teste acesso gestor", peso_setor=3)
        self.gestor_comum = get_user_model().objects.create_user(
            username="gestor_setor_comum", password="senha-teste-123",
        )
        self.setor_comum.gestor = self.gestor_comum
        self.setor_comum.save(update_fields=["gestor"])

        self.setor_ti = obter_setor_ti()
        self.gestor_ti = get_user_model().objects.create_user(
            username="gestor_da_ti", password="senha-teste-123",
        )
        self.setor_ti.gestor = self.gestor_ti
        self.setor_ti.save(update_fields=["gestor"])

    def _acessa(self, usuario, nome_rota):
        self.client.login(username=usuario, password="senha-teste-123")
        return self.client.get(reverse(nome_rota))

    def test_gestor_de_setor_comum_nao_entra_na_fila(self):
        self.assertEqual(self._acessa("gestor_setor_comum", "tickets:fila_tickets").status_code, 302)

    def test_gestor_de_setor_comum_nao_entra_nos_equipamentos(self):
        resposta = self._acessa("gestor_setor_comum", "tickets:listar_equipamentos")
        self.assertEqual(resposta.status_code, 302)

    def test_gestor_de_setor_comum_nao_entra_no_dashboard(self):
        self.assertEqual(self._acessa("gestor_setor_comum", "tickets:dashboard").status_code, 302)

    def test_gestor_da_ti_continua_entrando_na_fila(self):
        self.assertEqual(self._acessa("gestor_da_ti", "tickets:fila_tickets").status_code, 200)

    def test_gestor_da_ti_continua_entrando_nos_equipamentos(self):
        self.assertEqual(self._acessa("gestor_da_ti", "tickets:listar_equipamentos").status_code, 200)


class EdicaoDeEquipamentoPeloGestorTests(TestCase):
    """O CMDB é da TI: ser gestor do setor onde o equipamento está não dá mais
    direito de editá-lo (antes dava, por URL direta)."""

    def setUp(self):
        self.setor_comum = Setor.objects.create(nome="Setor teste edicao equip", peso_setor=3)
        self.gestor_comum = get_user_model().objects.create_user(
            username="gestor_edicao_equip", password="senha-teste-123",
        )
        self.setor_comum.gestor = self.gestor_comum
        self.setor_comum.save(update_fields=["gestor"])

        self.equipamento = ItemConfiguracao.objects.create(
            patrimonio="880011", categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor_comum,
            status=ItemConfiguracao.Status.ATIVO,
        )

    def test_gestor_do_setor_nao_edita_equipamento_do_proprio_setor(self):
        self.client.login(username="gestor_edicao_equip", password="senha-teste-123")
        resposta = self.client.get(
            reverse("tickets:editar_equipamento", args=[self.equipamento.pk])
        )
        self.assertEqual(resposta.status_code, 403)

    def test_tecnico_continua_editando(self):
        get_user_model().objects.create_user(
            username="tecnico_edicao_equip", is_staff=True, password="senha-teste-123",
        )
        self.client.login(username="tecnico_edicao_equip", password="senha-teste-123")
        resposta = self.client.get(
            reverse("tickets:editar_equipamento", args=[self.equipamento.pk])
        )
        self.assertEqual(resposta.status_code, 200)
