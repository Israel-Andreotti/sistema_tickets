"""Criação de contas de usuário a partir de um chamado — hoje só usada pela
categoria "Criação de usuário (admissão)" (ver Categoria.habilita_criacao_usuario),
que substitui o passo manual (o técnico criava a conta direto no AD/sistema
clínico e só registrava o desfecho por comentário).
"""
from django.contrib.auth import get_user_model

from ..models import Ticket


def criar_usuario_admissao(
    ticket: Ticket, *, first_name: str, last_name: str, username: str, email: str,
):
    """Cria a conta vinculada ao chamado que a originou. A conta nasce com
    senha inutilizável — a pessoa define a própria pela tela de
    recuperação de senha (services/recuperacao_senha.py), que exige e-mail
    cadastrado; por isso a conta nunca fica com uma senha que o técnico
    escolheu ou conhece."""
    if ticket.usuario_criado_id:
        raise ValueError("Este chamado já tem um usuário criado.")

    usuario = get_user_model().objects.create_user(
        username=username, first_name=first_name, last_name=last_name,
        email=email, is_staff=False,
    )
    usuario.set_unusable_password()
    usuario.save(update_fields=["password"])

    ticket.usuario_criado = usuario
    ticket.save(update_fields=["usuario_criado"])
    return usuario
