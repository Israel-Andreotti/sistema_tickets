"""Cria um PerfilTecnico (nível N1, padrão) pra todo usuário is_staff já
existente na base — daqui pra frente, o signal em tickets/signals.py cuida
disso sozinho pra usuários novos ou promovidos a is_staff."""
from django.db import migrations


def seed_perfis_tecnico(apps, schema_editor):
    User = apps.get_model("auth", "User")
    PerfilTecnico = apps.get_model("tickets", "PerfilTecnico")
    for usuario in User.objects.filter(is_staff=True):
        PerfilTecnico.objects.get_or_create(usuario=usuario)


def reverter(apps, schema_editor):
    PerfilTecnico = apps.get_model("tickets", "PerfilTecnico")
    PerfilTecnico.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0047_alter_notificacao_tipo_perfiltecnico"),
    ]

    operations = [
        migrations.RunPython(seed_perfis_tecnico, reverter),
    ]
