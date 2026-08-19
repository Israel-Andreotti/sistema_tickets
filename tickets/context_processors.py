from .models import Setor


def papel_usuario(request):
    user = request.user
    eh_gestor = (
        user.is_authenticated
        and not user.is_staff
        and Setor.objects.filter(gestor=user).exists()
    )

    # Acesso operacional pleno (fila, histórico, base de conhecimento, SLA):
    # técnicos, gestores de setor e superusuários. Só o Django admin (/admin/)
    # continua exclusivo a superusuários.
    pode_ver_slas = user.is_authenticated and (user.is_staff or user.is_superuser or eh_gestor)

    return {"eh_gestor": eh_gestor, "pode_ver_slas": pode_ver_slas}
