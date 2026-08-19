"""RN11-14: detecção de desvio de SLA.

RN11 — o desvio percentual de um ticket é (tempo_real - tempo_esperado) / tempo_esperado.
RN12 — os limiares que classificam um desvio (ex: % de estouro) vêm de ParametroSistema,
        nunca fixados no código.
RN13 — cada desvio é classificado em "atencao", "critico", ou None (dentro do SLA).
RN14 — desvios são agregados por categoria + setor (não por ticket isolado, nem só
        por categoria) numa janela de tempo, para alimentar a recomendação (RN15-17).
"""
from datetime import timedelta

from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField
from django.utils import timezone

from ..models import HistoricoSLA
from .parametros import get_parametro


def classificar_desvio(percentual: float) -> str | None:
    """RN12-13: classifica um desvio percentual conforme limiares configuráveis."""
    limiar_atencao = get_parametro("desvio_atencao_pct", default=20, cast=float)
    limiar_critico = get_parametro("desvio_critico_pct", default=50, cast=float)

    if percentual >= limiar_critico:
        return "critico"
    if percentual >= limiar_atencao:
        return "atencao"
    return None


def agregar_desvios_por_categoria_setor(janela_dias: int | None = None) -> list[dict]:
    """RN14: desvio percentual médio por (categoria_final, setor) na janela informada.

    Retorna uma lista de dicts com categoria_id, setor_id, percentual_medio,
    quantidade_tickets e tipo_desvio (resultado de classificar_desvio).
    """
    janela_dias = janela_dias or get_parametro(
        "janela_recomendacao_dias", default=30, cast=int
    )
    desde = timezone.now() - timedelta(days=janela_dias)

    percentual_expr = ExpressionWrapper(
        F("desvio") / F("tempo_esperado") * 100.0, output_field=FloatField()
    )

    linhas = (
        HistoricoSLA.objects
        .filter(
            ticket__data_fechamento__gte=desde,
            ticket__categoria_final__isnull=False,
        )
        .values("ticket__categoria_final", "ticket__setor")
        .annotate(percentual_medio=Avg(percentual_expr), quantidade_tickets=Count("id"))
    )

    return [
        {
            "categoria_id": linha["ticket__categoria_final"],
            "setor_id": linha["ticket__setor"],
            "percentual_medio": linha["percentual_medio"],
            "quantidade_tickets": linha["quantidade_tickets"],
            "tipo_desvio": classificar_desvio(linha["percentual_medio"]),
        }
        for linha in linhas
    ]
