from django.db import migrations

# Formato antigo (PAT-000N) -> novo formato (6 dígitos, sem letras).
RENOMEACOES = {
    "PAT-0001": "000001",
    "PAT-0002": "000002",
    "PAT-0003": "000003",
    "PAT-0004": "000004",
}


def renomear(apps, schema_editor):
    ItemConfiguracao = apps.get_model("tickets", "ItemConfiguracao")
    for antigo, novo in RENOMEACOES.items():
        ItemConfiguracao.objects.filter(patrimonio=antigo).update(patrimonio=novo)


def reverter(apps, schema_editor):
    ItemConfiguracao = apps.get_model("tickets", "ItemConfiguracao")
    for antigo, novo in RENOMEACOES.items():
        ItemConfiguracao.objects.filter(patrimonio=novo).update(patrimonio=antigo)


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0016_movimentacaoequipamento"),
    ]

    operations = [
        migrations.RunPython(renomear, reverter),
    ]
