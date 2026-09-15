from django.db import migrations

CHAVE = "peso_setor_vital"
VALOR = "4"
DESCRICAO = (
    "Peso de setor (escala 1 a 5) a partir do qual ele é considerado \"vital\" "
    "para o indicador de chamados críticos por setor — usado no dashboard e no "
    "destaque de criticidade clínica da fila"
)


def seed_parametro(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    ParametroSistema.objects.get_or_create(
        chave=CHAVE, defaults={"valor": VALOR, "descricao": DESCRICAO}
    )


def remove_parametro(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    ParametroSistema.objects.filter(chave=CHAVE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0057_categoria_habilita_criacao_usuario"),
    ]

    operations = [
        migrations.RunPython(seed_parametro, remove_parametro),
    ]
