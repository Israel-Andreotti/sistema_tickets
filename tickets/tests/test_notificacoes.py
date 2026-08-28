from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, ComentarioTicket, Notificacao, Setor, Ticket
from tickets.services.classificacao import atribuir_tecnico, confirmar_classificacao_final
from tickets.services.notificacoes import marcar_como_lida, marcar_todas_como_lidas, notificar
from tickets.services.sla import fechar_ticket


class NotificarTests(TestCase):
    def setUp(self):
        self.solicitante = get_user_model().objects.create_user(username="solicitante_teste_notif")
        self.categoria = Categoria.objects.create(
            nome="Categoria teste notif", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste notif", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante=self.solicitante,
            solicitante_nome="Solicitante Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )

    def test_notificar_cria_registro_para_o_solicitante(self):
        notificacao = notificar(self.ticket, Notificacao.Tipo.MUDANCA_STATUS, "Mensagem teste")
        self.assertIsNotNone(notificacao)
        self.assertEqual(notificacao.destinatario, self.solicitante)
        self.assertEqual(notificacao.ticket, self.ticket)
        self.assertFalse(notificacao.lida)

    def test_notificar_nao_cria_registro_sem_solicitante(self):
        self.ticket.solicitante = None
        self.ticket.save(update_fields=["solicitante"])
        notificacao = notificar(self.ticket, Notificacao.Tipo.MUDANCA_STATUS, "Mensagem teste")
        self.assertIsNone(notificacao)
        self.assertEqual(Notificacao.objects.count(), 0)

    def test_marcar_como_lida_define_lida_e_lida_em(self):
        notificacao = notificar(self.ticket, Notificacao.Tipo.MUDANCA_STATUS, "Mensagem teste")
        self.assertIsNone(notificacao.lida_em)
        marcar_como_lida(notificacao)
        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)
        self.assertIsNotNone(notificacao.lida_em)

    def test_marcar_todas_como_lidas_so_afeta_o_usuario_informado(self):
        outro_solicitante = get_user_model().objects.create_user(username="outro_solicitante_teste_notif")
        outro_ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Outro",
            solicitante=outro_solicitante, solicitante_nome="Outro", solicitante_ramal="1",
            solicitante_sala="Sala 1",
        )
        notificar(self.ticket, Notificacao.Tipo.MUDANCA_STATUS, "Para o solicitante")
        notificar(self.ticket, Notificacao.Tipo.MUDANCA_STATUS, "Outra para o solicitante")
        notificar(outro_ticket, Notificacao.Tipo.MUDANCA_STATUS, "Para o outro")

        total_afetado = marcar_todas_como_lidas(self.solicitante)

        self.assertEqual(total_afetado, 2)
        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.solicitante, lida=False).count(), 0
        )
        self.assertEqual(
            Notificacao.objects.filter(destinatario=outro_solicitante, lida=False).count(), 1
        )


class NotificacaoNasTransicoesDeStatusTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_notif", is_staff=True,
        )
        self.solicitante = get_user_model().objects.create_user(username="solicitante_teste_notif2")
        self.categoria = Categoria.objects.create(
            nome="Categoria teste notif2", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste notif2", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante=self.solicitante,
            solicitante_nome="Solicitante Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )

    def test_atribuir_tecnico_em_ticket_aberto_notifica(self):
        atribuir_tecnico(self.ticket, self.tecnico)
        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.solicitante, tipo=Notificacao.Tipo.MUDANCA_STATUS).count(),
            1,
        )

    def test_atribuir_tecnico_em_ticket_ja_em_atendimento_nao_duplica_notificacao(self):
        atribuir_tecnico(self.ticket, self.tecnico)
        outro_tecnico = get_user_model().objects.create_user(
            username="outro_tecnico_teste_notif", is_staff=True,
        )
        atribuir_tecnico(self.ticket, outro_tecnico)
        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.solicitante, tipo=Notificacao.Tipo.MUDANCA_STATUS).count(),
            1,
        )

    def test_confirmar_classificacao_final_em_ticket_aberto_notifica(self):
        confirmar_classificacao_final(self.ticket, self.categoria)
        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.solicitante, tipo=Notificacao.Tipo.MUDANCA_STATUS).count(),
            1,
        )

    def test_atribuir_e_depois_classificar_gera_apenas_uma_notificacao(self):
        atribuir_tecnico(self.ticket, self.tecnico)
        confirmar_classificacao_final(self.ticket, self.categoria)
        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.solicitante, tipo=Notificacao.Tipo.MUDANCA_STATUS).count(),
            1,
        )

    def test_fechar_ticket_notifica(self):
        self.ticket.categoria_final = self.categoria
        self.ticket.tecnico_responsavel = self.tecnico
        self.ticket.movimentacao_confirmada = True
        self.ticket.save(update_fields=["categoria_final", "tecnico_responsavel", "movimentacao_confirmada"])

        fechar_ticket(self.ticket, data_fechamento=self.ticket.data_abertura + timedelta(hours=1))

        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.solicitante, tipo=Notificacao.Tipo.MUDANCA_STATUS).count(),
            1,
        )


