"""Regra de acesso operacional do sistema, num único lugar porque ela é
consultada tanto pelas views (pra decidir se libera a ação) quanto pelo
context processor (pra decidir se mostra o link no menu) — tê-la em dois
lugares foi exatamente o que causou o menu mostrar links que a view barrava
em seguida (ver histórico do projeto)."""
from ..models import Setor
from .equipamento import obter_setor_ti
from .parametros import ParametroNaoConfigurado


def e_gestor_da_ti(user):
    """Gestor do setor de TI — na prática, o administrador do sistema. Ser
    gestor de qualquer outro setor não dá nenhum acesso especial: essa
    pessoa é um usuário comum, que só enxerga os próprios chamados."""
    try:
        setor_ti_id = obter_setor_ti().pk
    except (ParametroNaoConfigurado, Setor.DoesNotExist):
        return False
    return Setor.objects.filter(pk=setor_ti_id, gestor=user).exists()


def tem_acesso_operacional(user):
    """Acesso operacional pleno ao sistema — fila, histórico, base de
    conhecimento, SLA por categoria e ações em chamados: técnicos, gestor da
    TI e superusuários. O Django admin (/admin/) é a única área que continua
    exclusiva a superusuários (is_staff sozinho não concede acesso a ele)."""
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or e_gestor_da_ti(user)
    )
