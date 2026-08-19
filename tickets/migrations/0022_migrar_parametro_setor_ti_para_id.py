from django.db import migrations

CHAVE_ANTIGA = "setor_ti_sigla"
CHAVE_NOVA = "setor_ti_id"
DESCRICAO_NOVA = (
    "ID do setor de TI (Setor.id) para onde um equipamento substituído "
    "retorna automaticamente ao ser trocado num ticket"
)


def migrar_para_id(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    Setor = apps.get_model("tickets", "Setor")

    antigo = ParametroSistema.objects.filter(chave=CHAVE_ANTIGA).first()
    if antigo:
        setor = Setor.objects.filter(sigla=antigo.valor).first()
        if setor:
            ParametroSistema.objects.update_or_create(
                chave=CHAVE_NOVA, defaults={"valor": str(setor.pk), "descricao": DESCRICAO_NOVA}
            )
        antigo.delete()


def migrar_para_sigla(apps, schema_editor):
    ParametroSistema = apps.get_model("tickets", "ParametroSistema")
    Setor = apps.get_model("tickets", "Setor")

    novo = ParametroSistema.objects.filter(chave=CHAVE_NOVA).first()
    if novo:
        setor = Setor.objects.filter(pk=int(novo.valor)).first()
        if setor:
            ParametroSistema.objects.update_or_create(
                chave=CHAVE_ANTIGA,
                defaults={
                    "valor": setor.sigla,
                    "descricao": (
                        "Sigla do setor de TI (Setor.sigla) para onde um equipamento substituído "
                        "retorna automaticamente ao ser trocado num ticket"
                    ),
                },
            )
        novo.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0021_ticket_tecnico_responsavel"),
    ]

    operations = [
        migrations.RunPython(migrar_para_id, migrar_para_sigla),
    ]
