"""Pausa do SLA enquanto o chamado depende de algo externo à equipe (ver
PausaSLA.Motivo) — o tempo pausado não conta contra o SLA (services/sla.py)."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import Notificacao, PausaSLA, Ticket
from .notificacoes import notificar


def tempo_pausado_total(ticket: Ticket, *, referencia=None) -> timedelta:
    """Soma a duração de todas as pausas do chamado — uma pausa ainda aberta
    (finalizada_em nulo) conta até `referencia` (por padrão, agora)."""
    referencia = referencia or timezone.now()
    total = timedelta()
    for pausa in ticket.pausas_sla.all():
        fim = pausa.finalizada_em or referencia
        total += fim - pausa.iniciada_em
    return total


def pausar_ticket(ticket: Ticket, *, autor, motivo: str, observacao: str = "") -> PausaSLA:
    """Pausa o SLA do chamado — fica registrado como PausaSLA em aberto até
    retomar_ticket() ser chamada."""
    if ticket.status == Ticket.Status.FECHADO:
        raise ValueError("Não é possível pausar um chamado já fechado.")
    if ticket.status == Ticket.Status.PAUSADO:
        raise ValueError("Este chamado já está com o SLA pausado.")

    with transaction.atomic():
        pausa = PausaSLA.objects.create(ticket=ticket, autor=autor, motivo=motivo, observacao=observacao)
        ticket.status = Ticket.Status.PAUSADO
        ticket.save(update_fields=["status"])
        notificar(
            ticket, Notificacao.Tipo.MUDANCA_STATUS,
            f"Seu chamado {ticket.codigo} foi pausado: {pausa.get_motivo_display()}.",
        )
    return pausa


def retomar_ticket(ticket: Ticket, *, autor) -> PausaSLA:
    """Encerra a pausa em aberto do chamado e volta o status pra em atendimento."""
    if ticket.status != Ticket.Status.PAUSADO:
        raise ValueError("Este chamado não está pausado.")

    with transaction.atomic():
        pausa = (
            PausaSLA.objects.select_for_update()
            .get(ticket=ticket, finalizada_em__isnull=True)
        )
        pausa.finalizada_em = timezone.now()
        pausa.save(update_fields=["finalizada_em"])
        ticket.status = Ticket.Status.EM_ATENDIMENTO
        ticket.save(update_fields=["status"])
        notificar(
            ticket, Notificacao.Tipo.MUDANCA_STATUS,
            f"Seu chamado {ticket.codigo} voltou a ser atendido.",
        )
    return pausa
