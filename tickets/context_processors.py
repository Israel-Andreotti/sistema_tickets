from .models import Notificacao
from .services.permissoes import e_gestor_da_ti, tem_acesso_operacional


def papel_usuario(request):
    user = request.user
    eh_gestor = user.is_authenticated and not user.is_staff and e_gestor_da_ti(user)

    # Mesma regra usada pelas views (tecnico_required) pra decidir o que
    # aparece no menu — antes cada lado tinha sua própria conta e ficaram
    # dessincronizados quando o critério de "gestor" mudou de "qualquer
    # setor" para "só o setor de TI".
    pode_ver_slas = tem_acesso_operacional(user)

    notificacoes_nao_lidas = (
        Notificacao.objects.filter(destinatario=user, lida=False).count()
        if user.is_authenticated else 0
    )

    return {
        "eh_gestor": eh_gestor,
        "pode_ver_slas": pode_ver_slas,
        "notificacoes_nao_lidas": notificacoes_nao_lidas,
    }
