from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.portal_view, name="portal"),
    path("abrir/", views.abrir_ticket_view, name="abrir_ticket"),
    path("perfil/<str:username>/", views.perfil_view, name="perfil"),
    path("meus/", views.meus_tickets_view, name="meus_tickets"),
    path("meus/<int:pk>/", views.meu_ticket_detalhe_view, name="meu_ticket_detalhe"),
    path("notificacoes/", views.notificacoes_view, name="notificacoes"),
    path("notificacoes/dropdown/", views.notificacoes_dropdown_view, name="notificacoes_dropdown"),
    path("notificacoes/novas/", views.notificacoes_novas_view, name="notificacoes_novas"),
    path("notificacoes/<int:pk>/lida/", views.marcar_notificacao_lida_view, name="marcar_notificacao_lida"),
    path(
        "notificacoes/marcar-todas/",
        views.marcar_todas_notificacoes_lidas_view,
        name="marcar_todas_notificacoes_lidas",
    ),
    path("tecnico/", views.fila_tickets_view, name="fila_tickets"),
    path("tecnico/dashboard/", views.dashboard_view, name="dashboard"),
    path("tecnico/novos/", views.fila_tickets_novos_view, name="fila_tickets_novos"),
    path("tecnico/historico/", views.historico_tickets_view, name="historico_tickets"),
    path("sla/", views.sla_por_categoria_view, name="sla_por_categoria"),
    path("equipamentos/", views.listar_equipamentos_view, name="listar_equipamentos"),
    path("equipamentos/novo/", views.cadastrar_equipamento_view, name="cadastrar_equipamento"),
    path("equipamentos/consultar/", views.consultar_equipamento_view, name="consultar_equipamento"),
    path("equipamentos/<int:pk>/editar/", views.editar_equipamento_view, name="editar_equipamento"),
    path("tecnico/<int:pk>/", views.detalhe_ticket_view, name="detalhe_ticket"),
    path("tecnico/<int:pk>/classificar/", views.classificar_ticket_view, name="classificar_ticket"),
    path("tecnico/<int:pk>/atribuir/", views.atribuir_tecnico_view, name="atribuir_tecnico"),
    path("tecnico/<int:pk>/fechar/", views.fechar_ticket_view, name="fechar_ticket"),
    path(
        "tecnico/<int:pk>/movimentar-equipamento/",
        views.movimentar_equipamento_view,
        name="movimentar_equipamento",
    ),
    path("tecnico/<int:pk>/comentar/", views.adicionar_comentario_view, name="adicionar_comentario"),
    path("base-conhecimento/", views.listar_artigos_view, name="listar_artigos"),
    path("base-conhecimento/sugestoes/", views.sugestoes_artigos_view, name="sugestoes_artigos"),
    path("base-conhecimento/novo/", views.criar_artigo_view, name="criar_artigo"),
    path("base-conhecimento/<int:pk>/", views.detalhe_artigo_view, name="detalhe_artigo"),
    path("base-conhecimento/<int:pk>/editar/", views.editar_artigo_view, name="editar_artigo"),
]
