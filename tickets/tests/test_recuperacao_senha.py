from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tickets.models import CodigoRecuperacaoSenha
from tickets.services.recuperacao_senha import solicitar_codigo, validar_codigo


class SolicitarCodigoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_teste_recuperacao", email="solicitante@teste.com",
        )

    def test_gera_codigo_de_6_digitos_e_envia_email(self):
        registro = solicitar_codigo(self.usuario)

        self.assertEqual(len(registro.codigo), 6)
        self.assertTrue(registro.codigo.isdigit())
        self.assertIsNone(registro.usado_em)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(registro.codigo, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["solicitante@teste.com"])

    def test_levanta_erro_sem_email_cadastrado(self):
        usuario_sem_email = get_user_model().objects.create_user(username="sem_email_teste_recuperacao")

        with self.assertRaises(ValueError):
            solicitar_codigo(usuario_sem_email)
        self.assertEqual(len(mail.outbox), 0)

    def test_novo_codigo_invalida_codigo_anterior_em_aberto(self):
        primeiro = solicitar_codigo(self.usuario)
        solicitar_codigo(self.usuario)

        self.assertFalse(validar_codigo(self.usuario, primeiro.codigo))


class ValidarCodigoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="tecnico_teste_recuperacao", email="tecnico@teste.com",
        )

    def test_codigo_correto_e_valido_uma_unica_vez(self):
        registro = solicitar_codigo(self.usuario)

        self.assertTrue(validar_codigo(self.usuario, registro.codigo))
        self.assertFalse(validar_codigo(self.usuario, registro.codigo))

    def test_codigo_incorreto_e_invalido(self):
        solicitar_codigo(self.usuario)

        self.assertFalse(validar_codigo(self.usuario, "000000"))

    def test_codigo_expirado_e_invalido(self):
        registro = solicitar_codigo(self.usuario)
        CodigoRecuperacaoSenha.objects.filter(pk=registro.pk).update(
            expira_em=timezone.now() - timedelta(minutes=1)
        )

        self.assertFalse(validar_codigo(self.usuario, registro.codigo))


class FluxoEsqueciSenhaViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuario_teste_fluxo_recuperacao",
            email="fluxo@teste.com",
            password="senha_antiga_123",
        )

    def test_username_inexistente_nao_envia_email(self):
        resposta = self.client.post(reverse("esqueci_senha"), {"username": "nao_existe_ninguem"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(resposta, "Não foi possível enviar um código")

    def test_usuario_sem_email_mostra_erro(self):
        get_user_model().objects.create_user(username="sem_email_fluxo_recuperacao")

        resposta = self.client.post(reverse("esqueci_senha"), {"username": "sem_email_fluxo_recuperacao"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        # Mesma mensagem do teste acima (username inexistente): as duas falhas
        # não podem ser diferenciadas pelo texto, senão dá pra descobrir que
        # usernames existem só tentando "esqueci minha senha".
        self.assertContains(resposta, "Não foi possível enviar um código")

    def test_username_valido_envia_codigo_e_redireciona(self):
        resposta = self.client.post(
            reverse("esqueci_senha"), {"username": "usuario_teste_fluxo_recuperacao"}
        )

        self.assertRedirects(resposta, reverse("confirmar_codigo"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.session["recuperacao_usuario_id"], self.usuario.pk)

    def test_fluxo_completo_ate_definir_nova_senha(self):
        self.client.post(reverse("esqueci_senha"), {"username": "usuario_teste_fluxo_recuperacao"})
        codigo = CodigoRecuperacaoSenha.objects.get(usuario=self.usuario).codigo

        resposta = self.client.post(reverse("confirmar_codigo"), {"codigo": codigo})
        self.assertRedirects(resposta, reverse("definir_nova_senha"))
        self.assertTrue(self.client.session["pode_definir_nova_senha"])

        resposta = self.client.post(reverse("definir_nova_senha"), {
            "new_password1": "senha_nova_98765",
            "new_password2": "senha_nova_98765",
        })
        self.assertRedirects(resposta, reverse("tickets:portal"))

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("senha_nova_98765"))
        self.assertNotIn("pode_definir_nova_senha", self.client.session)

    def test_confirmar_codigo_sem_solicitacao_previa_redireciona(self):
        resposta = self.client.post(reverse("confirmar_codigo"), {"codigo": "123456"})

        self.assertRedirects(resposta, reverse("esqueci_senha"))

    def test_codigo_incorreto_nao_autentica(self):
        self.client.post(reverse("esqueci_senha"), {"username": "usuario_teste_fluxo_recuperacao"})

        resposta = self.client.post(reverse("confirmar_codigo"), {"codigo": "000000"})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Código inválido ou expirado.")
        self.assertNotIn("pode_definir_nova_senha", self.client.session)

    def test_definir_nova_senha_exige_flag_de_sessao(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("definir_nova_senha"))

        self.assertRedirects(
            resposta, reverse("tickets:perfil", kwargs={"username": self.usuario.username})
        )
