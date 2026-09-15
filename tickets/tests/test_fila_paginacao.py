"""A fila (visão em lista) crescia indefinidamente na mesma página — só o
kanban tinha colunas que "limitavam" visualmente o tanto de cartão por vez.
Agora a tabela pagina (50 por página); o kanban continua mostrando as
colunas inteiras, que já são naturalmente mais curtas."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Categoria, Setor
from tickets.services.classificacao import abrir_ticket


class PaginacaoDaFilaTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username="tecnico_teste_paginacao_fila", is_staff=True, password="senha-teste-123",
        )
        self.categoria = Categoria.objects.create(
            nome="Categoria teste paginacao fila", grupo=Categoria.Grupo.SUPORTE,
            peso_categoria=2, sla_horas=8,
        )
        self.setor = Setor.objects.create(nome="Setor teste paginacao fila", peso_setor=3)
        for i in range(55):
            abrir_ticket(
                categoria_sugerida=self.categoria, setor=self.setor, descricao=f"Chamado {i}",
                solicitante_nome="Fulano", solicitante_ramal="1", solicitante_sala="",
            )
        self.client.login(username="tecnico_teste_paginacao_fila", password="senha-teste-123")

    def test_primeira_pagina_tem_50_e_avisa_que_ha_mais(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        self.assertEqual(len(resposta.context["pagina"].object_list), 50)
        self.assertTrue(resposta.context["pagina"].has_next())
        self.assertContains(resposta, "Página 1 de 2")

    def test_segunda_pagina_tem_o_restante(self):
        resposta = self.client.get(reverse("tickets:fila_tickets"), {"pagina": 2})
        self.assertEqual(len(resposta.context["pagina"].object_list), 5)
        self.assertFalse(resposta.context["pagina"].has_next())

    def test_kanban_continua_mostrando_todos_os_chamados_independente_da_pagina(self):
        """tickets_por_status (kanban) não é afetado pela paginação da tabela."""
        resposta = self.client.get(reverse("tickets:fila_tickets"))
        total_no_kanban = sum(len(v) for v in resposta.context["tickets_por_status"].values())
        self.assertEqual(total_no_kanban, 55)
