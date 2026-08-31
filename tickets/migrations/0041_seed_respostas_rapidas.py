from django.db import migrations

RESPOSTAS = [
    # (titulo, texto, tipo_padrao)
    (
        "Limpeza de cache",
        "Pra resolver, siga os passos abaixo:\n"
        "1. Feche todas as janelas do navegador.\n"
        "2. Abra novamente e pressione Ctrl+Shift+Delete.\n"
        "3. Selecione \"Imagens e arquivos em cache\" e clique em limpar.\n"
        "4. Reinicie o navegador e tente acessar o sistema novamente.\n"
        "Se o problema persistir, me avise por aqui.",
        "resposta_usuario",
    ),
    (
        "Reset de senha",
        "Sua senha foi redefinida. Siga os passos abaixo para criar uma nova:\n"
        "1. Acesse a tela de login do sistema.\n"
        "2. Use a senha temporária informada por telefone/e-mail institucional.\n"
        "3. No primeiro acesso, o sistema vai pedir para você cadastrar uma nova senha.\n"
        "Qualquer dificuldade, me avise por aqui.",
        "resposta_usuario",
    ),
]


def seed_respostas_rapidas(apps, schema_editor):
    RespostaRapida = apps.get_model("tickets", "RespostaRapida")
    for titulo, texto, tipo_padrao in RESPOSTAS:
        RespostaRapida.objects.get_or_create(
            titulo=titulo, defaults={"texto": texto, "tipo_padrao": tipo_padrao}
        )


def remover_respostas_rapidas(apps, schema_editor):
    RespostaRapida = apps.get_model("tickets", "RespostaRapida")
    RespostaRapida.objects.filter(titulo__in=[r[0] for r in RESPOSTAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0040_respostarapida"),
    ]

    operations = [
        migrations.RunPython(seed_respostas_rapidas, remover_respostas_rapidas),
    ]
