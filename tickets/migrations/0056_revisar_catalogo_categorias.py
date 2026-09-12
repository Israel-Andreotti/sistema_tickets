"""Revisa o catálogo de Categoria pro catálogo real de serviços do hospital
(RN28/RN82) — a maior parte das 38 categorias existentes é reaproveitada
(rename/regrupo/retipo, mesmo pk, peso/SLA/nível preservados), 16 categorias
novas são criadas e 6 categorias sem correspondente no catálogo alvo são
marcadas inativas (`ativo=False`) em vez de apagadas — duas delas ainda são
usadas por tickets reais e não podem ser removidas (`on_delete=PROTECT` em
Ticket.categoria_*). Mesmo padrão de dict nome/pk → novo valor + forward/
reverse já usado em 0027_reclassificar_categorias_por_grupo.py.
"""
from django.db import migrations, models

# pk -> (novo_nome, novo_grupo, novo_tipo, novo_requer_patrimonio).
# peso_categoria/sla_horas/nivel_atendimento NÃO mudam — só nome/grupo/tipo/patrimônio.
REUSE_NOVO_POR_PK = {
    # Impressora
    41: ("Impressora com defeito / não imprime", "impressora", "incidente", True),
    61: ("Instalação de impressora no computador", "impressora", "requisicao", False),
    45: ("Troca de toner", "impressora", "requisicao", True),
    43: ("Scanner com defeito", "impressora", "incidente", True),
    46: ("Impressora de etiquetas/pulseiras com defeito", "impressora", "incidente", True),
    # Computador e periféricos
    51: ("Computador não liga / lento / com defeito", "computador", "incidente", True),
    37: ("Instalação de computador", "computador", "requisicao", False),
    38: ("Remoção ou troca de computador", "computador", "requisicao", True),
    47: ("Limpeza preventiva", "computador", "requisicao", True),
    60: ("Monitor com defeito", "computador", "incidente", True),
    48: ("Mouse ou teclado com defeito", "computador", "incidente", False),
    50: ("Webcam com defeito", "computador", "incidente", False),
    # Rede e telefonia
    27: ("Sem acesso à internet", "rede", "incidente", False),
    28: ("Instalação de novo ponto de rede", "rede", "requisicao", False),
    29: ("Wi-Fi sem conexão", "rede", "incidente", False),
    30: ("Solicitação de acesso VPN", "rede", "requisicao", False),
    31: ("Telefone VoIP com defeito", "rede", "incidente", True),
    32: ("Problema em ligações externas", "rede", "incidente", False),
    33: ("Configuração de transferência de chamadas", "rede", "requisicao", False),
    # Acessos e permissões
    52: ("Criação de usuário (admissão)", "acesso", "requisicao", False),
    54: ("Alteração de usuário", "acesso", "requisicao", False),
    53: ("Desligamento de colaborador (exclusão de usuário)", "acesso", "requisicao", False),
    34: ("Reset de senha", "acesso", "requisicao", False),
    55: ("Inclusão em lista de e-mail", "acesso", "requisicao", False),
    58: ("Permissão em pasta compartilhada", "acesso", "requisicao", False),
    # Sistemas clínicos/assistenciais
    24: ("Erro no prontuário eletrônico", "clinico", "incidente", False),
    25: ("Erro no sistema de laboratório/exames", "clinico", "incidente", False),
    26: ("Erro no sistema de agendamento/regulação", "clinico", "incidente", False),
    # Software e suporte geral
    35: ("Instalação/configuração de software", "suporte", "requisicao", False),
    40: ("Erro de acesso a site", "suporte", "incidente", False),
    57: ("E-mail não envia/recebe", "suporte", "incidente", False),
    39: ("Configuração de projeção/auditório", "suporte", "requisicao", False),
}

# pk -> valores originais (nome, grupo, tipo, requer_patrimonio), pra reverter.
REUSE_ANTIGO_POR_PK = {
    41: ("Impressora não imprime", "impressora", "incidente", True),
    61: ("Instalar impressora", "impressora", "requisicao", False),
    45: ("Troca de toner", "impressora", "incidente", True),
    43: ("Scanner não funciona", "computador", "incidente", False),
    46: ("Impressora térmica desconfigurada", "impressora", "incidente", True),
    51: ("Manutenção de computador", "computador", "requisicao", True),
    37: ("Instalação de computador", "computador", "requisicao", False),
    38: ("Remoção de computador", "computador", "requisicao", True),
    47: ("Limpeza preventiva de equipamento", "computador", "requisicao", False),
    60: ("Monitor não funciona", "computador", "incidente", True),
    48: ("Substituição/instalação de mouse", "computador", "incidente", False),
    50: ("Instalação/empréstimo de webcam", "computador", "requisicao", False),
    27: ("Sem internet", "rede", "incidente", False),
    28: ("Instalação de ponto de rede", "rede", "requisicao", False),
    29: ("Wi-Fi indisponível", "rede", "incidente", False),
    30: ("VPN / acesso remoto", "rede", "requisicao", False),
    31: ("Telefone com problemas", "rede", "incidente", True),
    32: ("Telefone não realiza ligações externas", "rede", "incidente", True),
    33: ("Telefone não transfere/puxa ligação", "rede", "incidente", True),
    52: ("Criação de usuário", "acesso", "requisicao", False),
    54: ("Alteração de usuário", "acesso", "incidente", False),
    53: ("Exclusão de usuário", "acesso", "requisicao", False),
    34: ("Reset de senha", "suporte", "incidente", False),
    55: ("Inclusão em lista de e-mail", "acesso", "requisicao", False),
    58: ("Permissão de usuários a pastas compartilhadas", "acesso", "requisicao", False),
    24: ("Prontuário eletrônico indisponível", "clinico", "incidente", False),
    25: ("Sistema de laboratório/exames fora do ar", "clinico", "incidente", False),
    26: ("Sistema de agendamento/regulação", "clinico", "incidente", False),
    35: ("Instalação de software e aplicativos", "suporte", "requisicao", False),
    40: ("Erro de acesso a site", "suporte", "incidente", False),
    57: ("Suporte ao e-mail", "acesso", "incidente", False),
    39: ("Configuração de equipamento de projeção/auditório", "suporte", "requisicao", False),
}

