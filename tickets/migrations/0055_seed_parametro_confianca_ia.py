from django.db import migrations

CHAVE = "ia_confianca_minima"
VALOR = "0.30"
DESCRICAO = (
    "Confiança mínima (0 a 1) para aceitar o palpite do classificador de IA — "
    "abaixo disso o chamado fica sem categoria_ia em vez de receber um palpite fraco"
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
        ("tickets", "0054_ticket_confianca_ia"),
    ]

    operations = [
        migrations.RunPython(seed_parametro, remove_parametro),
    ]
