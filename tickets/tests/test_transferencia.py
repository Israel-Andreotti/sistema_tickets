from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Notificacao, Setor, SolicitacaoTransferencia
from tickets.services.classificacao import (
    abrir_ticket,
    atribuir_tecnico,
    responder_solicitacao_transferencia,
    solicitar_transferencia,
)


class SolicitarTransferenciaTests(TestCase):
    def setUp(self):
        self.tecnico_a = get_user_model().objects.create_user(
            username="tecnico_a_transferencia", is_staff=True,
        )
        self.tecnico_b = get_user_model().objects.create_user(
            username="tecnico_b_transferencia", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste transferencia", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste transferencia", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(self.ticket, self.tecnico_a)

    def test_cria_solicitacao_e_notifica_responsavel_atual(self):
        solicitacao = solicitar_transferencia(self.ticket, solicitante=self.tecnico_b)
        self.assertEqual(solicitacao.status, SolicitacaoTransferencia.Status.PENDENTE)
        self.assertEqual(solicitacao.tecnico_atual, self.tecnico_a)
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.tecnico_a, ticket=self.ticket, tipo=Notificacao.Tipo.TRANSFERENCIA,
            ).exists()
        )

    def test_rejeita_chamado_sem_responsavel(self):
        outro_ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Sem responsavel",
            solicitante_nome="Ciclano", solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        with self.assertRaises(ValueError):
            solicitar_transferencia(outro_ticket, solicitante=self.tecnico_b)

    def test_rejeita_se_ja_e_o_responsavel(self):
        with self.assertRaises(ValueError):
            solicitar_transferencia(self.ticket, solicitante=self.tecnico_a)

    def test_rejeita_segunda_solicitacao_pendente(self):
        solicitar_transferencia(self.ticket, solicitante=self.tecnico_b)
        tecnico_c = get_user_model().objects.create_user(username="tecnico_c_transferencia", is_staff=True)
        with self.assertRaises(ValueError):
            solicitar_transferencia(self.ticket, solicitante=tecnico_c)


class ResponderSolicitacaoTransferenciaTests(TestCase):
    def setUp(self):
        self.tecnico_a = get_user_model().objects.create_user(
            username="tecnico_a_responder", is_staff=True,
        )
        self.tecnico_b = get_user_model().objects.create_user(
            username="tecnico_b_responder", is_staff=True,
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste responder", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste responder", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.solicitacao = solicitar_transferencia(self.ticket, solicitante=self.tecnico_b)

    def test_aceitar_transfere_e_notifica_solicitante(self):
        responder_solicitacao_transferencia(self.solicitacao, aceitar=True)
        self.ticket.refresh_from_db()
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.ticket.tecnico_responsavel, self.tecnico_b)
        self.assertEqual(self.solicitacao.status, SolicitacaoTransferencia.Status.ACEITA)
        self.assertIsNotNone(self.solicitacao.respondido_em)
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.tecnico_b, tipo=Notificacao.Tipo.TRANSFERENCIA,
            ).exists()
        )

    def test_recusar_nao_transfere_mas_notifica_solicitante(self):
        responder_solicitacao_transferencia(self.solicitacao, aceitar=False)
        self.ticket.refresh_from_db()
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.ticket.tecnico_responsavel, self.tecnico_a)
        self.assertEqual(self.solicitacao.status, SolicitacaoTransferencia.Status.RECUSADA)
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.tecnico_b, tipo=Notificacao.Tipo.TRANSFERENCIA,
            ).exists()
        )

    def test_rejeita_responder_solicitacao_ja_respondida(self):
        responder_solicitacao_transferencia(self.solicitacao, aceitar=True)
        with self.assertRaises(ValueError):
            responder_solicitacao_transferencia(self.solicitacao, aceitar=False)


