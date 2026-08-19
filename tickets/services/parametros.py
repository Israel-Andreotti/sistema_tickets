from ..models import ParametroSistema


class ParametroNaoConfigurado(Exception):
    """Levantada quando uma chave obrigatória não existe em ParametroSistema."""


def get_parametro(chave: str, *, default=None, cast=str):
    """Lê um valor de ParametroSistema, com cast opcional.

    Toda regra numérica (limiares de desvio, janelas de tempo, etc.) deve
    vir daqui, nunca de uma constante no código — é o requisito central do
    projeto: nada fixado na aplicação.
    """
    try:
        valor = ParametroSistema.objects.get(chave=chave).valor
    except ParametroSistema.DoesNotExist:
        if default is None:
            raise ParametroNaoConfigurado(
                f"Parâmetro obrigatório '{chave}' não encontrado em ParametroSistema."
            )
        return default
    return cast(valor)
