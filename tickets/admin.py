from django.contrib import admin

from .models import (
    ArtigoConhecimento,
    Categoria,
    ComentarioTicket,
    ExcecaoPrioridade,
    HistoricoSLA,
    ItemConfiguracao,
    MovimentacaoEquipamento,
    ParametroSistema,
    Recomendacao,
    RegraRecomendacao,
    Setor,
    Ticket,
)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "peso_setor", "gestor")
    list_editable = ("peso_setor",)
    search_fields = ("nome",)
    autocomplete_fields = ("gestor",)
    ordering = ("nome",)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "grupo", "peso_categoria", "sla_horas", "requer_patrimonio")
    list_editable = ("peso_categoria", "sla_horas", "requer_patrimonio")
    list_filter = ("grupo", "requer_patrimonio")
    search_fields = ("nome",)
    ordering = ("grupo", "nome")


@admin.register(ExcecaoPrioridade)
class ExcecaoPrioridadeAdmin(admin.ModelAdmin):
    list_display = ("categoria", "setor", "peso_override")
    list_editable = ("peso_override",)
    list_filter = ("categoria", "setor")
    autocomplete_fields = ("categoria", "setor")


@admin.register(ItemConfiguracao)
class ItemConfiguracaoAdmin(admin.ModelAdmin):
    list_display = (
        "patrimonio", "categoria", "marca", "modelo", "setor", "status",
        "data_aquisicao", "data_validade_garantia",
    )
    list_editable = ("status",)
    list_filter = ("status", "categoria", "setor")
    search_fields = ("patrimonio", "marca", "modelo")
    autocomplete_fields = ("setor",)


class ComentarioTicketInline(admin.TabularInline):
    model = ComentarioTicket
    extra = 0
    fields = ("autor", "tipo", "texto", "criado_em")
    readonly_fields = ("criado_em",)
    autocomplete_fields = ("autor",)


class MovimentacaoEquipamentoInline(admin.TabularInline):
    model = MovimentacaoEquipamento
    extra = 0
    fields = ("autor", "equipamento_saida", "equipamento_entrada", "sem_movimentacao", "criado_em")
    readonly_fields = ("criado_em",)
    autocomplete_fields = ("autor", "equipamento_saida", "equipamento_entrada")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    inlines = [MovimentacaoEquipamentoInline, ComentarioTicketInline]
    list_display = (
        "id",
        "solicitante_nome",
        "setor",
        "categoria_sugerida",
        "categoria_ia",
        "categoria_final",
        "impacto",
        "status",
        "tecnico_responsavel",
        "movimentacao_confirmada",
        "prioridade_calculada",
        "data_abertura",
    )
    list_filter = ("status", "setor", "categoria_final", "impacto", "movimentacao_confirmada", "tecnico_responsavel")
    search_fields = ("descricao", "solicitante_nome", "solicitante_ramal", "solicitante_sala", "solicitante_ip")
    autocomplete_fields = (
        "categoria_sugerida",
        "categoria_ia",
        "categoria_final",
        "setor",
        "item_configuracao",
        "tecnico_responsavel",
    )
    readonly_fields = ("prioridade_calculada", "data_abertura", "solicitante_ip")


@admin.register(HistoricoSLA)
class HistoricoSLAAdmin(admin.ModelAdmin):
    list_display = ("ticket", "tempo_real", "tempo_esperado", "desvio")
    autocomplete_fields = ("ticket",)


@admin.register(ParametroSistema)
class ParametroSistemaAdmin(admin.ModelAdmin):
    list_display = ("chave", "valor", "descricao")
    list_editable = ("valor",)
    search_fields = ("chave",)


@admin.register(RegraRecomendacao)
class RegraRecomendacaoAdmin(admin.ModelAdmin):
    list_display = ("tipo_desvio", "condicao", "acao_sugerida")
    search_fields = ("tipo_desvio",)


@admin.register(Recomendacao)
class RecomendacaoAdmin(admin.ModelAdmin):
    list_display = ("categoria", "setor", "regra", "data_gerada")
    list_filter = ("categoria", "setor")
    autocomplete_fields = ("categoria", "setor", "regra")
    readonly_fields = ("data_gerada",)


@admin.register(ArtigoConhecimento)
class ArtigoConhecimentoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "autor", "atualizado_em")
    list_filter = ("categoria",)
    search_fields = ("titulo", "resumo", "conteudo")
    autocomplete_fields = ("categoria", "autor")
    readonly_fields = ("criado_em", "atualizado_em")