class NotificacaoAoComentarViewTests(TestCase):
    def setUp(self):
        self.client_tecnico = self.client_class()
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_notif_view", is_staff=True, password="senha-teste-123",
        )
        self.solicitante = get_user_model().objects.create_user(username="solicitante_teste_notif_view")
        self.categoria = Categoria.objects.create(
            nome="Categoria teste notif view", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste notif view", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante=self.solicitante,
            solicitante_nome="Solicitante Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        self.client.login(username="tecnico_teste_notif_view", password="senha-teste-123")

    def test_comentario_nota_interna_nao_notifica(self):
        self.client.post(
            reverse("tickets:adicionar_comentario", args=[self.ticket.pk]),
            {"tipo": ComentarioTicket.Tipo.NOTA_INTERNA, "texto": "Nota interna de teste"},
        )
        self.assertEqual(Notificacao.objects.filter(destinatario=self.solicitante).count(), 0)

    def test_comentario_resposta_usuario_notifica(self):
        self.client.post(
            reverse("tickets:adicionar_comentario", args=[self.ticket.pk]),
            {"tipo": ComentarioTicket.Tipo.RESPOSTA_USUARIO, "texto": "Resposta de teste"},
        )
        self.assertEqual(
            Notificacao.objects.filter(
                destinatario=self.solicitante, tipo=Notificacao.Tipo.NOVO_COMENTARIO
            ).count(),
            1,
        )

    def test_comentario_desfecho_notifica(self):
        self.client.post(
            reverse("tickets:adicionar_comentario", args=[self.ticket.pk]),
            {"tipo": ComentarioTicket.Tipo.DESFECHO, "texto": "Desfecho de teste"},
        )
        self.assertEqual(
            Notificacao.objects.filter(
                destinatario=self.solicitante, tipo=Notificacao.Tipo.NOVO_COMENTARIO
            ).count(),
            1,
        )


class NotificacaoViewsDoSolicitanteTests(TestCase):
    def setUp(self):
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_notif_views", password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste notif views", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste notif views", peso_setor=3)
        self.ticket = Ticket.objects.create(
            categoria_sugerida=self.categoria,
            setor=self.setor,
            descricao="Descrição teste",
            solicitante=self.solicitante,
            solicitante_nome="Solicitante Teste",
            solicitante_ramal="1234",
            solicitante_sala="Sala 10",
        )
        self.notificacao = notificar(self.ticket, Notificacao.Tipo.MUDANCA_STATUS, "Mensagem teste")
        self.client.login(username="solicitante_teste_notif_views", password="senha-teste-123")

    def test_notificacoes_novas_retorna_total_nao_lidas(self):
        resposta = self.client.get(reverse("tickets:notificacoes_novas"))
        self.assertEqual(resposta.json(), {"total_nao_lidas": 1})

    def test_marcar_notificacao_lida_marca_e_redireciona_para_o_ticket(self):
        resposta = self.client.post(
            reverse("tickets:marcar_notificacao_lida", args=[self.notificacao.pk])
        )
        self.notificacao.refresh_from_db()
        self.assertTrue(self.notificacao.lida)
        self.assertRedirects(resposta, reverse("tickets:meu_ticket_detalhe", args=[self.ticket.pk]))

    def test_outro_usuario_nao_marca_notificacao_alheia(self):
        outro = get_user_model().objects.create_user(
            username="outro_teste_notif_views", password="senha-teste-123",
        )
        self.client.logout()
        self.client.login(username="outro_teste_notif_views", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:marcar_notificacao_lida", args=[self.notificacao.pk])
        )
        self.assertEqual(resposta.status_code, 404)
        self.notificacao.refresh_from_db()
        self.assertFalse(self.notificacao.lida)

    def test_marcar_todas_como_lidas_zera_contagem(self):
        notificar(self.ticket, Notificacao.Tipo.NOVO_COMENTARIO, "Segunda mensagem")
        self.client.post(reverse("tickets:marcar_todas_notificacoes_lidas"))
        resposta = self.client.get(reverse("tickets:notificacoes_novas"))
        self.assertEqual(resposta.json(), {"total_nao_lidas": 0})
