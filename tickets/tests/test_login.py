from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ManterConectadoTests(TestCase):
    """"Manter conectado" desmarcado expira a sessão ao fechar o navegador
    (session_expiry == 0); marcado, mantém a duração padrão do Django."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuario_teste_login", password="senha-teste-123",
        )

    def test_sem_manter_conectado_expira_ao_fechar_navegador(self):
        self.client.post(reverse("login"), {
            "username": "usuario_teste_login", "password": "senha-teste-123",
        })
        self.assertEqual(self.client.session.get_expire_at_browser_close(), True)

    def test_com_manter_conectado_nao_expira_ao_fechar_navegador(self):
        self.client.post(reverse("login"), {
            "username": "usuario_teste_login", "password": "senha-teste-123",
            "manter_conectado": "on",
        })
        self.assertEqual(self.client.session.get_expire_at_browser_close(), False)

    def test_login_invalido_nao_autentica(self):
        resposta = self.client.post(reverse("login"), {
            "username": "usuario_teste_login", "password": "senha-errada",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context["user"].is_authenticated)
