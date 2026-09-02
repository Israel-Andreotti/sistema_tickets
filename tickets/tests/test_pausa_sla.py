from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tickets.models import Categoria, Notificacao, PausaSLA, Setor, Ticket
from tickets.services.pausa import pausar_ticket, retomar_ticket, tempo_pausado_total
from tickets.services.sla import fechar_ticket


class PausarTicketTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_pausa", is_staff=True,
        )
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_pausa",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste pausa", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste pausa", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            codigo_tipo=self.categoria.tipo,
            codigo_numero=Ticket.objects.count() + 1,
            tecnico_responsavel=self.tecnico,
            solicitante=self.solicitante,
            status=Ticket.Status.EM_ATENDIMENTO,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante_nome="Fulano",
            solicitante_ramal="1",
            solicitante_sala="Sala 1",
        )

    def test_pausar_cria_pausa_e_muda_status(self):
        pausa = pausar_ticket(
            self.ticket, autor=self.tecnico,
            motivo=PausaSLA.Motivo.AGUARDANDO_FORNECEDOR, observacao="Aguardando peça X",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.PAUSADO)
        self.assertEqual(pausa.motivo, PausaSLA.Motivo.AGUARDANDO_FORNECEDOR)
        self.assertIsNone(pausa.finalizada_em)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.solicitante, ticket=self.ticket).exists()
        )

    def test_rejeita_pausar_chamado_ja_pausado(self):
        pausar_ticket(self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_FORNECEDOR)
        with self.assertRaises(ValueError):
            pausar_ticket(self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_PECA)

    def test_rejeita_pausar_chamado_fechado(self):
        self.ticket.status = Ticket.Status.FECHADO
        self.ticket.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            pausar_ticket(self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.OUTRO)

    def test_retomar_encerra_pausa_e_volta_status(self):
        pausar_ticket(self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_USUARIO)
        pausa = retomar_ticket(self.ticket, autor=self.tecnico)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.EM_ATENDIMENTO)
        self.assertIsNotNone(pausa.finalizada_em)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.solicitante, ticket=self.ticket).count() >= 2
        )

    def test_rejeita_retomar_chamado_nao_pausado(self):
        with self.assertRaises(ValueError):
            retomar_ticket(self.ticket, autor=self.tecnico)


class TempoPausadoTotalTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_tempo_pausado", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste tempo pausado", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste tempo pausado", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            codigo_tipo=self.categoria.tipo,
            codigo_numero=Ticket.objects.count() + 1,
            tecnico_responsavel=self.tecnico,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante_nome="Fulano",
            solicitante_ramal="1",
            solicitante_sala="Sala 1",
        )

    def test_soma_pausas_ja_fechadas(self):
        agora = timezone.now()
        p1 = PausaSLA.objects.create(ticket=self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_FORNECEDOR)
        PausaSLA.objects.filter(pk=p1.pk).update(
            iniciada_em=agora - timedelta(hours=10), finalizada_em=agora - timedelta(hours=8),
        )
        p2 = PausaSLA.objects.create(ticket=self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_PECA)
        PausaSLA.objects.filter(pk=p2.pk).update(
            iniciada_em=agora - timedelta(hours=5), finalizada_em=agora - timedelta(hours=3),
        )
        total = tempo_pausado_total(self.ticket, referencia=agora)
        self.assertEqual(total, timedelta(hours=4))

    def test_pausa_em_aberto_conta_ate_a_referencia(self):
        agora = timezone.now()
        pausa = PausaSLA.objects.create(ticket=self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_USUARIO)
        PausaSLA.objects.filter(pk=pausa.pk).update(iniciada_em=agora - timedelta(hours=3))
        total = tempo_pausado_total(self.ticket, referencia=agora)
        self.assertEqual(total, timedelta(hours=3))


class FecharTicketComPausaTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_fechar_pausa", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste fechar pausa", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste fechar pausa", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            categoria_final=self.categoria,
            codigo_tipo=self.categoria.tipo,
            codigo_numero=Ticket.objects.count() + 1,
            tecnico_responsavel=self.tecnico,
            movimentacao_confirmada=True,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante_nome="Fulano",
            solicitante_ramal="1",
            solicitante_sala="Sala 1",
        )

    def test_tempo_real_desconta_pausa_encerrada(self):
        self.ticket.refresh_from_db()
        pausa = PausaSLA.objects.create(
            ticket=self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_FORNECEDOR,
        )
        PausaSLA.objects.filter(pk=pausa.pk).update(
            iniciada_em=self.ticket.data_abertura + timedelta(hours=2),
            finalizada_em=self.ticket.data_abertura + timedelta(hours=5),
        )
        data_fechamento = self.ticket.data_abertura + timedelta(hours=12)

        historico = fechar_ticket(self.ticket, data_fechamento=data_fechamento)

        self.assertEqual(historico.tempo_pausado, Decimal("3.00"))
        self.assertEqual(historico.tempo_real, Decimal("9.00"))
        self.assertEqual(historico.desvio, Decimal("1.00"))

    def test_rejeita_fechar_com_pausa_aberta(self):
        self.ticket.status = Ticket.Status.PAUSADO
        self.ticket.save(update_fields=["status"])
        PausaSLA.objects.create(ticket=self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_FORNECEDOR)
        with self.assertRaises(ValueError):
            fechar_ticket(self.ticket)


class PausarRetomarViewTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_pausa_view", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste pausa view", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste pausa view", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            codigo_tipo=self.categoria.tipo,
            codigo_numero=Ticket.objects.count() + 1,
            tecnico_responsavel=self.tecnico,
            status=Ticket.Status.EM_ATENDIMENTO,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante_nome="Fulano",
            solicitante_ramal="1",
            solicitante_sala="Sala 1",
        )
        self.client.login(username="tecnico_teste_pausa_view", password="senha-teste-123")

    def test_post_pausar_com_motivo_valido(self):
        resposta = self.client.post(
            reverse("tickets:pausar_ticket", args=[self.ticket.pk]),
            {"motivo": "aguardando_fornecedor", "observacao": "Peça a caminho"},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.PAUSADO)

    def test_post_pausar_com_motivo_invalido_nao_pausa(self):
        resposta = self.client.post(
            reverse("tickets:pausar_ticket", args=[self.ticket.pk]),
            {"motivo": "motivo_que_nao_existe"},
            follow=True,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.EM_ATENDIMENTO)
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("válido" in m for m in mensagens))

    def test_post_retomar(self):
        pausar_ticket(self.ticket, autor=self.tecnico, motivo=PausaSLA.Motivo.AGUARDANDO_FORNECEDOR)
        resposta = self.client.post(reverse("tickets:retomar_ticket", args=[self.ticket.pk]))
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.EM_ATENDIMENTO)


class FiltroStatusPausadoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_filtro_pausa", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste filtro pausa", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste filtro pausa", peso_setor=3)
        self.ticket_pausado = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            codigo_tipo=self.categoria.tipo,
            codigo_numero=Ticket.objects.count() + 1,
            tecnico_responsavel=self.tecnico,
            status=Ticket.Status.PAUSADO,
            setor=self.setor,
            descricao="Chamado pausado",
            solicitante_nome="Fulano Pausado",
            solicitante_ramal="1",
            solicitante_sala="Sala 1",
        )
        self.ticket_ativo = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            codigo_tipo=self.categoria.tipo,
            codigo_numero=Ticket.objects.count() + 1,
            tecnico_responsavel=self.tecnico,
            status=Ticket.Status.EM_ATENDIMENTO,
            setor=self.setor,
            descricao="Chamado ativo",
            solicitante_nome="Fulano Ativo",
            solicitante_ramal="2",
            solicitante_sala="Sala 2",
        )
        self.client.login(username="tecnico_teste_filtro_pausa", password="senha-teste-123")

    def test_filtro_status_pausado_na_fila(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"status": "pausado"})
        tickets_ids = {t.pk for t in resposta.context["tickets"]}
        self.assertIn(self.ticket_pausado.pk, tickets_ids)
        self.assertNotIn(self.ticket_ativo.pk, tickets_ids)
