from django.contrib.auth import get_user_model
from django.test import TestCase, modify_settings, override_settings
from django.urls import reverse

# django-debug-toolbar decide se injeta o painel olhando settings.DEBUG em
# tempo de requisição, mas suas URLs (__debug__/) só entram no urlconf se
# DEBUG já era True quando o Django carregou config/urls.py — como o test
# runner força DEBUG=False nesse momento, usar override_settings(DEBUG=True)
# sozinho faz o middleware tentar renderizar um painel cujas URLs não
# existem. Remove o middleware nesses testes pra evitar esse descompasso.
_SEM_DEBUG_TOOLBAR = modify_settings(
    MIDDLEWARE={"remove": ["debug_toolbar.middleware.DebugToolbarMiddleware"]}
)


class PreviewPaginasErroTests(TestCase):
    """As views de preview-erro/* só respondem com DEBUG=True (config/views.py)
    — servem pra visualizar 403.html/500.html sem precisar provocar o erro de
    verdade (o Django só troca pelo template customizado com DEBUG=False).
    O test runner do Django força DEBUG=False durante os testes, então cada
    caso liga/desliga explicitamente com override_settings."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuario_teste_preview_erro", password="senha-teste-123",
        )
        self.client.login(username="usuario_teste_preview_erro", password="senha-teste-123")

    @override_settings(DEBUG=True)
    @_SEM_DEBUG_TOOLBAR
    def test_preview_403_renderiza_com_status_403(self):
        resposta = self.client.get(reverse("preview_erro_403"))
        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, "Você não tem permissão", status_code=403)

    @override_settings(DEBUG=True)
    @_SEM_DEBUG_TOOLBAR
    def test_preview_500_renderiza_com_status_500(self):
        resposta = self.client.get(reverse("preview_erro_500"))
        self.assertEqual(resposta.status_code, 500)
        self.assertContains(resposta, "Não foi possível processar", status_code=500)

    def test_preview_403_da_404_sem_debug(self):
        resposta = self.client.get(reverse("preview_erro_403"))
        self.assertEqual(resposta.status_code, 404)

    def test_preview_500_da_404_sem_debug(self):
        resposta = self.client.get(reverse("preview_erro_500"))
        self.assertEqual(resposta.status_code, 404)


class PortalMostraLinksDePreviewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuario_teste_portal_preview", password="senha-teste-123",
        )
        self.client.login(username="usuario_teste_portal_preview", password="senha-teste-123")

    @override_settings(DEBUG=True)
    @_SEM_DEBUG_TOOLBAR
    def test_portal_mostra_pep_e_pms_como_links_quando_debug(self):
        resposta = self.client.get(reverse("tickets:portal"))
        self.assertContains(resposta, reverse("preview_erro_403"))
        self.assertContains(resposta, reverse("preview_erro_500"))

    def test_portal_mostra_pep_e_pms_desabilitados_sem_debug(self):
        resposta = self.client.get(reverse("tickets:portal"))
        self.assertContains(resposta, "Prontuário Eletrônico do Paciente")
        self.assertContains(resposta, "Portal do Ministério da Saúde")
