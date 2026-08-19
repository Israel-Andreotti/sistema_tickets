from django.db import migrations

# Categorias existentes que passam a exigir número de patrimônio na abertura do
# chamado: impressoras, computador e telefones VoIP (estes últimos ficam no
# grupo "rede", não "equipamento" — mesmo assim são um aparelho físico rastreável).
NOMES_REQUER_PATRIMONIO = [
    "Impressora não imprime",
    "Impressora com papel atolado",
    "Compartilhar impressora",
    "Troca de toner",
    "Impressora térmica desconfigurada",
    "Manutenção de computador",
    "Telefone com problemas",
    "Telefone não realiza ligações externas",
    "Telefone não transfere/puxa ligação",
]

# Categoria nova: não existia "monitor" no catálogo de 0005_substituir_catalogo_categorias.
MONITOR_NOME = "Monitor não funciona"
MONITOR_GRUPO = "equipamento"
MONITOR_PESO = 2
MONITOR_SLA = 24


def marcar_categorias(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")

    Categoria.objects.filter(nome__in=NOMES_REQUER_PATRIMONIO).update(
        requer_patrimonio=True
    )

    Categoria.objects.get_or_create(
        nome=MONITOR_NOME,
        defaults={
            "grupo": MONITOR_GRUPO,
            "peso_categoria": MONITOR_PESO,
            "sla_horas": MONITOR_SLA,
            "requer_patrimonio": True,
        },
    )


def reverter(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")

    Categoria.objects.filter(nome__in=NOMES_REQUER_PATRIMONIO).update(
        requer_patrimonio=False
    )
    Categoria.objects.filter(nome=MONITOR_NOME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0007_categoria_requer_patrimonio"),
    ]

    operations = [
        migrations.RunPython(marcar_categorias, reverter),
    ]
