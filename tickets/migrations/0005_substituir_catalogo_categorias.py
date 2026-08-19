from django.db import migrations

CATEGORIAS_ANTIGAS_NOMES = [
    "Prontuário eletrônico",
    "Sistema de laboratório/exames",
    "Sistema de agendamento/regulação",
    "Internet",
    "Ponto de rede",
    "Wi-Fi",
    "VPN",
    "Telefonia",
    "Reset de senha",
    "Instalação/configuração de software",
    "Instalação/remoção de computador",
    "Configuração de projeção/auditório",
    "Erro de acesso a site",
    "Impressora",
    "Scanner",
    "Toner",
    "Limpeza preventiva",
    "Mouse/teclado",
    "Webcam",
    "Manutenção de computador",
    "Criação/exclusão/alteração de usuário",
    "Listas de e-mail",
    "Permissões de pastas compartilhadas",
]

# Recriadas na reversão desta migração, com os mesmos dados de 0002_seed_catalogo.
CATEGORIAS_ANTIGAS_COMPLETO = [
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

# (nome, grupo, peso_categoria, sla_horas) — catálogo real informado pelo usuário,
# um serviço por sintoma específico. peso_categoria/sla_horas são propostas de
# criticidade/urgência (mesmo critério das migrações anteriores), ajustáveis pelo
# admin sem alterar código.
CATEGORIAS_NOVAS = [
    # Sistemas clínicos/assistenciais
    ("Prontuário eletrônico indisponível", "clinico", 5, 1),
    ("Sistema de laboratório/exames fora do ar", "clinico", 5, 2),
    ("Sistema de agendamento/regulação", "clinico", 4, 4),

    # Infraestrutura de rede
    ("Sem internet", "rede", 3, 4),
    ("Instalação de ponto de rede", "rede", 2, 24),
    ("Wi-Fi indisponível", "rede", 2, 8),
    ("VPN / acesso remoto", "rede", 3, 8),
    ("Telefone com problemas", "rede", 3, 4),
    ("Telefone não realiza ligações externas", "rede", 3, 4),
    ("Telefone não transfere/puxa ligação", "rede", 3, 4),

    # Suporte ao usuário
    ("Reset de senha", "suporte", 3, 2),
    ("Instalação de software e aplicativos", "suporte", 2, 24),
    ("Configuração de software e aplicativos", "suporte", 2, 24),
    ("Instalação de computador", "suporte", 2, 48),
    ("Remoção de computador", "suporte", 1, 48),
    ("Configuração de equipamento de projeção/auditório", "suporte", 2, 24),
    ("Erro de acesso a site", "suporte", 2, 8),

    # Equipamentos e periféricos
    ("Impressora não imprime", "equipamento", 3, 8),
    ("Impressora com papel atolado", "equipamento", 2, 4),
    ("Scanner não funciona", "equipamento", 2, 24),
    ("Compartilhar impressora", "equipamento", 1, 24),
    ("Troca de toner", "equipamento", 2, 24),
    ("Impressora térmica desconfigurada", "equipamento", 3, 8),
    ("Limpeza preventiva de equipamento", "equipamento", 1, 72),
    ("Substituição/instalação de mouse", "equipamento", 1, 24),
    ("Substituição/instalação de teclado", "equipamento", 1, 24),
    ("Instalação/empréstimo de webcam", "equipamento", 1, 48),
    ("Manutenção de computador", "equipamento", 3, 24),

    # Acessos e permissões
    ("Criação de usuário", "acesso", 3, 24),
    ("Exclusão de usuário", "acesso", 3, 24),
    ("Alteração de usuário", "acesso", 2, 24),
    ("Inclusão em lista de e-mail", "acesso", 2, 24),
    ("Remoção de lista de e-mail", "acesso", 2, 24),
    ("Suporte ao e-mail", "acesso", 3, 8),
    ("Permissão de usuários a pastas compartilhadas", "acesso", 2, 24),
    ("Criação de pasta compartilhada", "acesso", 2, 24),
]


def substituir_categorias(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")

    Categoria.objects.filter(nome__in=CATEGORIAS_ANTIGAS_NOMES).delete()

    for nome, grupo, peso_categoria, sla_horas in CATEGORIAS_NOVAS:
        Categoria.objects.get_or_create(
            nome=nome,
            defaults={
                "grupo": grupo,
                "peso_categoria": peso_categoria,
                "sla_horas": sla_horas,
            },
        )


def reverter_categorias(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")

    Categoria.objects.filter(nome__in=[c[0] for c in CATEGORIAS_NOVAS]).delete()

    for nome, grupo, peso_categoria, sla_horas in CATEGORIAS_ANTIGAS_COMPLETO:
        Categoria.objects.get_or_create(
            nome=nome,
            defaults={
                "grupo": grupo,
                "peso_categoria": peso_categoria,
                "sla_horas": sla_horas,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0004_substituir_catalogo_setores"),
    ]

    operations = [
        migrations.RunPython(substituir_categorias, reverter_categorias),
    ]
