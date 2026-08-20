from django.core.cache import cache

from ..models import ParametroSistema

# Parâmetros mudam raramente (são configuração, editada via admin), mas
# get_parametro é chamado por ticket/linha em vários laços (classificação de
# desvio, recomendação, equipamento) — sem cache isso vira N+1 query. O TTL
# é só uma rede de segurança; a invalidação de verdade é via signal logo
# abaixo, disparada assim que o parâmetro é salvo/apagado.
TIMEOUT_CACHE_PARAMETRO = 60 * 15
PREFIXO_CACHE_PARAMETRO = "parametro_sistema"


class ParametroNaoConfigurado(Exception):
    """Levantada quando uma chave obrigatória não existe em ParametroSistema."""


def _chave_cache(chave: str) -> str:
    return f"{PREFIXO_CACHE_PARAMETRO}:{chave}"


def get_parametro(chave: str, *, default=None, cast=str):
    """Lê um valor de ParametroSistema, com cast opcional.

    Toda regra numérica (limiares de desvio, janelas de tempo, etc.) deve
    vir daqui, nunca de uma constante no código — é o requisito central do
    projeto: nada fixado na aplicação.
    """
    valor_bruto = cache.get(_chave_cache(chave))
    if valor_bruto is None:
        try:
            valor_bruto = ParametroSistema.objects.get(chave=chave).valor
        except ParametroSistema.DoesNotExist:
            if default is None:
                raise ParametroNaoConfigurado(
                    f"Parâmetro obrigatório '{chave}' não encontrado em ParametroSistema."
                )
            return default
        cache.set(_chave_cache(chave), valor_bruto, TIMEOUT_CACHE_PARAMETRO)
    return cast(valor_bruto)


def invalidar_cache_parametro(chave: str) -> None:
    cache.delete(_chave_cache(chave))
