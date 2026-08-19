"""Reclassifica as categorias existentes na nova taxonomia de grupo, que passa
a separar por tipo de equipamento (Impressora, Computador) em vez de agrupar
tudo em "Equipamentos e periféricos". Mapeamento explícito por nome, definido
a partir do catálogo real informado pelo usuário."""
from django.db import migrations

NOVO_GRUPO_POR_NOME = {
    # Impressora
    "Compartilhar impressora": "impressora",
    "Impressora com papel atolado": "impressora",
    "Impressora não imprime": "impressora",
    "Impressora térmica desconfigurada": "impressora",
    "Troca de toner": "impressora",
    # Computador e periféricos
    "Manutenção de computador": "computador",
    "Instalação de computador": "computador",
    "Remoção de computador": "computador",
    "Monitor não funciona": "computador",
    "Substituição/instalação de mouse": "computador",
    "Substituição/instalação de teclado": "computador",
    "Instalação/empréstimo de webcam": "computador",
    "Scanner não funciona": "computador",
    "Limpeza preventiva de equipamento": "computador",
    # Rede e telefonia (grupo já existia, mantido)
    "Instalação de ponto de rede": "rede",
    "Sem internet": "rede",
    "Wi-Fi indisponível": "rede",
    "VPN / acesso remoto": "rede",
    "Telefone com problemas": "rede",
    "Telefone não realiza ligações externas": "rede",
    "Telefone não transfere/puxa ligação": "rede",
    # Acessos e permissões (grupo já existia, mantido)
    "Alteração de usuário": "acesso",
    "Criação de pasta compartilhada": "acesso",
    "Criação de usuário": "acesso",
    "Exclusão de usuário": "acesso",
    "Inclusão em lista de e-mail": "acesso",
    "Permissão de usuários a pastas compartilhadas": "acesso",
    "Remoção de lista de e-mail": "acesso",
    "Suporte ao e-mail": "acesso",
    # Sistemas clínicos/assistenciais (grupo já existia, mantido)
    "Prontuário eletrônico indisponível": "clinico",
    "Sistema de agendamento/regulação": "clinico",
    "Sistema de laboratório/exames fora do ar": "clinico",
    # Software e suporte geral
    "Configuração de equipamento de projeção/auditório": "suporte",
    "Configuração de software e aplicativos": "suporte",
    "Erro de acesso a site": "suporte",
    "Instalação de software e aplicativos": "suporte",
    "Reset de senha": "suporte",
}

# Grupo original de cada categoria, para a reversão da migração.
GRUPO_ANTIGO_POR_NOME = {
    "Compartilhar impressora": "equipamento",
    "Impressora com papel atolado": "equipamento",
    "Impressora não imprime": "equipamento",
    "Impressora térmica desconfigurada": "equipamento",
    "Troca de toner": "equipamento",
    "Manutenção de computador": "equipamento",
    "Instalação de computador": "suporte",
    "Remoção de computador": "suporte",
    "Monitor não funciona": "equipamento",
    "Substituição/instalação de mouse": "equipamento",
    "Substituição/instalação de teclado": "equipamento",
    "Instalação/empréstimo de webcam": "equipamento",
    "Scanner não funciona": "equipamento",
    "Limpeza preventiva de equipamento": "equipamento",
    "Instalação de ponto de rede": "rede",
    "Sem internet": "rede",
    "Wi-Fi indisponível": "rede",
    "VPN / acesso remoto": "rede",
    "Telefone com problemas": "rede",
    "Telefone não realiza ligações externas": "rede",
    "Telefone não transfere/puxa ligação": "rede",
    "Alteração de usuário": "acesso",
    "Criação de pasta compartilhada": "acesso",
    "Criação de usuário": "acesso",
    "Exclusão de usuário": "acesso",
    "Inclusão em lista de e-mail": "acesso",
    "Permissão de usuários a pastas compartilhadas": "acesso",
    "Remoção de lista de e-mail": "acesso",
    "Suporte ao e-mail": "acesso",
    "Prontuário eletrônico indisponível": "clinico",
    "Sistema de agendamento/regulação": "clinico",
    "Sistema de laboratório/exames fora do ar": "clinico",
    "Configuração de equipamento de projeção/auditório": "suporte",
    "Configuração de software e aplicativos": "suporte",
    "Erro de acesso a site": "suporte",
    "Instalação de software e aplicativos": "suporte",
    "Reset de senha": "suporte",
}


def aplicar_novo_grupo(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")
    for nome, grupo in NOVO_GRUPO_POR_NOME.items():
        Categoria.objects.filter(nome=nome).update(grupo=grupo)


def reverter_para_grupo_antigo(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")
    for nome, grupo in GRUPO_ANTIGO_POR_NOME.items():
        Categoria.objects.filter(nome=nome).update(grupo=grupo)


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0026_categoria_grupo_por_equipamento"),
    ]

    operations = [
        migrations.RunPython(aplicar_novo_grupo, reverter_para_grupo_antigo),
    ]
