import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tickets.models import Categoria, ItemConfiguracao, MovimentacaoEquipamento, Setor, Ticket
from tickets.services.classificacao import abrir_ticket
from tickets.services.equipamento import aplicar_movimentacoes_pendentes, movimentar_equipamento
from tickets.services.sla import fechar_ticket


class MovimentarEquipamentoMotivoRetornoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_motivo_retorno", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste motivo retorno", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste motivo retorno", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.equipamento = ItemConfiguracao.objects.create(
            patrimonio="200001", categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor, status=ItemConfiguracao.Status.EM_USO,
        )

    def test_grava_motivo_e_cargo_quando_desligamento(self):
        registro = movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_saida=self.equipamento,
            motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.DESLIGAMENTO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.LIDERANCA,
        )
        self.assertEqual(registro.motivo_retorno, MovimentacaoEquipamento.MotivoRetorno.DESLIGAMENTO)
        self.assertEqual(registro.nivel_cargo_desligado, ItemConfiguracao.NivelCargoDesligado.LIDERANCA)

    def test_ignora_cargo_quando_motivo_nao_e_desligamento(self):
        registro = movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_saida=self.equipamento,
            motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.FALTA,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.LIDERANCA,
        )
        self.assertEqual(registro.motivo_retorno, MovimentacaoEquipamento.MotivoRetorno.FALTA)
        self.assertIsNone(registro.nivel_cargo_desligado)

    def test_exige_motivo_quando_ha_equipamento_de_saida(self):
        with self.assertRaises(ValueError):
            movimentar_equipamento(self.ticket, autor=self.tecnico, equipamento_saida=self.equipamento)

    def test_exige_cargo_quando_motivo_e_desligamento(self):
        with self.assertRaises(ValueError):
            movimentar_equipamento(
                self.ticket, autor=self.tecnico, equipamento_saida=self.equipamento,
                motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.DESLIGAMENTO,
            )

    def test_nao_exige_motivo_sem_equipamento_de_saida(self):
        equipamento_entrada = ItemConfiguracao.objects.create(
            patrimonio="200002", categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor, status=ItemConfiguracao.Status.ATIVO,
        )
        # equipamento de entrada precisa estar lotado na TI — usa o setor do
        # parâmetro pra passar na elegibilidade, então força o setor_ti aqui.
        from tickets.services.equipamento import obter_setor_ti
        equipamento_entrada.setor = obter_setor_ti()
        equipamento_entrada.save(update_fields=["setor"])

        registro = movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_entrada=equipamento_entrada,
        )
        self.assertIsNone(registro.motivo_retorno)


