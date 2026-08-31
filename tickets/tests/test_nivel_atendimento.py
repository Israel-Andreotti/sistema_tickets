from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, EscalonamentoTicket, Notificacao, PerfilTecnico, Setor
from tickets.services.classificacao import abrir_ticket, escalar_ticket, niveis_acima
from tickets.services.notificacoes import notificar_tecnicos_nivel


class NiveisAcimaTests(TestCase):
    def test_n1_oferece_n2_e_n3(self):
        self.assertEqual(niveis_acima(Categoria.NivelAtendimento.N1), ["n2", "n3"])

    def test_n2_oferece_so_n3(self):
        self.assertEqual(niveis_acima(Categoria.NivelAtendimento.N2), ["n3"])

    def test_n3_nao_oferece_nada(self):
        self.assertEqual(niveis_acima(Categoria.NivelAtendimento.N3), [])


class AbrirTicketNivelTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste nivel", peso_setor=3)

    def test_ticket_nasce_com_nivel_da_categoria(self):
        categoria_n2 = Categoria.objects.create(
            nome="Categoria N2 teste", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8, nivel_atendimento=Categoria.NivelAtendimento.N2,
        )
        ticket = abrir_ticket(
            categoria_sugerida=categoria_n2, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.assertEqual(ticket.nivel_atual, Categoria.NivelAtendimento.N2)

    def test_ticket_nasce_n1_por_padrao(self):
        categoria = Categoria.objects.create(
            nome="Categoria N1 teste", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        ticket = abrir_ticket(
            categoria_sugerida=categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.assertEqual(ticket.nivel_atual, Categoria.NivelAtendimento.N1)


class EscalarTicketTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_escalonamento", is_staff=True,
        )
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_escalonamento",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste escalonamento", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste escalonamento", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
            solicitante=self.solicitante,
        )

    def test_escala_de_n1_para_n2_e_grava_log(self):
        escalonamento = escalar_ticket(
            self.ticket, autor=self.tecnico, novo_nivel=Categoria.NivelAtendimento.N2,
            justificativa="Precisa de especialista",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.nivel_atual, Categoria.NivelAtendimento.N2)
        self.assertEqual(escalonamento.nivel_anterior, Categoria.NivelAtendimento.N1)
        self.assertEqual(escalonamento.nivel_novo, Categoria.NivelAtendimento.N2)
        self.assertEqual(escalonamento.autor, self.tecnico)
        self.assertEqual(escalonamento.justificativa, "Precisa de especialista")

    def test_permite_pular_direto_para_n3(self):
        escalar_ticket(self.ticket, autor=self.tecnico, novo_nivel=Categoria.NivelAtendimento.N3)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.nivel_atual, Categoria.NivelAtendimento.N3)

    def test_rejeita_escalar_para_mesmo_nivel(self):
        with self.assertRaises(ValueError):
            escalar_ticket(self.ticket, autor=self.tecnico, novo_nivel=Categoria.NivelAtendimento.N1)

    def test_rejeita_escalar_para_nivel_inferior(self):
        escalar_ticket(self.ticket, autor=self.tecnico, novo_nivel=Categoria.NivelAtendimento.N2)
        with self.assertRaises(ValueError):
            escalar_ticket(self.ticket, autor=self.tecnico, novo_nivel=Categoria.NivelAtendimento.N1)

    def test_dispara_notificacao_para_solicitante(self):
        escalar_ticket(self.ticket, autor=self.tecnico, novo_nivel=Categoria.NivelAtendimento.N2)
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.solicitante, ticket=self.ticket,
                tipo=Notificacao.Tipo.MUDANCA_STATUS,
            ).exists()
        )


class EscalarTicketViewTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_escalar_view", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste escalar view", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste escalar view", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.client.login(username="tecnico_teste_escalar_view", password="senha-teste-123")

    def test_post_escala_ticket(self):
        resposta = self.client.post(
            reverse("tickets:escalar_ticket", args=[self.ticket.pk]),
            {"novo_nivel": "n2", "justificativa": "Motivo qualquer"},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.nivel_atual, "n2")
        self.assertEqual(EscalonamentoTicket.objects.filter(ticket=self.ticket).count(), 1)

    def test_post_com_nivel_igual_nao_escala_e_mostra_erro(self):
        resposta = self.client.post(
            reverse("tickets:escalar_ticket", args=[self.ticket.pk]),
            {"novo_nivel": "n1"},
            follow=True,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.nivel_atual, "n1")
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("acima" in m for m in mensagens))

    def test_post_com_nivel_invalido_mostra_erro(self):
        resposta = self.client.post(
            reverse("tickets:escalar_ticket", args=[self.ticket.pk]),
            {"novo_nivel": "n9"},
            follow=True,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.nivel_atual, "n1")
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("válido" in m for m in mensagens))


class FiltroNivelTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_filtro_nivel", is_staff=True, password="senha-teste-123",
        )
        self.setor = Setor.objects.create(nome="Setor teste filtro nivel", peso_setor=3)
        self.categoria_n1 = Categoria.objects.create(
            nome="Categoria N1 filtro", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8, nivel_atendimento=Categoria.NivelAtendimento.N1,
        )
        self.categoria_n3 = Categoria.objects.create(
            nome="Categoria N3 filtro", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8, nivel_atendimento=Categoria.NivelAtendimento.N3,
        )
        self.ticket_n1 = abrir_ticket(
            categoria_sugerida=self.categoria_n1, setor=self.setor, descricao="Chamado N1",
            solicitante_nome="Fulano N1", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.ticket_n3 = abrir_ticket(
            categoria_sugerida=self.categoria_n3, setor=self.setor, descricao="Chamado N3",
            solicitante_nome="Fulano N3", solicitante_ramal="2", solicitante_sala="Sala 2",
        )
        self.client.login(username="tecnico_teste_filtro_nivel", password="senha-teste-123")

    def test_filtro_nivel_na_fila(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"nivel": "n3"})
        tickets_ids = {t.pk for t in resposta.context["tickets"]}
        self.assertIn(self.ticket_n3.pk, tickets_ids)
        self.assertNotIn(self.ticket_n1.pk, tickets_ids)


class PerfilTecnicoSignalTests(TestCase):
    def test_usuario_staff_ganha_perfil_tecnico_automaticamente(self):
        tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_signal_perfil", is_staff=True,
        )
        perfil = PerfilTecnico.objects.get(usuario=tecnico)
        self.assertEqual(perfil.nivel_atendimento, Categoria.NivelAtendimento.N1)

    def test_usuario_comum_nao_ganha_perfil_tecnico(self):
        solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_signal_perfil",
        )
        self.assertFalse(PerfilTecnico.objects.filter(usuario=solicitante).exists())

    def test_promover_usuario_a_staff_cria_perfil(self):
        usuario = get_user_model().objects.create_user(
            username="usuario_teste_promovido", is_staff=False,
        )
        self.assertFalse(PerfilTecnico.objects.filter(usuario=usuario).exists())
        usuario.is_staff = True
        usuario.save()
        self.assertTrue(PerfilTecnico.objects.filter(usuario=usuario).exists())


