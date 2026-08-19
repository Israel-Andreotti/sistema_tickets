from django.db import migrations

SETORES_ANTIGOS = [
    # (sigla,) — apagados nesta migração, substituídos pelo catálogo real do hospital
    ("UTINEO",), ("EMERG",), ("BLOCIR",), ("BANSANG",), ("PNAR",),
    ("FARM",), ("ENGCLIN",), ("ALOJCONJ",), ("INTMULH",), ("INTPSIQ",), ("UCINEO",),
    ("RECCAD",), ("TI",), ("PSICO",), ("CTRLOP",), ("BANLEITE",),
    ("ADM",), ("FAT",), ("DIRGERAL",), ("RH",), ("MANUT",), ("ENSPESQ",), ("FIN",),
]

# Recriados na reversão desta migração, com os mesmos dados de 0002_seed_catalogo.
SETORES_ANTIGOS_COMPLETO = [
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

# (nome, sigla, peso_setor) — catálogo real informado pelo usuário. peso_setor é uma
# proposta de criticidade (5 = risco de vida imediato/suporte crítico direto a essas
# áreas, 4 = alta criticidade, 3 = suporte assistencial/operacional relevante,
# 2 = administrativo/apoio geral), ajustável pelo admin sem alterar código.
SETORES_NOVOS = [
    ("Laboratório – Coleta", "LABCOL", 3),
    ("Marcação de Consultas", "MARCCONS", 2),
    ("Exames de Alto Custo", "EXAMALTO", 3),
    ("Ouvidoria", "OUVID", 2),
    ("Psicologia", "PSICO", 3),
    ("TEA", "TEA", 3),
    ("Serviço Social", "SERVSOC", 3),
    ("Arquivo Médico", "ARQMED", 2),
    ("Coordenação Ambulatorial", "COORDAMB", 3),
    ("Banco de Sangue", "BANSANG", 5),
    ("Laboratório – Área Técnica", "LABTEC", 3),
    ("Serviço de Triagem e Referência Neonatal", "TRIAGENEO", 5),
    ("Ambulatório Ginecologia", "AMBGINECO", 3),
    ("Almoxarifado", "ALMOX", 2),
    ("Ambulatório Psiquiatria", "AMBPSIQ", 3),
    ("Odontologia", "ODONTO", 3),
    ("Ambulatório Pediatria", "AMBPED", 3),
    ("CRAI - Centro de Referência em Atendimento Infanto-juvenil", "CRAI", 3),
    ("SESMT – Segurança do Trabalho", "SESMT", 2),
    ("CCIH – Controle de Infecção Hospitalar", "CCIH", 4),
    ("ASSEP – Assessoria de Ensino e Pesquisa", "ASSEP", 2),
    ("Recursos Humanos", "RH", 2),
    ("Financeiro", "FIN", 2),
    ("Faturamento", "FAT", 2),
    ("Engenharia Clínica", "ENGCLIN", 4),
    ("Núcleo de Tecnologia da Informação", "NTI", 3),
    ("Patrimônio", "PATRIM", 2),
    ("Higienização e Limpeza", "HIGLIMP", 2),
    ("Rouparia", "ROUPARIA", 2),
    ("Farmácia", "FARM", 4),
    ("Unidade de Apoio Logístico", "UAL", 3),
    ("Nutrição – Administrativo", "NUTRADM", 2),
    ("Nutrição – Área Técnica", "NUTRTEC", 3),
    ("Internação Pediátrica", "INTPED", 4),
    ("UTI Pediátrica", "UTIPED", 5),
    ("Internação Psiquiátrica", "INTPSIQ", 4),
    ("Pré-Natal de Alto Risco", "PNAR", 5),
    ("Banco de Leite", "BANLEITE", 3),
    ("Internação Ginecológica", "INTGINE", 4),
    ("Alojamento Conjunto", "ALOJCONJ", 4),
    ("UTI Neonatal", "UTINEO", 5),
    ("Centro Obstétrico", "CENTOBST", 5),
    ("Bloco Cirúrgico", "BLOCIR", 5),
    ("Bloco Cirúrgico – Administrativo", "BLOCIRADM", 3),
    ("Centro de Materiais e Esterilização", "CME", 4),
]


def substituir_setores(apps, schema_editor):
    Setor = apps.get_model("tickets", "Setor")

    Setor.objects.filter(sigla__in=[s[0] for s in SETORES_ANTIGOS]).delete()

    for nome, sigla, peso_setor in SETORES_NOVOS:
        Setor.objects.get_or_create(
            sigla=sigla, defaults={"nome": nome, "peso_setor": peso_setor}
        )


def reverter_setores(apps, schema_editor):
    Setor = apps.get_model("tickets", "Setor")

    Setor.objects.filter(sigla__in=[s[1] for s in SETORES_NOVOS]).delete()

    for nome, sigla, peso_setor in SETORES_ANTIGOS_COMPLETO:
        Setor.objects.get_or_create(
            sigla=sigla, defaults={"nome": nome, "peso_setor": peso_setor}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0003_seed_parametros_e_regras"),
    ]

    operations = [
        migrations.RunPython(substituir_setores, reverter_setores),
    ]
