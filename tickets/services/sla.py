"""RN08-10: controle de SLA.

RN08 — o tempo esperado de atendimento vem do sla_horas da categoria_final.
RN09 — o tempo real é medido entre data_abertura e data_fechamento do ticket,
       descontado qualquer tempo em que o chamado ficou com o SLA pausado
       (ver services/pausa.py) — tempo esperando fornecedor/peça/usuário não
       conta contra a equipe interna.
RN10 — ao fechar o ticket, o sistema grava um HistoricoSLA com tempo_real,
        tempo_esperado, tempo_pausado e o desvio entre tempo_real e tempo_esperado.

Fechar um chamado também exige categoria_final confirmada, técnico responsável
atribuído, movimentação de equipamento resolvida (registrada ou confirmada
como desnecessária) e nenhuma pausa de SLA em aberto — e é o momento em que
qualquer movimentação pendente (ver services/equipamento.py) é efetivamente
aplicada ao CMDB.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import HistoricoSLA, Notificacao, Ticket
from .equipamento import aplicar_movimentacoes_pendentes
from .notificacoes import notificar
from .pausa import tempo_pausado_total


def prazo_ajustado(ticket: Ticket, *, referencia=None):
    """Prazo do SLA já deslocado pelo tempo total pausado até `referencia`
    (por padrão, agora) — usado na fila e no dashboard no lugar do cálculo
    cru `data_abertura + sla_horas`, pra pausa não contar contra o prazo."""
    categoria_referencia = ticket.categoria_final or ticket.categoria_sugerida
    prazo_base = ticket.data_abertura + timedelta(hours=float(categoria_referencia.sla_horas))
    return prazo_base + tempo_pausado_total(ticket, referencia=referencia)


def percentual_sla_consumido(ticket: Ticket, *, referencia=None) -> int:
    """% do SLA já consumido, descontando o tempo pausado — usado na barra
    de progresso da fila."""
    referencia = referencia or timezone.now()
    categoria_referencia = ticket.categoria_final or ticket.categoria_sugerida
    sla_horas = float(categoria_referencia.sla_horas)
    if not sla_horas:
        return 100
    decorrido = (referencia - ticket.data_abertura) - tempo_pausado_total(ticket, referencia=referencia)
    return round(min(100, max(0, decorrido.total_seconds() / 3600 / sla_horas * 100)))


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
    if ticket.status == Ticket.Status.PAUSADO:
        raise ValueError(
            "Retome o chamado (encerre a pausa de SLA) antes de fechá-lo."
        )

    with transaction.atomic():
        aplicar_movimentacoes_pendentes(ticket)

        ticket.data_fechamento = data_fechamento or timezone.now()
        ticket.status = Ticket.Status.FECHADO
        ticket.save(update_fields=["data_fechamento", "status"])

        tempo_pausado_horas = tempo_pausado_total(
            ticket, referencia=ticket.data_fechamento
        ).total_seconds() / 3600
        tempo_real = (
            (ticket.data_fechamento - ticket.data_abertura).total_seconds() / 3600
            - tempo_pausado_horas
        )
        tempo_esperado = float(ticket.categoria_final.sla_horas)
        desvio = tempo_real - tempo_esperado

        historico, _ = HistoricoSLA.objects.update_or_create(
            ticket=ticket,
            defaults={
                "tempo_real": round(tempo_real, 2),
                "tempo_esperado": round(tempo_esperado, 2),
                "tempo_pausado": round(tempo_pausado_horas, 2),
                "desvio": round(desvio, 2),
            },
        )
        notificar(
            ticket, Notificacao.Tipo.MUDANCA_STATUS,
            f"Seu chamado {ticket.codigo} foi fechado.",
        )
    return historico
