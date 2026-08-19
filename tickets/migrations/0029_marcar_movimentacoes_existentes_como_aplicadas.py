"""Toda MovimentacaoEquipamento criada antes desta mudança já teve seu efeito
aplicado ao CMDB imediatamente no momento do registro (comportamento antigo).
A partir daqui, o registro só fica "aplicada=True" quando o chamado é
efetivamente fechado — mas o histórico existente precisa refletir que já
foi aplicado, senão fecharia tickets já fechados reaplicando movimentações
que na prática já aconteceram."""
from django.db import migrations


def marcar_como_aplicadas(apps, schema_editor):
    MovimentacaoEquipamento = apps.get_model("tickets", "MovimentacaoEquipamento")
    MovimentacaoEquipamento.objects.update(aplicada=True)


def reverter(apps, schema_editor):
    MovimentacaoEquipamento = apps.get_model("tickets", "MovimentacaoEquipamento")
    MovimentacaoEquipamento.objects.update(aplicada=False)


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0028_movimentacao_aplicada"),
    ]

    operations = [
        migrations.RunPython(marcar_como_aplicadas, reverter),
    ]
