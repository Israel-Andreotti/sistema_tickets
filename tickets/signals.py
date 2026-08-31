from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ParametroSistema, PerfilTecnico
from .services.parametros import invalidar_cache_parametro


@receiver(post_save, sender=ParametroSistema)
@receiver(post_delete, sender=ParametroSistema)
def limpar_cache_parametro(sender, instance, **kwargs):
    invalidar_cache_parametro(instance.chave)


@receiver(post_save, sender=get_user_model())
def criar_perfil_tecnico(sender, instance, **kwargs):
    """Garante que todo usuário is_staff (técnico) tenha um PerfilTecnico —
    nasce em N1, e o gestor cura pra N2/N3 depois pelo admin."""
    if instance.is_staff:
        PerfilTecnico.objects.get_or_create(usuario=instance)
