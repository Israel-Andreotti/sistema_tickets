"""Popula mais itens de exemplo no CMDB (monitores, impressoras, telefones,
computadores em setores variados) e adiciona a categoria "Instalar
impressora" — faltava uma categoria específica para instalação/configuração
inicial de uma impressora nova (diferente de "Compartilhar impressora", que
pressupõe um equipamento já cadastrado)."""
from django.db import migrations

# (patrimonio, categoria, marca, modelo, setor_nome, status)
EQUIPAMENTOS = [
    ("000005", "computador", "Dell", "OptiPlex 3090", "Emergência Pediátrica", "ativo"),
    ("000006", "computador", "Lenovo", "ThinkCentre M70s", "UTI Neonatal", "ativo"),
    ("000007", "computador", "HP", "EliteDesk 800", "Laboratório – Coleta", "ativo"),
    ("000008", "monitor", "Samsung", "S24R350", "Internação Pediátrica", "ativo"),
    ("000009", "monitor", "AOC", "24B2XH", "Recursos Humanos", "ativo"),
    ("000010", "monitor", "LG", "22MK400H", "Financeiro", "manutencao"),
    ("000011", "impressora", "HP", "LaserJet Pro M15w", "Farmácia", "ativo"),
    ("000012", "impressora", "Epson", "L3250", "Faturamento", "ativo"),
    ("000013", "impressora", "Zebra", "ZD230", "Almoxarifado", "ativo"),
    ("000014", "telefone_voip", "Cisco", "CP-7841", "Ouvidoria", "ativo"),
    ("000015", "telefone_voip", "Grandstream", "GXP2130", "Recursos Humanos", "ativo"),
    ("000016", "telefone_voip", "Yealink", "T46S", "UTI Pediátrica", "ativo"),
    ("000017", "computador", "Dell", "OptiPlex 7090", "Núcleo de Tecnologia da Informação", "ativo"),
    ("000018", "monitor", "Dell", "P2419H", "Núcleo de Tecnologia da Informação", "baixado"),
]

NOVA_CATEGORIA = {
    "nome": "Instalar impressora",
    "grupo": "impressora",
    "peso_categoria": 2,
    "sla_horas": 48,
    "requer_patrimonio": False,
}


def seed_equipamentos(apps, schema_editor):
    ItemConfiguracao = apps.get_model("tickets", "ItemConfiguracao")
    Setor = apps.get_model("tickets", "Setor")

    for patrimonio, categoria, marca, modelo, setor_nome, status in EQUIPAMENTOS:
        setor = Setor.objects.filter(nome=setor_nome).first()
        if not setor:
            continue
        ItemConfiguracao.objects.get_or_create(
            patrimonio=patrimonio,
            defaults={
                "categoria": categoria, "marca": marca, "modelo": modelo,
                "setor": setor, "status": status,
            },
        )


def remover_equipamentos(apps, schema_editor):
    ItemConfiguracao = apps.get_model("tickets", "ItemConfiguracao")
    ItemConfiguracao.objects.filter(patrimonio__in=[e[0] for e in EQUIPAMENTOS]).delete()


def seed_categoria(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")
    Categoria.objects.get_or_create(nome=NOVA_CATEGORIA["nome"], defaults=NOVA_CATEGORIA)


def remover_categoria(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")
    Categoria.objects.filter(nome=NOVA_CATEGORIA["nome"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0031_item_data_validade_garantia"),
    ]

    operations = [
        migrations.RunPython(seed_equipamentos, remover_equipamentos),
        migrations.RunPython(seed_categoria, remover_categoria),
    ]
