"""Feedback 👍/👎 em artigo da base de conhecimento sugerido durante a
abertura de chamado — mede se a base evitou a abertura. Um usuário tem no
máximo um feedback por artigo; votar de novo atualiza o voto anterior."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import ArtigoConhecimento, FeedbackArtigoConhecimento
from tickets.services.artigos import registrar_feedback_artigo


class RegistrarFeedbackArtigoServiceTests(TestCase):
    def setUp(self):
        self.autor = get_user_model().objects.create_user(username="autor_teste_feedback", is_staff=True)
        self.usuario = get_user_model().objects.create_user(username="solicitante_teste_feedback")
        self.artigo = ArtigoConhecimento.objects.create(
            titulo="Artigo teste feedback", conteudo="Conteúdo", autor=self.autor,
        )

    def test_cria_feedback_novo(self):
        registrar_feedback_artigo(self.artigo, self.usuario, util=True)
        feedback = FeedbackArtigoConhecimento.objects.get(artigo=self.artigo, usuario=self.usuario)
        self.assertTrue(feedback.util)

    def test_votar_de_novo_atualiza_em_vez_de_duplicar(self):
        registrar_feedback_artigo(self.artigo, self.usuario, util=True)
        registrar_feedback_artigo(self.artigo, self.usuario, util=False)

        self.assertEqual(
            FeedbackArtigoConhecimento.objects.filter(artigo=self.artigo, usuario=self.usuario).count(), 1,
        )
        feedback = FeedbackArtigoConhecimento.objects.get(artigo=self.artigo, usuario=self.usuario)
        self.assertFalse(feedback.util)


class FeedbackArtigoViewTests(TestCase):
    def setUp(self):
        self.autor = get_user_model().objects.create_user(username="autor_teste_feedback_view", is_staff=True)
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_teste_feedback_view", password="senha-teste-123",
        )
        self.artigo = ArtigoConhecimento.objects.create(
            titulo="Artigo teste feedback view", conteudo="Conteúdo", autor=self.autor,
        )
        self.client.login(username="solicitante_teste_feedback_view", password="senha-teste-123")

    def test_feedback_positivo_e_salvo(self):
        resposta = self.client.post(
            reverse("tickets:feedback_artigo", args=[self.artigo.pk]),
            data=json.dumps({"util": True}), content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            FeedbackArtigoConhecimento.objects.get(artigo=self.artigo, usuario=self.usuario).util
        )

    def test_corpo_invalido_retorna_400(self):
        resposta = self.client.post(
            reverse("tickets:feedback_artigo", args=[self.artigo.pk]),
            data=json.dumps({"util": "sim"}), content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(FeedbackArtigoConhecimento.objects.exists())

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.post(
            reverse("tickets:feedback_artigo", args=[self.artigo.pk]),
            data=json.dumps({"util": True}), content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 302)

    def test_metodo_get_nao_e_permitido(self):
        resposta = self.client.get(reverse("tickets:feedback_artigo", args=[self.artigo.pk]))
        self.assertEqual(resposta.status_code, 405)


class FeedbackNaPaginaDoArtigoTests(TestCase):
    """Regressão: o feedback só existia no card pequeno de sugestão, na tela
    de abrir chamado — o link abre o artigo numa aba nova (target=_blank),
    deixando o card (e o feedback) fora de vista. Agora o mesmo controle
    também aparece na página do artigo, mas só quando a pessoa chegou lá por
    uma sugestão (?de_sugestao=1), não navegando livre pela base."""

    def setUp(self):
        self.autor = get_user_model().objects.create_user(username="autor_teste_feedback_pagina", is_staff=True)
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_teste_feedback_pagina", password="senha-teste-123",
        )
        self.artigo = ArtigoConhecimento.objects.create(
            titulo="Artigo teste feedback na pagina", conteudo="Conteúdo", autor=self.autor,
        )
        self.client.login(username="solicitante_teste_feedback_pagina", password="senha-teste-123")

    def _abrir_artigo(self, de_sugestao=False):
        params = {"de_sugestao": "1"} if de_sugestao else {}
        return self.client.get(reverse("tickets:detalhe_artigo", args=[self.artigo.pk]), params)

    def test_bloco_de_feedback_aparece_quando_vem_de_sugestao(self):
        resposta = self._abrir_artigo(de_sugestao=True)
        self.assertContains(resposta, "Este artigo ajudou a resolver seu problema?")

    def test_bloco_de_feedback_nao_aparece_navegando_livre(self):
        resposta = self._abrir_artigo(de_sugestao=False)
        self.assertNotContains(resposta, "Este artigo ajudou a resolver seu problema?")

    def test_ja_tendo_votado_mostra_confirmacao_direto(self):
        registrar_feedback_artigo(self.artigo, self.usuario, util=True)
        resposta = self._abrir_artigo(de_sugestao=True)
        self.assertContains(resposta, "Obrigado! Você disse que este artigo")
        self.assertNotContains(resposta, "Este artigo ajudou a resolver seu problema?")


class SugestoesArtigosIncluiIdTests(TestCase):
    """A sugestão precisa do id do artigo pra saber em qual artigo o
    feedback (👍/👎) vai ser registrado."""

    def setUp(self):
        autor = get_user_model().objects.create_user(username="autor_teste_sugestao_id", is_staff=True)
        self.artigo = ArtigoConhecimento.objects.create(
            titulo="Como resolver problema de internação",
            conteudo="Passo a passo detalhado sobre internação",
            autor=autor,
        )
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_teste_sugestao_id", password="senha-teste-123",
        )
        self.client.login(username="solicitante_teste_sugestao_id", password="senha-teste-123")

    def test_resposta_inclui_id_do_artigo(self):
        resposta = self.client.get(
            reverse("tickets:sugestoes_artigos"), {"q": "problema de internação"},
        )
        dados = resposta.json()
        self.assertEqual(len(dados["artigos"]), 1)
        self.assertEqual(dados["artigos"][0]["id"], self.artigo.pk)
