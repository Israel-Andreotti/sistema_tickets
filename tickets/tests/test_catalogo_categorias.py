from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.forms import AbrirTicketForm, ConfirmarClassificacaoForm
from tickets.models import Categoria, Setor, Ticket
from tickets.services.classificacao import abrir_ticket, atribuir_tecnico


class CategoriaAtivaTests(TestCase):
    """Categorias inativas (Categoria.ativo=False) somem da abertura de
    chamado, mas continuam selecionáveis quando já é a categoria em uso por
    um ticket existente — ver forms.py: _categorias_agrupadas/_categorias_meta,
    AbrirTicketForm, ConfirmarClassificacaoForm."""

    def setUp(self):
        self.setor = Setor.objects.create(nome="Setor teste catalogo", peso_setor=3)
        self.categoria_ativa = Categoria.objects.create(
            nome="Categoria ativa teste", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.categoria_inativa = Categoria.objects.create(
            nome="Categoria inativa teste", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8, ativo=False,
        )
        self.usuario = get_user_model().objects.create_user(
            username="usuario_teste_catalogo", password="senha-teste-123",
        )

    def test_categoria_inativa_nao_aparece_no_form_de_abertura(self):
        form = AbrirTicketForm()
        self.assertIn(self.categoria_ativa, form.fields["categoria_sugerida"].queryset)
        self.assertNotIn(self.categoria_inativa, form.fields["categoria_sugerida"].queryset)

    def test_categoria_inativa_nao_aparece_na_tela_de_abrir_chamado(self):
        self.client.login(username="usuario_teste_catalogo", password="senha-teste-123")
        resposta = self.client.get(reverse("tickets:abrir_ticket"))
        self.assertContains(resposta, "Categoria ativa teste")
        self.assertNotContains(resposta, "Categoria inativa teste")

    def test_categoria_inativa_nao_pode_ser_escolhida_na_abertura(self):
        self.client.login(username="usuario_teste_catalogo", password="senha-teste-123")
        resposta = self.client.post(reverse("tickets:abrir_ticket"), {
            "categoria_sugerida": self.categoria_inativa.pk,
            "grupo": Categoria.Grupo.SUPORTE,
            "setor": self.setor.pk,
            "impacto": Ticket.Impacto.APENAS_EU,
            "descricao": "Descrição de teste",
            "solicitante_ramal": "123",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Ticket.objects.exists())

    def test_categoria_atual_do_ticket_continua_selecionavel_mesmo_inativa(self):
        """Um ticket já classificado com uma categoria que depois virou
        inativa precisa continuar podendo ser reconfirmado com ela — senão
        o form rejeitaria a própria categoria que o ticket já usa."""
        ticket = abrir_ticket(
            categoria_sugerida=self.categoria_inativa, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        form = ConfirmarClassificacaoForm(
            {"categoria_final": self.categoria_inativa.pk},
            categoria_atual_id=self.categoria_inativa.pk,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["categoria_final"], self.categoria_inativa)

    def test_tecnico_consegue_reconfirmar_categoria_inativa_ja_em_uso(self):
        tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_catalogo", is_staff=True, password="senha-teste-123",
        )
        ticket = abrir_ticket(
            categoria_sugerida=self.categoria_inativa, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(ticket, tecnico)
        self.client.login(username="tecnico_teste_catalogo", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:classificar_ticket", args=[ticket.pk]),
            {"categoria_final": self.categoria_inativa.pk},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.categoria_final, self.categoria_inativa)

    def test_outra_categoria_inativa_nao_pode_ser_escolhida_na_classificacao(self):
        """A categoria inativa A JÁ EM USO continua selecionável, mas uma
        OUTRA categoria inativa qualquer não pode virar a nova classificação."""
        outra_inativa = Categoria.objects.create(
            nome="Outra categoria inativa teste", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8, ativo=False,
        )
        tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_catalogo2", is_staff=True, password="senha-teste-123",
        )
        ticket = abrir_ticket(
            categoria_sugerida=self.categoria_ativa, setor=self.setor, descricao="Descrição teste",
            solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="Sala 1",
        )
        atribuir_tecnico(ticket, tecnico)
        self.client.login(username="tecnico_teste_catalogo2", password="senha-teste-123")
        resposta = self.client.post(
            reverse("tickets:classificar_ticket", args=[ticket.pk]),
            {"categoria_final": outra_inativa.pk},
        )
        self.assertRedirects(resposta, reverse("tickets:detalhe_ticket", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertIsNone(ticket.categoria_final)
