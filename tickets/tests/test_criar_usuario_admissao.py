from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.forms import CriarUsuarioAdmissaoForm
from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket, atribuir_tecnico
from tickets.services.usuarios import criar_usuario_admissao


class CriarUsuarioAdmissaoServiceTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(
            nome="Criação de usuário teste", grupo=Categoria.Grupo.ACESSO,
            peso_categoria=2, sla_horas=24, habilita_criacao_usuario=True,
        )
        self.setor = Setor.objects.create(nome="Setor teste criar usuario", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )

    def test_cria_usuario_e_vincula_ao_ticket(self):
        usuario = criar_usuario_admissao(
            self.ticket, first_name="Maria", last_name="Silva",
            username="maria.silva", email="maria.silva@hospital.local",
        )
        self.assertEqual(usuario.first_name, "Maria")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.has_usable_password())
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.usuario_criado, usuario)

    def test_rejeita_criar_dois_usuarios_pro_mesmo_chamado(self):
        criar_usuario_admissao(
            self.ticket, first_name="Maria", last_name="Silva",
            username="maria.silva2", email="maria.silva2@hospital.local",
        )
        with self.assertRaises(ValueError):
            criar_usuario_admissao(
                self.ticket, first_name="Outra", last_name="Pessoa",
                username="outra.pessoa", email="outra@hospital.local",
            )


class CriarUsuarioAdmissaoFormTests(TestCase):
    def test_rejeita_username_duplicado(self):
        get_user_model().objects.create_user(username="ja.existe")
        form = CriarUsuarioAdmissaoForm({
            "first_name": "Maria", "last_name": "Silva",
            "username": "ja.existe", "email": "maria@hospital.local",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)


class CriarUsuarioAdmissaoViewTests(TestCase):
    def setUp(self):
        self.tecnico_a = get_user_model().objects.create_user(
            username="tecnico_a_criar_usuario", is_staff=True, password="senha-teste-123",
        )
        self.tecnico_b = get_user_model().objects.create_user(
            username="tecnico_b_criar_usuario", is_staff=True, password="senha-teste-123",
        )
        self.categoria_habilitada = Categoria.objects.create(
            nome="Criação de usuário teste view", grupo=Categoria.Grupo.ACESSO,
            peso_categoria=2, sla_horas=24, habilita_criacao_usuario=True,
        )
        self.categoria_comum = Categoria.objects.create(
            nome="Categoria comum teste view", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=24,
        )
        self.setor = Setor.objects.create(nome="Setor teste criar usuario view", peso_setor=3)
        self.ticket = abrir_ticket(
            categoria_sugerida=self.categoria_habilitada, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(self.ticket, self.tecnico_a)

    def _post(self, **overrides):
        dados = {
            "first_name": "Maria", "last_name": "Silva",
            "username": "maria.silva.view", "email": "maria.silva.view@hospital.local",
        }
        dados.update(overrides)
        return self.client.post(reverse("tickets:criar_usuario_admissao", args=[self.ticket.pk]), dados)

    def test_tecnico_responsavel_cria_usuario(self):
        self.client.login(username="tecnico_a_criar_usuario", password="senha-teste-123")
        resposta = self._post()
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.usuario_criado)
        self.assertEqual(self.ticket.usuario_criado.username, "maria.silva.view")

    def test_tecnico_nao_responsavel_nao_consegue(self):
        self.client.login(username="tecnico_b_criar_usuario", password="senha-teste-123")
        resposta = self._post()
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.usuario_criado)

    def test_nao_funciona_quando_categoria_nao_habilita(self):
        self.ticket.categoria_sugerida = self.categoria_comum
        self.ticket.save(update_fields=["categoria_sugerida"])
        self.client.login(username="tecnico_a_criar_usuario", password="senha-teste-123")
        resposta = self._post()
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.usuario_criado)

    def test_card_aparece_na_tela_do_chamado(self):
        self.client.login(username="tecnico_a_criar_usuario", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertContains(resposta, "Criação de usuário")
        self.assertContains(resposta, 'name="username"')

    def test_card_nao_aparece_pra_categoria_comum(self):
        self.ticket.categoria_sugerida = self.categoria_comum
        self.ticket.save(update_fields=["categoria_sugerida"])
        self.client.login(username="tecnico_a_criar_usuario", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:detalhe_ticket", args=[self.ticket.pk]))
        self.assertNotContains(resposta, 'name="username"')
