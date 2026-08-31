from django.db import migrations

PARAMETROS = [
    # (chave, valor, descricao)
    (
        "fator_prioridade_incidente",
        "1.0",
        "Multiplicador aplicado a peso_categoria x peso_setor quando a "
        "categoria é do tipo Incidente, na ausência de ExcecaoPrioridade",
    ),
    (
        "fator_prioridade_requisicao",
        "1.0",
        "Multiplicador aplicado a peso_categoria x peso_setor quando a "
        "categoria é do tipo Requisição, na ausência de ExcecaoPrioridade",
    ),
]


def seed_fatores(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    for chave, valor, descricao in PARAMETROS:
        ParametroSistema.objects.get_or_create(
            chave=chave, defaults={"valor": valor, "descricao": descricao}
        )


def remove_fatores(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    ParametroSistema.objects.filter(chave__in=[p[0] for p in PARAMETROS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0034_categoria_tipo"),
    ]

    operations = [
        migrations.RunPython(seed_fatores, remove_fatores),
    ]
