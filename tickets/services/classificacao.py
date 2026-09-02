"""RN01-04: dupla checagem de classificação do ticket.

RN01 — o solicitante escolhe uma categoria (categoria_sugerida) ao abrir o ticket.
RN02 — a IA analisa a descrição e determina sua própria categoria (categoria_ia),
        independente da escolha do solicitante.
RN03 — o técnico vê as duas lado a lado e confirma/corrige a classificação final.
RN04 — apenas categoria_final alimenta cálculo de SLA e prioridade.
"""
from django.utils import timezone

from ..models import (
    Categoria,
    EscalonamentoTicket,
    ItemConfiguracao,
    Notificacao,
    SolicitacaoTransferencia,
    Setor,
    Ticket,
)
from .codigo import proximo_numero_sequencial
from .notificacoes import notificar, notificar_tecnicos_nivel, notificar_usuario
from .prioridade import calcular_prioridade

_ORDEM_NIVEL = [
    Categoria.NivelAtendimento.N1, Categoria.NivelAtendimento.N2, Categoria.NivelAtendimento.N3,
]


def abrir_ticket(
    *,
    categoria_sugerida: Categoria,
    setor: Setor,
    descricao: str,
    solicitante_nome: str,
    solicitante_ramal: str,
    solicitante_sala: str,
    solicitante=None,
    item_configuracao: ItemConfiguracao | None = None,
    solicitante_ip: str | None = None,
    impacto: str = Ticket.Impacto.APENAS_EU,
) -> Ticket:
    """RN01: registra a categoria escolhida pelo solicitante e seus dados de contato.

    O código do chamado (INC/REQ + número sequencial) é definido aqui, a
    partir do tipo de categoria_sugerida, e nunca recalculado depois.
    """
    return Ticket.objects.create(
        categoria_sugerida=categoria_sugerida,
        codigo_tipo=categoria_sugerida.tipo,
        codigo_numero=proximo_numero_sequencial(categoria_sugerida.tipo),
        nivel_atual=categoria_sugerida.nivel_atendimento,
        setor=setor,
        descricao=descricao,
        solicitante=solicitante,
        solicitante_nome=solicitante_nome,
        solicitante_ramal=solicitante_ramal,
        solicitante_sala=solicitante_sala,
        item_configuracao=item_configuracao,
        solicitante_ip=solicitante_ip,
        impacto=impacto,
    )


def registrar_classificacao_ia(ticket: Ticket, categoria_ia: Categoria) -> Ticket:
    """RN02: grava a categoria inferida pelo modelo de IA a partir da descrição."""
    ticket.categoria_ia = categoria_ia
    ticket.save(update_fields=["categoria_ia"])
    return ticket


def atribuir_tecnico(ticket: Ticket, tecnico) -> Ticket:
    """Atribui um técnico responsável pelo atendimento do chamado.

    Passa o chamado para "em atendimento" automaticamente, caso ainda esteja "aberto".
    """
    ticket.tecnico_responsavel = tecnico
    vai_iniciar_atendimento = ticket.status == Ticket.Status.ABERTO
    if vai_iniciar_atendimento:
        ticket.status = Ticket.Status.EM_ATENDIMENTO
    ticket.save(update_fields=["tecnico_responsavel", "status"])
    if vai_iniciar_atendimento:
        notificar(
            ticket, Notificacao.Tipo.MUDANCA_STATUS,
            f"Seu chamado {ticket.codigo} entrou em atendimento.",
        )
    return ticket


def solicitar_transferencia(ticket: Ticket, *, solicitante) -> SolicitacaoTransferencia:
    """Pede pra assumir um chamado que já tem responsável — fica pendente
    até o responsável atual aceitar ou recusar (ver
    responder_solicitacao_transferencia). Chamado sem responsável não passa
    por aqui — nesse caso é atribuição direta via atribuir_tecnico()."""
    if ticket.tecnico_responsavel_id is None:
        raise ValueError("Chamado sem responsável — atribua um técnico em vez de solicitar.")
    if ticket.tecnico_responsavel_id == solicitante.pk:
        raise ValueError("Você já é o responsável por este chamado.")
    if ticket.solicitacoes_transferencia.filter(status=SolicitacaoTransferencia.Status.PENDENTE).exists():
        raise ValueError("Já existe uma solicitação de transferência pendente para este chamado.")

    solicitacao = SolicitacaoTransferencia.objects.create(
        ticket=ticket, solicitante=solicitante, tecnico_atual=ticket.tecnico_responsavel,
    )
    notificar_usuario(
        ticket.tecnico_responsavel, ticket, Notificacao.Tipo.TRANSFERENCIA,
        f"{solicitante.get_full_name() or solicitante.username} solicitou assumir o chamado {ticket.codigo}.",
    )
    return solicitacao


