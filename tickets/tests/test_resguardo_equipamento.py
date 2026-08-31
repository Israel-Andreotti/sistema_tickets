from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tickets.forms import CadastrarEquipamentoForm
from tickets.models import ItemConfiguracao, Setor
from tickets.services.equipamento import liberar_resguardos_vencidos


class DataFimResguardoTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste resguardo", peso_setor=3)

    def _criar_item(self, **kwargs):
        return ItemConfiguracao.objects.create(
            patrimonio=kwargs.pop("patrimonio", "100001"),
            categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor,
            **kwargs,
        )

    def test_prazo_30_dias_para_lideranca(self):
        item = self._criar_item(
            status=ItemConfiguracao.Status.EM_RESGUARDO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.LIDERANCA,
            data_inicio_resguardo=timezone.now().date(),
        )
        self.assertEqual(item.prazo_resguardo_dias, 30)
        self.assertEqual(item.data_fim_resguardo, item.data_inicio_resguardo + timedelta(days=30))

    def test_prazo_15_dias_para_colaborador(self):
        item = self._criar_item(
            status=ItemConfiguracao.Status.EM_RESGUARDO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.COLABORADOR,
            data_inicio_resguardo=timezone.now().date(),
        )
        self.assertEqual(item.prazo_resguardo_dias, 15)
        self.assertEqual(item.data_fim_resguardo, item.data_inicio_resguardo + timedelta(days=15))

    def test_sem_nivel_cargo_nao_calcula_prazo(self):
        item = self._criar_item(status=ItemConfiguracao.Status.ATIVO)
        self.assertIsNone(item.prazo_resguardo_dias)
        self.assertIsNone(item.data_fim_resguardo)


class LiberarResguardosVencidosTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste liberar resguardo", peso_setor=3)

    def _criar_item(self, patrimonio, **kwargs):
        return ItemConfiguracao.objects.create(
            patrimonio=patrimonio, categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor, **kwargs,
        )

    def test_promove_resguardo_vencido(self):
        hoje = timezone.now().date()
        item = self._criar_item(
            "100002", status=ItemConfiguracao.Status.EM_RESGUARDO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.COLABORADOR,
            data_inicio_resguardo=hoje - timedelta(days=16),
        )
        total = liberar_resguardos_vencidos()
        item.refresh_from_db()
        self.assertEqual(total, 1)
        self.assertEqual(item.status, ItemConfiguracao.Status.RESGUARDO_LIBERADO)

    def test_nao_promove_resguardo_ainda_dentro_do_prazo(self):
        hoje = timezone.now().date()
        item = self._criar_item(
            "100003", status=ItemConfiguracao.Status.EM_RESGUARDO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.LIDERANCA,
            data_inicio_resguardo=hoje - timedelta(days=10),
        )
        total = liberar_resguardos_vencidos()
        item.refresh_from_db()
        self.assertEqual(total, 0)
        self.assertEqual(item.status, ItemConfiguracao.Status.EM_RESGUARDO)

    def test_ignora_equipamentos_em_outros_status(self):
        self._criar_item("100004", status=ItemConfiguracao.Status.ATIVO)
        self._criar_item("100005", status=ItemConfiguracao.Status.BAIXADO)
        total = liberar_resguardos_vencidos()
        self.assertEqual(total, 0)


class CadastrarEquipamentoFormResguardoTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste form resguardo", peso_setor=3)

    def _dados_base(self, **overrides):
        dados = {
            "patrimonio": "100006", "categoria": ItemConfiguracao.Categoria.COMPUTADOR,
            "marca": "Marca", "modelo": "Modelo", "setor": self.setor.pk,
            "status": ItemConfiguracao.Status.EM_RESGUARDO,
        }
        dados.update(overrides)
        return dados

    def test_exige_nivel_cargo_e_data_inicio_quando_em_resguardo(self):
        form = CadastrarEquipamentoForm(data=self._dados_base())
        self.assertFalse(form.is_valid())
        self.assertIn("nivel_cargo_desligado", form.errors)
        self.assertIn("data_inicio_resguardo", form.errors)

    def test_valido_com_nivel_cargo_e_data_inicio(self):
        form = CadastrarEquipamentoForm(data=self._dados_base(
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.LIDERANCA,
            data_inicio_resguardo="2026-01-01",
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_status_em_uso_nao_exige_campos_de_resguardo(self):
        form = CadastrarEquipamentoForm(data=self._dados_base(status=ItemConfiguracao.Status.EM_USO))
        self.assertTrue(form.is_valid(), form.errors)


class ListarEquipamentosAcionaLiberacaoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_listar_resguardo", is_staff=True, password="senha-teste-123",
        )
        self.setor = Setor.objects.create(nome="Setor teste listar resguardo", peso_setor=3)
        self.client.login(username="tecnico_teste_listar_resguardo", password="senha-teste-123")

    def test_visitar_lista_promove_resguardo_vencido(self):
        item = ItemConfiguracao.objects.create(
            patrimonio="100007", categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor,
            status=ItemConfiguracao.Status.EM_RESGUARDO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.COLABORADOR,
            data_inicio_resguardo=timezone.now().date() - timedelta(days=20),
        )
        self.client.get(reverse("tickets:listar_equipamentos"), {"todos": "1"})
        item.refresh_from_db()
        self.assertEqual(item.status, ItemConfiguracao.Status.RESGUARDO_LIBERADO)
