"""RN01-04: dupla checagem de classificação do ticket.

RN01 — o solicitante escolhe uma categoria (categoria_sugerida) ao abrir o ticket.
RN02 — a IA analisa a descrição e determina sua própria categoria (categoria_ia),
        independente da escolha do solicitante.
RN03 — o técnico vê as duas lado a lado e confirma/corrige a classificação final.
RN04 — apenas categoria_final alimenta cálculo de SLA e prioridade.
"""
from ..models import Categoria, ItemConfiguracao, Setor, Ticket
from .prioridade import calcular_prioridade


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
    """RN01: registra a categoria escolhida pelo solicitante e seus dados de contato."""
    return Ticket.objects.create(
        categoria_sugerida=categoria_sugerida,
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
    if ticket.status == Ticket.Status.ABERTO:
        ticket.status = Ticket.Status.EM_ATENDIMENTO
    ticket.save(update_fields=["tecnico_responsavel", "status"])
    return ticket


def confirmar_classificacao_final(ticket: Ticket, categoria_final: Categoria) -> Ticket:
    """RN03-04: o técnico confirma (ou corrige) a categoria final do ticket.

    Isso já dispara o recálculo de prioridade (RN05-07), pois é a categoria_final
    que passa a valer para SLA e prioridade a partir deste ponto.
    """
    ticket.categoria_final = categoria_final
    ticket.prioridade_calculada = calcular_prioridade(categoria_final, ticket.setor)
    if ticket.status == Ticket.Status.ABERTO:
        ticket.status = Ticket.Status.EM_ATENDIMENTO
    ticket.save(update_fields=["categoria_final", "prioridade_calculada", "status"])
    return ticket