def responder_solicitacao_transferencia(solicitacao: SolicitacaoTransferencia, *, aceitar: bool) -> SolicitacaoTransferencia:
    """Aceita (transfere de fato, via atribuir_tecnico) ou recusa um pedido
    de transferência — nos dois casos avisa quem pediu do resultado."""
    if solicitacao.status != SolicitacaoTransferencia.Status.PENDENTE:
        raise ValueError("Essa solicitação já foi respondida.")

    solicitacao.status = (
        SolicitacaoTransferencia.Status.ACEITA if aceitar else SolicitacaoTransferencia.Status.RECUSADA
    )
    solicitacao.respondido_em = timezone.now()
    solicitacao.save(update_fields=["status", "respondido_em"])

    if aceitar:
        atribuir_tecnico(solicitacao.ticket, solicitacao.solicitante)

    nome_atual = solicitacao.tecnico_atual.get_full_name() or solicitacao.tecnico_atual.username
    notificar_usuario(
        solicitacao.solicitante, solicitacao.ticket, Notificacao.Tipo.TRANSFERENCIA,
        f"Sua solicitação para assumir o chamado {solicitacao.ticket.codigo} foi "
        f"{'aceita' if aceitar else 'recusada'} por {nome_atual}.",
    )
    return solicitacao


def niveis_acima(nivel_atual: str) -> list[str]:
    """Níveis de atendimento acima do atual — usado pra montar as opções
    de escalonamento disponíveis (nunca é possível rebaixar nível)."""
    return _ORDEM_NIVEL[_ORDEM_NIVEL.index(nivel_atual) + 1:]


def escalar_ticket(ticket: Ticket, *, autor, novo_nivel: str, justificativa: str = "") -> EscalonamentoTicket:
    """Escala o chamado pra um nível de atendimento acima do atual (N1→N2,
    N1→N3, N2→N3) — nunca pra baixo. Grava um EscalonamentoTicket com o
    histórico completo e avisa o solicitante da mudança."""
    if _ORDEM_NIVEL.index(novo_nivel) <= _ORDEM_NIVEL.index(ticket.nivel_atual):
        raise ValueError("Só é possível escalar para um nível de atendimento acima do atual.")

    nivel_anterior = ticket.nivel_atual
    ticket.nivel_atual = novo_nivel
    ticket.save(update_fields=["nivel_atual"])

    notificar(
        ticket, Notificacao.Tipo.MUDANCA_STATUS,
        f"Seu chamado {ticket.codigo} foi escalado para nível {novo_nivel.upper()}.",
    )
    notificar_tecnicos_nivel(
        ticket, novo_nivel,
        f"O chamado {ticket.codigo} foi escalado para o seu nível de atendimento ({novo_nivel.upper()}).",
        excluir=autor,
    )

    return EscalonamentoTicket.objects.create(
        ticket=ticket, autor=autor, nivel_anterior=nivel_anterior,
        nivel_novo=novo_nivel, justificativa=justificativa,
    )


def confirmar_classificacao_final(ticket: Ticket, categoria_final: Categoria) -> Ticket:
    """RN03-04: o técnico confirma (ou corrige) a categoria final do ticket.

    Isso já dispara o recálculo de prioridade (RN05-07), pois é a categoria_final
    que passa a valer para SLA e prioridade a partir deste ponto.
    """
    ticket.categoria_final = categoria_final
    ticket.prioridade_calculada = calcular_prioridade(categoria_final, ticket.setor)
    vai_iniciar_atendimento = ticket.status == Ticket.Status.ABERTO
    if vai_iniciar_atendimento:
        ticket.status = Ticket.Status.EM_ATENDIMENTO
    ticket.save(update_fields=["categoria_final", "prioridade_calculada", "status"])
    if vai_iniciar_atendimento:
        notificar(
            ticket, Notificacao.Tipo.MUDANCA_STATUS,
            f"Seu chamado {ticket.codigo} entrou em atendimento.",
        )
    return ticket
