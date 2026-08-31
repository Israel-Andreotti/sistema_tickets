from django.db import migrations

GRUPOS_POR_TITULO = {
    "Limpeza de cache": "suporte",
    "Reset de senha": "acesso",
}


def seed_grupos(apps, schema_editor):
    RespostaRapida = apps.get_model("tickets", "RespostaRapida")
    for titulo, grupo in GRUPOS_POR_TITULO.items():
        RespostaRapida.objects.filter(titulo=titulo).update(grupo=grupo)


def reverter_grupos(apps, schema_editor):
    RespostaRapida = apps.get_model("tickets", "RespostaRapida")
    RespostaRapida.objects.filter(titulo__in=GRUPOS_POR_TITULO.keys()).update(grupo=None)


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0042_alter_respostarapida_options_respostarapida_grupo"),
    ]

    operations = [
        migrations.RunPython(seed_grupos, reverter_grupos),
    ]
