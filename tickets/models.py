"""
Models Django para o sistema de classificação, priorização e recomendação
de tickets de TI hospitalar.

Todas as regras de negócio (pesos, SLAs, limiares de desvio e mapeamento
de recomendações) são armazenadas nestas tabelas — nunca fixadas no código
da aplicação, conforme exigido no projeto.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

patrimonio_validator = RegexValidator(
    regex=r"^\d{6}$",
    message="O patrimônio deve ter exatamente 6 dígitos numéricos, sem letras.",
)


class Setor(models.Model):
    nome = models.CharField(max_length=100)
    peso_setor = models.PositiveSmallIntegerField(
        help_text="Criticidade operacional do setor, de 1 a 5"
    )
    gestor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="setores_geridos",
        help_text="Usuário responsável pelo setor, autorizado a editar os equipamentos dele",
    )

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Categoria(models.Model):
    class Grupo(models.TextChoices):
        IMPRESSORA = "impressora", "Impressora"
        COMPUTADOR = "computador", "Computador e periféricos"
        REDE = "rede", "Rede e telefonia"
        ACESSO = "acesso", "Acessos e permissões"
        CLINICO = "clinico", "Sistemas clínicos/assistenciais"
        SUPORTE = "suporte", "Software e suporte geral"

    nome = models.CharField(max_length=150)
    grupo = models.CharField(max_length=20, choices=Grupo.choices)
    peso_categoria = models.PositiveSmallIntegerField(
        help_text="Criticidade intrínseca do serviço, de 1 a 5"
    )
    sla_horas = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text="Tempo esperado de atendimento, em horas"
    )
    requer_patrimonio = models.BooleanField(
        default=False,
        help_text="Se marcado, a abertura do chamado exige o número de patrimônio do equipamento",
    )

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["grupo", "nome"]

    def __str__(self):
        return self.nome


class ExcecaoPrioridade(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE)
    peso_override = models.PositiveSmallIntegerField(
        help_text="Peso de prioridade que substitui o cálculo padrão "
                   "(peso_categoria × peso_setor) para esta combinação"
    )

    class Meta:
        verbose_name = "Exceção de prioridade"
        verbose_name_plural = "Exceções de prioridade"
        unique_together = ("categoria", "setor")

    def __str__(self):
        return f"{self.categoria} @ {self.setor} → {self.peso_override}"


class ItemConfiguracao(models.Model):
    """CMDB — item de configuração (equipamento físico rastreado)."""

    class Categoria(models.TextChoices):
        COMPUTADOR = "computador", "Computador"
        MONITOR = "monitor", "Monitor"
        IMPRESSORA = "impressora", "Impressora"
        SCANNER = "scanner", "Scanner"
        TELEFONE_VOIP = "telefone_voip", "Telefone VoIP"
        MOUSE = "mouse", "Mouse"
        TECLADO = "teclado", "Teclado"
        WEBCAM = "webcam", "Webcam"
        OUTRO = "outro", "Outro"

    class Status(models.TextChoices):
        ATIVO = "ativo", "Disponível"
        MANUTENCAO = "manutencao", "Em triagem"
        BAIXADO = "baixado", "Baixado"

    patrimonio = models.CharField(
        max_length=6, unique=True, validators=[patrimonio_validator],
        help_text="6 dígitos numéricos, sem letras (ex: 000123)",
    )
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ATIVO
    )
    data_aquisicao = models.DateField(null=True, blank=True)
    data_validade_garantia = models.DateField(
        null=True, blank=True,
        help_text="Data em que a garantia do equipamento expira, se houver",
    )

    class Meta:
        verbose_name = "Item de configuração"
        verbose_name_plural = "Itens de configuração (CMDB)"
        ordering = ["patrimonio"]

    def __str__(self):
        return f"{self.patrimonio} — {self.get_categoria_display()} {self.marca} {self.modelo}"


class Ticket(models.Model):
    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        EM_ATENDIMENTO = "em_atendimento", "Em atendimento"
        FECHADO = "fechado", "Fechado"

    class Impacto(models.TextChoices):
        APENAS_EU = "apenas_eu", "Apenas eu"
        MEU_DEPARTAMENTO = "meu_departamento", "Meu departamento"
        EMPRESA_INTEIRA = "empresa_inteira", "Empresa inteira"

    categoria_sugerida = models.ForeignKey(
        Categoria, on_delete=models.PROTECT,
        related_name="tickets_como_sugerida",
        help_text="Categoria selecionada pelo usuário solicitante ao abrir o ticket",
    )
    categoria_ia = models.ForeignKey(
        Categoria, on_delete=models.PROTECT,
        related_name="tickets_como_classificada_ia", null=True, blank=True,
        help_text="Categoria determinada pelo modelo de IA a partir da descrição",
    )
    categoria_final = models.ForeignKey(
        Categoria, on_delete=models.PROTECT,
        related_name="tickets_como_final", null=True, blank=True,
        help_text="Categoria confirmada pelo técnico — usada no cálculo de SLA e prioridade",
    )
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT)
    impacto = models.CharField(
        max_length=20, choices=Impacto.choices, default=Impacto.APENAS_EU,
        help_text="Quem ou o que está sendo impactado pelo problema",
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets_abertos",
        help_text="Usuário autenticado que abriu o chamado, usado para a tela \"Meus chamados\"",
    )
    solicitante_nome = models.CharField(max_length=150)
    solicitante_ramal = models.CharField(max_length=20)
    solicitante_sala = models.CharField(max_length=100)
    solicitante_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text="IP do computador usado para abrir o chamado, capturado automaticamente",
    )
    item_configuracao = models.ForeignKey(
        ItemConfiguracao, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Equipamento do CMDB relacionado ao ticket, quando aplicável",
    )
    movimentacao_confirmada = models.BooleanField(
        default=False,
        help_text="Marcado quando o técnico registra uma movimentação de equipamento "
                   "ou confirma explicitamente que não houve nenhuma — exigido para fechar o chamado",
    )
    tecnico_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets_atribuidos",
        limit_choices_to={"is_staff": True},
        help_text="Técnico responsável pelo atendimento deste chamado",
    )
    descricao = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ABERTO
    )
    prioridade_calculada = models.PositiveSmallIntegerField(null=True, blank=True)
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-prioridade_calculada", "data_abertura"]

    def __str__(self):
        return f"Ticket #{self.pk} — {self.setor}"


class ComentarioTicket(models.Model):
    """Troca de informações entre técnicos: atualizações, diagnóstico,
    procedimento adotado — histórico interno do atendimento."""

    class Tipo(models.TextChoices):
        NOTA_INTERNA = "nota_interna", "Nota interna"
        RESPOSTA_USUARIO = "resposta_usuario", "Resposta ao usuário"
        DESFECHO = "desfecho", "Desfecho/solução final"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.NOTA_INTERNA)
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comentário do ticket"
        verbose_name_plural = "Comentários do ticket"
        ordering = ["criado_em"]

    def __str__(self):
        return f"Comentário de {self.autor} em #{self.ticket_id}"


class Notificacao(models.Model):
    """Aviso in-app pro solicitante: mudança de status do chamado ou resposta/
    desfecho do técnico. Fica guardada mesmo depois de lida — só o campo
    `lida` muda, pra manter o histórico completo disponível pro usuário."""

    class Tipo(models.TextChoices):
        MUDANCA_STATUS = "mudanca_status", "Mudança de status"
        NOVO_COMENTARIO = "novo_comentario", "Novo comentário"

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificacoes"
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="notificacoes")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    mensagem = models.CharField(max_length=255)
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    lida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Notificação para {self.destinatario} — chamado #{self.ticket_id}"


class MovimentacaoEquipamento(models.Model):
    """Histórico de cada movimentação de equipamento registrada num ticket —
    inclusive quando o técnico confirma que não houve nenhuma (RN27)."""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="movimentacoes_equipamento"
    )
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    equipamento_saida = models.ForeignKey(
        ItemConfiguracao, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimentacoes_como_saida",
    )
    equipamento_entrada = models.ForeignKey(
        ItemConfiguracao, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimentacoes_como_entrada",
    )
    sem_movimentacao = models.BooleanField(default=False)
    aplicada = models.BooleanField(
        default=False,
        help_text="Marcado quando a movimentação é efetivamente aplicada ao CMDB — "
                   "isso só acontece quando o chamado é fechado, não no momento do registro",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação de equipamento"
        verbose_name_plural = "Movimentações de equipamento"
        ordering = ["-criado_em"]

    def descricao(self):
        if self.sem_movimentacao:
            return "Confirmado: nenhuma movimentação de equipamento foi necessária."
        verbo_saida = "retornou" if self.aplicada else "vai retornar"
        verbo_entrada = "foi vinculado" if self.aplicada else "será vinculado"
        partes = []
        if self.equipamento_saida:
            partes.append(f"{self.equipamento_saida.patrimonio} {verbo_saida} para a informática")
        if self.equipamento_entrada:
            partes.append(f"{self.equipamento_entrada.patrimonio} {verbo_entrada} ao chamado")
        return ("; ".join(partes) + ".").capitalize()

    def __str__(self):
        return f"Movimentação #{self.pk} do ticket #{self.ticket_id}"


class HistoricoSLA(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE)
    tempo_real = models.DecimalField(max_digits=8, decimal_places=2)
    tempo_esperado = models.DecimalField(max_digits=8, decimal_places=2)
    desvio = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = "Histórico de SLA"
        verbose_name_plural = "Históricos de SLA"

    def __str__(self):
        return f"SLA do ticket #{self.ticket_id}"


class ParametroSistema(models.Model):
    """Parâmetros e limiares configuráveis, lidos pela camada de negócio."""

    chave = models.CharField(max_length=100, primary_key=True)
    valor = models.CharField(max_length=255)
    descricao = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Parâmetro do sistema"
        verbose_name_plural = "Parâmetros do sistema"

    def __str__(self):
        return f"{self.chave} = {self.valor}"


class RegraRecomendacao(models.Model):
    tipo_desvio = models.CharField(max_length=100)
    condicao = models.CharField(
        max_length=255,
        help_text="Descrição da condição que dispara esta regra, "
                   "referenciando chaves de ParametroSistema",
    )
    acao_sugerida = models.TextField()

    class Meta:
        verbose_name = "Regra de recomendação"
        verbose_name_plural = "Regras de recomendação"

    def __str__(self):
        return self.tipo_desvio


class Recomendacao(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE)
    regra = models.ForeignKey(RegraRecomendacao, on_delete=models.PROTECT)
    data_gerada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Recomendação"
        verbose_name_plural = "Recomendações"
        ordering = ["-data_gerada"]

    def __str__(self):
        return f"{self.regra} — {self.categoria} @ {self.setor}"


class ArtigoConhecimento(models.Model):
    """Tutorial ou artigo da base de conhecimento interna da equipe de TI."""

    titulo = models.CharField(max_length=200)
    resumo = models.CharField(
        max_length=300, blank=True,
        help_text="Breve resumo exibido na listagem (opcional)",
    )
    conteudo = models.TextField(help_text="Corpo do artigo ou tutorial")
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="artigos",
        help_text="Categoria de chamado relacionada, se aplicável",
    )
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Artigo da base de conhecimento"
        verbose_name_plural = "Artigos da base de conhecimento"
        ordering = ["-atualizado_em"]

    def __str__(self):
        return self.titulo