# Sem correspondente no catálogo alvo — marcadas ativo=False em vez de
# apagadas (pk 59 ainda tem 1 ticket referenciando, então não pode ser
# removida; as outras não têm ticket, mas seguem o mesmo tratamento por
# consistência e pra manter o histórico do Admin).
ORFAS_PKS = [42, 44, 49, 56, 36, 59]

# (nome, grupo, tipo, peso_categoria, sla_horas, requer_patrimonio) — sem
# correspondente no catálogo existente; peso/SLA são só uma proposta inicial
# (mesmo critério de similaridade já usado nas migrations anteriores),
# ajustável pelo Admin sem alterar código. nivel_atendimento fica no default
# (N1) igual a todas as outras categorias hoje.
NOVAS = [
    # Computador e periféricos
    ("Leitor de código de barras com defeito", "computador", "incidente", 2, 24, True),
    ("Nobreak/estabilizador com defeito", "computador", "incidente", 3, 8, True),
    ("Celular/tablet corporativo", "computador", "incidente", 2, 24, True),
    # Rede e telefonia
    ("Ponto de rede sem funcionar", "rede", "incidente", 2, 8, False),
    ("VPN sem conexão", "rede", "incidente", 3, 4, False),
    ("Configuração de ramal VoIP", "rede", "requisicao", 2, 24, True),
    # Acessos e permissões
    ("Desbloqueio de conta", "acesso", "requisicao", 2, 8, False),
    ("Acesso/perfil em sistema clínico", "acesso", "requisicao", 3, 24, False),
    ("Mapeamento de unidade de rede", "acesso", "requisicao", 2, 24, False),
    ("Certificado digital", "acesso", "requisicao", 2, 24, False),
    # Sistemas clínicos/assistenciais
    ("Erro no sistema de imagens (PACS)", "clinico", "incidente", 4, 4, False),
    ("Erro no sistema de farmácia/dispensação", "clinico", "incidente", 5, 2, False),
    ("Painel/totem de senhas com defeito", "clinico", "incidente", 2, 24, True),
    # Software e suporte geral
    ("Erro em software", "suporte", "incidente", 2, 8, False),
    ("Suspeita de vírus/phishing", "suporte", "incidente", 4, 4, False),
    ("Recuperação de arquivo/backup", "suporte", "requisicao", 2, 24, False),
]


def revisar_catalogo(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")

    for pk, (nome, grupo, tipo, requer_patrimonio) in REUSE_NOVO_POR_PK.items():
        Categoria.objects.filter(pk=pk).update(
            nome=nome, grupo=grupo, tipo=tipo, requer_patrimonio=requer_patrimonio,
        )

    Categoria.objects.filter(pk__in=ORFAS_PKS).update(ativo=False)

    for nome, grupo, tipo, peso_categoria, sla_horas, requer_patrimonio in NOVAS:
        Categoria.objects.get_or_create(
            nome=nome,
            defaults={
                "grupo": grupo, "tipo": tipo,
                "peso_categoria": peso_categoria, "sla_horas": sla_horas,
                "requer_patrimonio": requer_patrimonio,
            },
        )


def reverter_catalogo(apps, schema_editor):
    Categoria = apps.get_model("tickets", "Categoria")

    Categoria.objects.filter(nome__in=[n[0] for n in NOVAS]).delete()

    Categoria.objects.filter(pk__in=ORFAS_PKS).update(ativo=True)

    for pk, (nome, grupo, tipo, requer_patrimonio) in REUSE_ANTIGO_POR_PK.items():
        Categoria.objects.filter(pk=pk).update(
            nome=nome, grupo=grupo, tipo=tipo, requer_patrimonio=requer_patrimonio,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0055_seed_parametro_confianca_ia'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoria',
            name='ativo',
            field=models.BooleanField(default=True, help_text='Categorias inativas somem da abertura de chamado, mas continuam no Admin e no histórico de tickets que já as usaram'),
        ),
        migrations.RunPython(revisar_catalogo, reverter_catalogo),
    ]
