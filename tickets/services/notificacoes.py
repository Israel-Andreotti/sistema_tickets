"""Notificações in-app pro solicitante: avisa sobre mudança de status do
chamado e sobre respostas/desfecho do técnico. Ficam guardadas mesmo depois
de lidas — o campo `lida` é o que controla o que aparece como pendente."""

from django.contrib.auth import get_user_model
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


def notificar_tecnicos_nivel(ticket: Ticket, nivel: str, mensagem: str, *, excluir=None) -> list[Notificacao]:
    """Avisa todo técnico ativo cujo PerfilTecnico é desse nível — usado
    quando um chamado é escalado, pra quem atende aquele nível saber que
    tem um chamado novo esperando. `excluir`, se informado, não recebe (o
    próprio técnico que acabou de escalar não precisa ser avisado)."""
    tecnicos = get_user_model().objects.filter(
        is_staff=True, is_active=True, perfil_tecnico__nivel_atendimento=nivel,
    )
    if excluir is not None:
        tecnicos = tecnicos.exclude(pk=excluir.pk)
    return [
        Notificacao.objects.create(
            destinatario=tecnico, ticket=ticket, tipo=Notificacao.Tipo.ESCALONAMENTO, mensagem=mensagem,
        )
        for tecnico in tecnicos
    ]


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
