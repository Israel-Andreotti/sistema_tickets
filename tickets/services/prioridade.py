"""RN05-07: cálculo de prioridade do ticket.

RN05 — prioridade = peso_categoria × peso_setor × fator_prioridade_<tipo>.
RN06 — uma ExcecaoPrioridade para a combinação (categoria, setor), quando existir,
        substitui o cálculo padrão por um peso manual (o fator de tipo não se aplica).
RN07 — a prioridade é recalculada sempre que a categoria_final do ticket é
        confirmada/alterada (ver services.classificacao.confirmar_classificacao_final).
"""
from ..models import Categoria, ExcecaoPrioridade, Setor
from .parametros import get_parametro


def calcular_prioridade(categoria: Categoria, setor: Setor) -> int:
    excecao = ExcecaoPrioridade.objects.filter(categoria=categoria, setor=setor).first()
    if excecao is not None:
        return excecao.peso_override

    chave_fator = (
        "fator_prioridade_incidente" if categoria.tipo == Categoria.Tipo.INCIDENTE
        else "fator_prioridade_requisicao"
    )
    fator = get_parametro(chave_fator, default=1.0, cast=float)
    return round(categoria.peso_categoria * setor.peso_setor * fator)
