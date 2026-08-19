"""RN15-17: geração de recomendação.

RN15 — RegraRecomendacao mapeia um tipo_desvio ("atencao"/"critico") para uma ação
        sugerida; esse mapeamento é editável via banco, não fixado no código.
RN16 — quando o desvio agregado de uma combinação categoria+setor ultrapassa o
        limiar de uma regra (e tem volume mínimo de tickets para ser relevante),
        gera-se uma Recomendacao vinculada a essa categoria, setor e regra.
RN17 — não duplicar: se já existe uma Recomendacao recente (dentro da janela de
        agregação) para a mesma combinação categoria+setor+regra, não gerar outra.
"""
from datetime import timedelta

from django.utils import timezone

from ..models import Recomendacao, RegraRecomendacao
from .desvio import agregar_desvios_por_categoria_setor
from .parametros import get_parametro


def gerar_recomendacoes(janela_dias: int | None = None) -> list[Recomendacao]:
    min_tickets = get_parametro("min_tickets_para_recomendacao", default=5, cast=int)
    janela_dias = janela_dias or get_parametro(
        "janela_recomendacao_dias", default=30, cast=int
    )
    desde = timezone.now() - timedelta(days=janela_dias)

    geradas = []
    for agregacao in agregar_desvios_por_categoria_setor(janela_dias):
        if agregacao["tipo_desvio"] is None:
            continue
        if agregacao["quantidade_tickets"] < min_tickets:
            continue

        try:
            regra = RegraRecomendacao.objects.get(tipo_desvio=agregacao["tipo_desvio"])
        except RegraRecomendacao.DoesNotExist:
            continue

        ja_existe = Recomendacao.objects.filter(
            categoria_id=agregacao["categoria_id"],
            setor_id=agregacao["setor_id"],
            regra=regra,
            data_gerada__gte=desde,
        ).exists()
        if ja_existe:
            continue

        recomendacao = Recomendacao.objects.create(
            categoria_id=agregacao["categoria_id"],
            setor_id=agregacao["setor_id"],
            regra=regra,
        )
        geradas.append(recomendacao)

    return geradas