class NotificarTecnicosNivelTests(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste notificar tecnicos", peso_setor=3)
        self.categoria = Categoria.objects.create(
            nome="Categoria teste notificar tecnicos", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        self.tecnico_n1 = get_user_model().objects.create_user(username="tecnico_n1_teste", is_staff=True)
        self.tecnico_n2_a = get_user_model().objects.create_user(username="tecnico_n2_a_teste", is_staff=True)
        self.tecnico_n2_b = get_user_model().objects.create_user(username="tecnico_n2_b_teste", is_staff=True)
        self.tecnico_n2_a.perfil_tecnico.nivel_atendimento = Categoria.NivelAtendimento.N2
        self.tecnico_n2_a.perfil_tecnico.save()
        self.tecnico_n2_b.perfil_tecnico.nivel_atendimento = Categoria.NivelAtendimento.N2
        self.tecnico_n2_b.perfil_tecnico.save()

    def test_notifica_so_tecnicos_do_nivel(self):
        notificar_tecnicos_nivel(self.ticket, Categoria.NivelAtendimento.N2, "Chamado escalado")
        destinatarios = set(
            Notificacao.objects.filter(ticket=self.ticket).values_list("destinatario__username", flat=True)
        )
        self.assertEqual(destinatarios, {"tecnico_n2_a_teste", "tecnico_n2_b_teste"})

    def test_exclui_autor_informado(self):
        notificar_tecnicos_nivel(
            self.ticket, Categoria.NivelAtendimento.N2, "Chamado escalado", excluir=self.tecnico_n2_a,
        )
        destinatarios = set(
            Notificacao.objects.filter(ticket=self.ticket).values_list("destinatario__username", flat=True)
        )
        self.assertEqual(destinatarios, {"tecnico_n2_b_teste"})

    def test_tecnico_inativo_nao_recebe(self):
        self.tecnico_n2_a.is_active = False
        self.tecnico_n2_a.save()
        notificar_tecnicos_nivel(self.ticket, Categoria.NivelAtendimento.N2, "Chamado escalado")
        destinatarios = set(
            Notificacao.objects.filter(ticket=self.ticket).values_list("destinatario__username", flat=True)
        )
        self.assertEqual(destinatarios, {"tecnico_n2_b_teste"})


class EscalarTicketNotificaTecnicosDoNivelTests(TestCase):
    def setUp(self):
        self.tecnico_autor = get_user_model().objects.create_user(
            username="tecnico_autor_escalonamento", is_staff=True,
        )
        self.tecnico_n2 = get_user_model().objects.create_user(
            username="tecnico_n2_destino_escalonamento", is_staff=True,
        )
        self.tecnico_n2.perfil_tecnico.nivel_atendimento = Categoria.NivelAtendimento.N2
        self.tecnico_n2.perfil_tecnico.save()
        self.setor = Setor.objects.create(nome="Setor teste escalar notifica", peso_setor=3)
        self.categoria = Categoria.objects.create(
            nome="Categoria teste escalar notifica", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )

    def test_escalar_notifica_tecnicos_do_novo_nivel(self):
        escalar_ticket(self.ticket, autor=self.tecnico_autor, novo_nivel=Categoria.NivelAtendimento.N2)
        self.assertTrue(
            Notificacao.objects.filter(
                ticket=self.ticket, destinatario=self.tecnico_n2, tipo=Notificacao.Tipo.ESCALONAMENTO,
            ).exists()
        )

    def test_escalar_nao_notifica_o_proprio_autor(self):
        self.tecnico_autor.perfil_tecnico.nivel_atendimento = Categoria.NivelAtendimento.N2
        self.tecnico_autor.perfil_tecnico.save()
        escalar_ticket(self.ticket, autor=self.tecnico_autor, novo_nivel=Categoria.NivelAtendimento.N2)
        self.assertFalse(
            Notificacao.objects.filter(ticket=self.ticket, destinatario=self.tecnico_autor).exists()
        )


class PerfilViewNivelTecnicoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_perfil_view", is_staff=True, password="senha-teste-123",
        )
        self.tecnico.perfil_tecnico.nivel_atendimento = Categoria.NivelAtendimento.N2
        self.tecnico.perfil_tecnico.save()
        self.solicitante = get_user_model().objects.create_user(
            username="solicitante_teste_perfil_view", password="senha-teste-123",
        )
        self.client.login(username="tecnico_teste_perfil_view", password="senha-teste-123")

    def test_perfil_do_tecnico_mostra_nivel(self):
        resposta = self.client.get(reverse("tickets:perfil", args=["tecnico_teste_perfil_view"]))
        self.assertEqual(resposta.context["nivel_tecnico"].nivel_atendimento, "n2")
        self.assertContains(resposta, "N2")

    def test_perfil_de_usuario_comum_nao_mostra_nivel(self):
        resposta = self.client.get(reverse("tickets:perfil", args=["solicitante_teste_perfil_view"]))
        self.assertIsNone(resposta.context["nivel_tecnico"])
