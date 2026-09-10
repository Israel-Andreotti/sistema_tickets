"""Recuperação de senha por código temporário enviado por e-mail — em vez do
link com token do PasswordResetView padrão do Django, porque o sistema roda
na rede interna do hospital e não tem um domínio público pra esse link
apontar. O código de 6 dígitos é validado manualmente pelo usuário na tela
seguinte (ver views.py: esqueci_senha_view, confirmar_codigo_view)."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from ..models import CodigoRecuperacaoSenha

VALIDADE_MINUTOS = 15


def solicitar_codigo(usuario):
    """Invalida qualquer código anterior em aberto do usuário, gera um novo
    código de 6 dígitos e envia por e-mail. Levanta ValueError se o usuário
    não tiver e-mail cadastrado."""
    if not usuario.email:
        raise ValueError("Este usuário não tem e-mail cadastrado.")

    CodigoRecuperacaoSenha.objects.filter(
        usuario=usuario, usado_em__isnull=True
    ).update(usado_em=timezone.now())

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    registro = CodigoRecuperacaoSenha.objects.create(
        usuario=usuario,
        codigo=codigo,
        expira_em=timezone.now() + timedelta(minutes=VALIDADE_MINUTOS),
    )

    send_mail(
        subject="Código de recuperação de senha — Chamados de TI",
        message=(
            f"Olá, {usuario.get_full_name() or usuario.username}!\n\n"
            f"Seu código de recuperação de senha é: {codigo}\n\n"
            f"Ele é válido por {VALIDADE_MINUTOS} minutos e só pode ser usado uma vez.\n\n"
            "Se você não solicitou essa recuperação, ignore este e-mail."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
    )
    return registro


def validar_codigo(usuario, codigo):
    """Confirma o código informado e marca como usado. Retorna True se o
    código existe, pertence ao usuário, não expirou e ainda não foi usado."""
    agora = timezone.now()
    registro = (
        CodigoRecuperacaoSenha.objects
        .filter(usuario=usuario, codigo=codigo, usado_em__isnull=True, expira_em__gt=agora)
        .order_by("-criado_em")
        .first()
    )
    if registro is None:
        return False

    registro.usado_em = agora
    registro.save(update_fields=["usado_em"])
    return True
