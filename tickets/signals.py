from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ParametroSistema
from .services.parametros import invalidar_cache_parametro


@receiver(post_save, sender=ParametroSistema)
@receiver(post_delete, sender=ParametroSistema)
def limpar_cache_parametro(sender, instance, **kwargs):
    invalidar_cache_parametro(instance.chave)
