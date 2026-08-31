"""Numeração sequencial independente por tipo de chamado (Incidente/Requisição),
usada em Ticket.codigo (ver models.py). O incremento é atômico via
select_for_update, pra não gerar o mesmo número em criações simultâneas."""

from django.db import transaction

from ..models import ContadorChamado


def proximo_numero_sequencial(tipo: str) -> int:
    with transaction.atomic():
        contador, _ = ContadorChamado.objects.select_for_update().get_or_create(tipo=tipo)
        contador.ultimo_numero += 1
        contador.save(update_fields=["ultimo_numero"])
        return contador.ultimo_numero
