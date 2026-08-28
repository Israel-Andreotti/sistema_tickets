"""Notificações in-app pro solicitante: avisa sobre mudança de status do
chamado e sobre respostas/desfecho do técnico. Ficam guardadas mesmo depois
de lidas — o campo `lida` é o que controla o que aparece como pendente."""

from django.utils import timezone

from ..models import Notificacao, Ticket


def notificar(ticket: Ticket, tipo: str, mensagem: str) -> Notificacao | None:
    if ticket.solicitante_id is None:
        return None
    return Notificacao.objects.create(
        destinatario_id=ticket.solicitante_id,
        ticket=ticket,
        tipo=tipo,
        mensagem=mensagem,
    )


def marcar_como_lida(notificacao: Notificacao) -> Notificacao:
    if not notificacao.lida:
        notificacao.lida = True
        notificacao.lida_em = timezone.now()
        notificacao.save(update_fields=["lida", "lida_em"])
    return notificacao


def marcar_todas_como_lidas(usuario) -> int:
    return Notificacao.objects.filter(destinatario=usuario, lida=False).update(
        lida=True, lida_em=timezone.now()
    )
