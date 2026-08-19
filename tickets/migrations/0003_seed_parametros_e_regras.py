from django.db import migrations

PARAMETROS = [
    # (chave, valor, descricao)
    (
        "desvio_atencao_pct",
        "20",
        "Percentual de estouro médio de SLA (categoria+setor) que caracteriza desvio leve (atenção)",
    ),
    (
        "desvio_critico_pct",
        "50",
        "Percentual de estouro médio de SLA (categoria+setor) que caracteriza desvio crítico",
    ),
    (
        "janela_recomendacao_dias",
        "30",
        "Janela de tempo (dias) usada para agregar desvios de SLA por categoria+setor",
    ),
    (
        "min_tickets_para_recomendacao",
        "5",
        "Número mínimo de tickets fechados no período para uma agregação virar recomendação",
    ),
]

REGRAS = [
    # (tipo_desvio, condicao, acao_sugerida)
    (
        "atencao",
        "% médio de estouro de SLA entre desvio_atencao_pct e desvio_critico_pct "
        "para a combinação categoria+setor, com pelo menos min_tickets_para_recomendacao "
        "tickets fechados na janela_recomendacao_dias",
        "Monitorar a combinação categoria/setor e avaliar reforço pontual de equipe "
        "ou peças de reposição.",
    ),
    (
        "critico",
        "% médio de estouro de SLA acima de desvio_critico_pct para a combinação "
        "categoria+setor, com pelo menos min_tickets_para_recomendacao tickets "
        "fechados na janela_recomendacao_dias",
        "Abrir revisão formal do processo de atendimento para essa combinação "
        "categoria/setor: considerar técnico dedicado, revisão de estoque de peças "
        "ou renegociação do SLA.",
    ),
]


def seed_parametros_e_regras(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    RegraRecomendacao = apps.get_model("tickets", "RegraRecomendacao")

    for chave, valor, descricao in PARAMETROS:
        ParametroSistema.objects.get_or_create(
            chave=chave, defaults={"valor": valor, "descricao": descricao}
        )

    for tipo_desvio, condicao, acao_sugerida in REGRAS:
        RegraRecomendacao.objects.get_or_create(
            tipo_desvio=tipo_desvio,
            defaults={"condicao": condicao, "acao_sugerida": acao_sugerida},
        )


def remove_parametros_e_regras(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    RegraRecomendacao = apps.get_model("tickets", "RegraRecomendacao")

    ParametroSistema.objects.filter(chave__in=[p[0] for p in PARAMETROS]).delete()
    RegraRecomendacao.objects.filter(tipo_desvio__in=[r[0] for r in REGRAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0002_seed_catalogo"),
    ]

    operations = [
        migrations.RunPython(seed_parametros_e_regras, remove_parametros_e_regras),
    ]
