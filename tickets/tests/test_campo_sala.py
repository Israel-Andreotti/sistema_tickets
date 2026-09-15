"""Campo "Sala" na abertura de chamado: existia no model (Ticket.solicitante_sala)
mas a view sempre gravava "" e o formulário nem o expunha — o bloco condicional
em detalhe_ticket.html nunca aparecia na prática. Agora é opcional no
formulário e vai pro chamado quando preenchido."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor, Ticket


class CampoSalaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="solicitante_teste_sala", password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste sala", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste sala", peso_setor=3)
        self.client.login(username="solicitante_teste_sala", password="senha-teste-123")

    def _abrir(self, **extra):
        dados = {
            "categoria_sugerida": self.categoria.pk,
            "grupo": self.categoria.grupo,
            "setor": self.setor.pk,
            "impacto": Ticket.Impacto.APENAS_EU,
            "descricao": "Descrição de teste com sala",
            "solicitante_ramal": "123",
        }
        dados.update(extra)
        return self.client.post(reverse("tickets:abrir_ticket"), dados)

    def test_sala_preenchida_e_salva_no_ticket(self):
        self._abrir(solicitante_sala="204")
        ticket = Ticket.objects.get(descricao="Descrição de teste com sala")
        self.assertEqual(ticket.solicitante_sala, "204")

    def test_sala_em_branco_e_opcional(self):
        resposta = self._abrir(solicitante_sala="")
        self.assertEqual(resposta.status_code, 302)
        ticket = Ticket.objects.get(descricao="Descrição de teste com sala")
        self.assertEqual(ticket.solicitante_sala, "")

    def test_sala_aparece_no_detalhe_do_ticket_quando_preenchida(self):
        self._abrir(solicitante_sala="Ala B, sala 12")
        ticket = Ticket.objects.get(descricao="Descrição de teste com sala")
        resposta = self.client.get(reverse("tickets:meu_ticket_detalhe", args=[ticket.pk]))
        self.assertContains(resposta, "Ala B, sala 12")