class SolicitarTransferenciaViewTests(TestCase):
    def setUp(self):
        self.tecnico_a = get_user_model().objects.create_user(
            username="tecnico_a_view", is_staff=True, password="senha-teste-123",
        )
        self.tecnico_b = get_user_model().objects.create_user(
            username="tecnico_b_view", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste view transferencia", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste view transferencia", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(self.ticket, self.tecnico_a)

    def test_post_solicitar_transferencia_cria_solicitacao(self):
        self.client.login(username="tecnico_b_view", password="senha-teste-123")
        resposta = self.client.post(reverse("tickets:solicitar_transferencia", args=[self.ticket.pk]))
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertEqual(SolicitacaoTransferencia.objects.filter(ticket=self.ticket).count(), 1)

    def test_responder_bloqueia_quem_nao_e_o_tecnico_atual(self):
        self.client.login(username="tecnico_b_view", password="senha-teste-123")
        self.client.post(reverse("tickets:solicitar_transferencia", args=[self.ticket.pk]))
        solicitacao = SolicitacaoTransferencia.objects.get(ticket=self.ticket)

        # tecnico_b tentando responder a própria solicitação (não é o tecnico_atual)
        resposta = self.client.post(
            reverse("tickets:responder_transferencia", args=[self.ticket.pk, solicitacao.pk]),
            {"acao": "aceitar"},
        )
        self.assertEqual(resposta.status_code, 403)
        solicitacao.refresh_from_db()
        self.assertEqual(solicitacao.status, SolicitacaoTransferencia.Status.PENDENTE)

    def test_tecnico_atual_consegue_aceitar(self):
        self.client.login(username="tecnico_b_view", password="senha-teste-123")
        self.client.post(reverse("tickets:solicitar_transferencia", args=[self.ticket.pk]))
        solicitacao = SolicitacaoTransferencia.objects.get(ticket=self.ticket)

        self.client.login(username="tecnico_a_view", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:responder_transferencia", args=[self.ticket.pk, solicitacao.pk]),
            {"acao": "aceitar"},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.tecnico_responsavel, self.tecnico_b)


class DetalheTicketTransferenciaTemplateTests(TestCase):
    def setUp(self):
        self.tecnico_a = get_user_model().objects.create_user(
            username="tecnico_a_template", is_staff=True, password="senha-teste-123",
        )
        self.tecnico_b = get_user_model().objects.create_user(
            username="tecnico_b_template", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste template transferencia", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste template transferencia", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )

    def test_sem_responsavel_mostra_assumir_chamado(self):
        self.client.login(username="tecnico_b_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Assumir chamado")
        self.assertNotContains(resposta, "Solicitar chamado")

    def test_com_responsavel_outro_tecnico_mostra_solicitar_chamado(self):
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.client.login(username="tecnico_b_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Solicitar chamado")
        self.assertNotContains(resposta, "Assumir chamado")

    def test_card_mostra_avatar_com_iniciais_do_responsavel(self):
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.client.login(username="tecnico_b_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "avatar-circle")
        self.assertContains(resposta, "TE")

    def test_com_solicitacao_pendente_tecnico_atual_ve_transferir_e_recusar(self):
        atribuir_tecnico(self.ticket, self.tecnico_a)
        solicitar_transferencia(self.ticket, solicitante=self.tecnico_b)
        self.client.login(username="tecnico_a_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Transferir")
        self.assertContains(resposta, "Recusar")

    def test_com_solicitacao_pendente_outro_tecnico_ve_aviso(self):
        atribuir_tecnico(self.ticket, self.tecnico_a)
        solicitar_transferencia(self.ticket, solicitante=self.tecnico_b)
        tecnico_c = get_user_model().objects.create_user(
            username="tecnico_c_template", is_staff=True, password="senha-teste-123",
        )
        self.client.login(username="tecnico_c_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Solicitação de transferência pendente")
        self.assertNotContains(resposta, "Solicitar chamado")
        self.assertContains(resposta, "Gerenciar")

    def test_tecnico_sem_responsavel_ve_botao_atribuir_para_mim_direto(self):
        """Pra técnico, o card usa um botão direto (sem abrir o modal) —
        ver detalhe_ticket.html: só aparece "Gerenciar" quando já há
        responsável (aí o modal segue existindo pro fluxo de solicitação)."""
        self.client.login(username="tecnico_b_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Atribuir para mim")

    def test_tecnico_nao_ve_seletor_de_atribuicao_livre(self):
        """O picker "Atribuir/Reatribuir para [qualquer técnico]" é a
        atribuição direta pra outra pessoa que fica restrita a quem não é
        técnico (gestor/superusuário) — ver a checagem de request.user.is_staff."""
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.client.login(username="tecnico_b_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertNotContains(resposta, "Selecione um técnico...")

    def test_tecnico_com_responsavel_outro_solicita_direto_pelo_card(self):
        """O botão "Solicitar chamado" do card (fora do modal) já é o form
        de verdade — clicar nele deve criar a solicitação sem precisar
        abrir "Gerenciar"."""
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.client.login(username="tecnico_b_template", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:solicitar_transferencia", args=[self.ticket.pk])
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertTrue(
            self.ticket.solicitacoes_transferencia.filter(solicitante=self.tecnico_b).exists()
        )

    def test_tecnico_responsavel_sem_solicitacao_pendente_ve_gerenciar_e_tag_voce(self):
        """Sem pendência, o card do próprio responsável não oferece
        "Atribuir para mim"/"Solicitar chamado" (ele já é o responsável) —
        mas mantém o botão "Gerenciar" pro alinhamento com os outros cards,
        e mostra a tag "Atribuído a você"."""
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.client.login(username="tecnico_a_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertNotContains(resposta, "Atribuir para mim")
        self.assertNotContains(resposta, "Solicitar chamado")
        self.assertContains(resposta, "Gerenciar")
        self.assertContains(resposta, "Atribuído a você")

    def test_gestor_continua_vendo_seletor_de_atribuicao_livre(self):
        gestor = get_user_model().objects.create_user(
            username="gestor_teste_template", password="senha-teste-123",
        )
        self.setor.gestor = gestor
        self.setor.save(update_fields=["gestor"])
        atribuir_tecnico(self.ticket, self.tecnico_a)
        self.client.login(username="gestor_teste_template", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Selecione um técnico...")