class AplicarMovimentacoesPendentesMotivoRetornoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_aplicar_motivo", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste aplicar motivo", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste aplicar motivo", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.ticket.tecnico_responsavel = self.tecnico
        self.ticket.categoria_final = self.categoria
        self.ticket.movimentacao_confirmada = True
        self.ticket.save(update_fields=["tecnico_responsavel", "categoria_final", "movimentacao_confirmada"])

    def _criar_equipamento(self, patrimonio):
        return ItemConfiguracao.objects.create(
            patrimonio=patrimonio, categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor, status=ItemConfiguracao.Status.EM_USO,
        )

    def test_desligamento_deixa_equipamento_em_resguardo(self):
        equipamento = self._criar_equipamento("200003")
        movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_saida=equipamento,
            motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.DESLIGAMENTO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.LIDERANCA,
        )

        aplicar_movimentacoes_pendentes(self.ticket)

        equipamento.refresh_from_db()
        hoje = timezone.now().date()
        self.assertEqual(equipamento.status, ItemConfiguracao.Status.EM_RESGUARDO)
        self.assertEqual(equipamento.nivel_cargo_desligado, ItemConfiguracao.NivelCargoDesligado.LIDERANCA)
        self.assertEqual(equipamento.data_inicio_resguardo, hoje)
        self.assertEqual(equipamento.tecnico_responsavel_resguardo, self.tecnico)
        self.assertEqual(equipamento.ticket_origem_resguardo, self.ticket)
        self.assertEqual(equipamento.prazo_resguardo_dias, 30)

    def test_falta_mantem_comportamento_atual(self):
        equipamento = self._criar_equipamento("200004")
        movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_saida=equipamento,
            motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.FALTA,
        )

        aplicar_movimentacoes_pendentes(self.ticket)

        equipamento.refresh_from_db()
        self.assertEqual(equipamento.status, ItemConfiguracao.Status.MANUTENCAO)
        self.assertIsNone(equipamento.nivel_cargo_desligado)
        self.assertIsNone(equipamento.data_inicio_resguardo)
        self.assertIsNone(equipamento.tecnico_responsavel_resguardo)
        self.assertIsNone(equipamento.ticket_origem_resguardo)

    def test_troca_comum_mantem_comportamento_atual(self):
        equipamento = self._criar_equipamento("200005")
        movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_saida=equipamento,
            motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.TROCA_COMUM,
        )

        aplicar_movimentacoes_pendentes(self.ticket)

        equipamento.refresh_from_db()
        self.assertEqual(equipamento.status, ItemConfiguracao.Status.MANUTENCAO)
        self.assertIsNone(equipamento.tecnico_responsavel_resguardo)

    def test_fechar_ticket_aplica_resguardo_por_desligamento(self):
        """Ponta a ponta: fechar o chamado é o que dispara
        aplicar_movimentacoes_pendentes() de verdade (não só o teste direto
        acima) — confirma que o caminho real do fechamento também funciona."""
        equipamento = self._criar_equipamento("200006")
        movimentar_equipamento(
            self.ticket, autor=self.tecnico, equipamento_saida=equipamento,
            motivo_retorno=MovimentacaoEquipamento.MotivoRetorno.DESLIGAMENTO,
            nivel_cargo_desligado=ItemConfiguracao.NivelCargoDesligado.COLABORADOR,
        )

        fechar_ticket(self.ticket, data_fechamento=self.ticket.data_abertura)

        equipamento.refresh_from_db()
        self.assertEqual(equipamento.status, ItemConfiguracao.Status.EM_RESGUARDO)
        self.assertEqual(equipamento.prazo_resguardo_dias, 15)


class MovimentarEquipamentoViewMotivoRetornoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_view_motivo", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste view motivo", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste view motivo", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.equipamento = ItemConfiguracao.objects.create(
            patrimonio="200007", categoria=ItemConfiguracao.Categoria.COMPUTADOR,
            marca="Marca", modelo="Modelo", setor=self.setor, status=ItemConfiguracao.Status.EM_USO,
        )
        self.client.login(username="tecnico_teste_view_motivo", password="senha-teste-123")

    def test_post_sem_motivo_retorno_falha(self):
        resposta = self.client.post(
            reverse("tickets:movimentar_equipamento", args=[self.ticket.pk]),
            {"itens": json.dumps([{"patrimonio": self.equipamento.patrimonio}])},
            follow=True,
        )
        self.assertContains(resposta, "Selecione um motivo válido")
        self.assertEqual(MovimentacaoEquipamento.objects.count(), 0)

    def test_post_desligamento_sem_cargo_falha(self):
        resposta = self.client.post(
            reverse("tickets:movimentar_equipamento", args=[self.ticket.pk]),
            {"itens": json.dumps([{
                "patrimonio": self.equipamento.patrimonio, "motivo_retorno": "desligamento",
            }])},
            follow=True,
        )
        self.assertContains(resposta, "Selecione o cargo do funcionário desligado")
        self.assertEqual(MovimentacaoEquipamento.objects.count(), 0)

    def test_post_desligamento_com_cargo_funciona(self):
        resposta = self.client.post(
            reverse("tickets:movimentar_equipamento", args=[self.ticket.pk]),
            {"itens": json.dumps([{
                "patrimonio": self.equipamento.patrimonio,
                "motivo_retorno": "desligamento",
                "nivel_cargo_desligado": "lideranca",
            }])},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        mov = MovimentacaoEquipamento.objects.get()
        self.assertEqual(mov.motivo_retorno, "desligamento")
        self.assertEqual(mov.nivel_cargo_desligado, "lideranca")
