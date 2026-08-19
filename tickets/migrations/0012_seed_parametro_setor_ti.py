from django.db import migrations

CHAVE = "setor_ti_sigla"
VALOR = "NTI"
DESCRICAO = (
    "Sigla do setor de TI (Setor.sigla) para onde um equipamento substituído "
    "retorna automaticamente ao ser trocado num ticket"
)


def seed_parametro(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    ParametroSistema.objects.get_or_create(
        chave=CHAVE, defaults={"valor": VALOR, "descricao": DESCRICAO}
    )


def remover_parametro(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    ParametroSistema.objects.filter(chave=CHAVE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0011_setor_gestor"),
    ]

    operations = [
        migrations.RunPython(seed_parametro, remover_parametro),
    ]
