"""RN08-10: controle de SLA.

RN08 — o tempo esperado de atendimento vem do sla_horas da categoria_final.
RN09 — o tempo real é medido entre data_abertura e data_fechamento do ticket.
RN10 — ao fechar o ticket, o sistema grava um HistoricoSLA com tempo_real,
        tempo_esperado e o desvio entre os dois.

Fechar um chamado também exige categoria_final confirmada, técnico responsável
atribuído e movimentação de equipamento resolvida (registrada ou confirmada
como desnecessária) — e é o momento em que qualquer movimentação pendente
(ver services/equipamento.py) é efetivamente aplicada ao CMDB.
"""
from django.db import transaction
from django.utils import timezone

from ..models import HistoricoSLA, Ticket
from .equipamento import aplicar_movimentacoes_pendentes


def fechar_ticket(ticket: Ticket, *, data_fechamento=None) -> HistoricoSLA:
    if ticket.categoria_final is None:
        raise ValueError(
            "Ticket não pode ser fechado sem uma categoria_final confirmada pelo técnico."
        )
    if ticket.tecnico_responsavel_id is None:
        raise ValueError(
            "Ticket não pode ser fechado sem um técnico responsável atribuído."
        )
    if not ticket.movimentacao_confirmada:
        raise ValueError(
            "Registre a movimentação de equipamento ou confirme que não houve "
            "nenhuma antes de fechar o chamado."
        )

    with transaction.atomic():
        aplicar_movimentacoes_pendentes(ticket)

        ticket.data_fechamento = data_fechamento or timezone.now()
        ticket.status = Ticket.Status.FECHADO
        ticket.save(update_fields=["data_fechamento", "status"])

        tempo_real = (ticket.data_fechamento - ticket.data_abertura).total_seconds() / 3600
        tempo_esperado = float(ticket.categoria_final.sla_horas)
        desvio = tempo_real - tempo_esperado

        historico, _ = HistoricoSLA.objects.update_or_create(
            ticket=ticket,
            defaults={
                "tempo_real": round(tempo_real, 2),
                "tempo_esperado": round(tempo_esperado, 2),
                "desvio": round(desvio, 2),
            },
        )
    return historico
