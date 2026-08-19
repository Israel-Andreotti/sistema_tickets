from django.db import migrations

SETORES = [
    # (nome, sigla, peso_setor)
    ("UTI Neonatal", "UTINEO", 5),
    ("Emergência/Pronto Atendimento", "EMERG", 5),
    ("Bloco Cirúrgico", "BLOCIR", 5),
    ("Banco de Sangue", "BANSANG", 5),
    ("Pré Natal de Alto Risco", "PNAR", 5),
    ("Farmácia Hospitalar", "FARM", 4),
    ("Engenharia Clínica", "ENGCLIN", 4),
    ("Alojamento Conjunto", "ALOJCONJ", 4),
    ("Internação da Mulher", "INTMULH", 4),
    ("Internação Psiquiátrica", "INTPSIQ", 4),
    ("UCI Neonatal", "UCINEO", 4),
    ("Recepção/Cadastro", "RECCAD", 3),
    ("Tecnologia da Informação", "TI", 3),
    ("Psicologia", "PSICO", 3),
    ("Controle Operacional", "CTRLOP", 3),
    ("Banco de Leite", "BANLEITE", 3),
    ("Administrativo", "ADM", 2),
    ("Faturamento", "FAT", 2),
    ("Direção Geral", "DIRGERAL", 2),
    ("Recursos Humanos", "RH", 2),
    ("Manutenção", "MANUT", 2),
    ("Ensino e Pesquisa", "ENSPESQ", 2),
    ("Financeiro", "FIN", 2),
]

# (nome, grupo, peso_categoria, sla_horas) — valores padrão propostos,
# ajustáveis pelo admin sem alterar código.
CATEGORIAS = [
    ("Prontuário eletrônico", "clinico", 5, 1),
    ("Sistema de laboratório/exames", "clinico", 5, 2),
    ("Sistema de agendamento/regulação", "clinico", 4, 4),

    ("Internet", "rede", 3, 4),
    ("Ponto de rede", "rede", 3, 8),
    ("Wi-Fi", "rede", 2, 8),
    ("VPN", "rede", 3, 8),
    ("Telefonia", "rede", 4, 2),

    ("Reset de senha", "suporte", 3, 2),
    ("Instalação/configuração de software", "suporte", 2, 24),
    ("Instalação/remoção de computador", "suporte", 2, 48),
    ("Configuração de projeção/auditório", "suporte", 2, 24),
    ("Erro de acesso a site", "suporte", 2, 8),

    ("Impressora", "equipamento", 3, 8),
    ("Scanner", "equipamento", 2, 24),
    ("Toner", "equipamento", 2, 24),
    ("Limpeza preventiva", "equipamento", 1, 72),
    ("Mouse/teclado", "equipamento", 2, 24),
    ("Webcam", "equipamento", 1, 48),
    ("Manutenção de computador", "equipamento", 3, 24),

    ("Criação/exclusão/alteração de usuário", "acesso", 3, 24),
    ("Listas de e-mail", "acesso", 2, 24),
    ("Permissões de pastas compartilhadas", "acesso", 3, 24),
]


def seed_catalogo(apps, schema_editor):
    Setor = apps.get_model("tickets", "Setor")
    Categoria = apps.get_model("tickets", "Categoria")

    for nome, sigla, peso_setor in SETORES:
        Setor.objects.get_or_create(
            sigla=sigla, defaults={"nome": nome, "peso_setor": peso_setor}
        )

    for nome, grupo, peso_categoria, sla_horas in CATEGORIAS:
        Categoria.objects.get_or_create(
            nome=nome,
            defaults={
                "grupo": grupo,
                "peso_categoria": peso_categoria,
                "sla_horas": sla_horas,
            },
        )


def remove_catalogo(apps, schema_editor):
    Setor = apps.get_model("tickets", "Setor")
    Categoria = apps.get_model("tickets", "Categoria")

    Setor.objects.filter(sigla__in=[s[1] for s in SETORES]).delete()
    Categoria.objects.filter(nome__in=[c[0] for c in CATEGORIAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalogo, remove_catalogo),
    ]
