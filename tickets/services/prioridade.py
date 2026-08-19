"""RN05-07: cálculo de prioridade do ticket.

RN05 — prioridade = peso_categoria × peso_setor.
RN06 — uma ExcecaoPrioridade para a combinação (categoria, setor), quando existir,
        substitui o cálculo padrão por um peso manual.
RN07 — a prioridade é recalculada sempre que a categoria_final do ticket é
        confirmada/alterada (ver services.classificacao.confirmar_classificacao_final).
"""
from ..models import Categoria, ExcecaoPrioridade, Setor


def calcular_prioridade(categoria: Categoria, setor: Setor) -> int:
    excecao = ExcecaoPrioridade.objects.filter(categoria=categoria, setor=setor).first()
    if excecao is not None:
        return excecao.peso_override
    return categoria.peso_categoria * setor.peso_setor
