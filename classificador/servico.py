"""Serviço de classificação zero-shot de chamados de TI.

Carrega o mDeBERTa-v3-base-mnli-xnli uma vez, na subida, e expõe um único
endpoint que o Django consome (ver tickets/services/ia.py).

Por que zero-shot: o hospital não tem uma base histórica de chamados rotulados
para treinar um classificador supervisionado — e mesmo que tivesse, o catálogo
de categorias muda pelo Admin, e um modelo treinado teria que ser retreinado a
cada mudança. O zero-shot recebe as categorias como texto a cada chamada, então
uma categoria criada hoje no Admin já é classificável agora, sem retreino.

Como funciona: o modelo é de NLI (natural language inference). Para cada
categoria candidata, ele avalia se a descrição do chamado (premissa) implica a
hipótese "Este chamado é sobre {categoria}". A categoria com maior probabilidade
de implicação vence.

Rodar:
    pip install -r classificador/requirements.txt
    uvicorn classificador.servico:app --host 0.0.0.0 --port 8001

A primeira execução baixa ~1,1 GB de pesos do Hugging Face e guarda em cache
(~/.cache/huggingface). Depois disso, roda offline.
"""
import logging
import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel, Field

logger = logging.getLogger("classificador")

MODELO = os.environ.get("MODELO_IA", "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")

# O template é o que transforma cada categoria numa hipótese de NLI. Em
# português, e explicitando "chamado de TI", porque o modelo é multilíngue e
# sem isso tende a ancorar no inglês genérico.
TEMPLATE_HIPOTESE = "Este chamado de suporte de TI é sobre {}."

app = FastAPI(title="Classificador de chamados de TI", version="1.0")


class CategoriaCandidata(BaseModel):
    id: int
    nome: str
    grupo: str | None = None

    def como_label(self) -> str:
        """O nome sozinho costuma ser ambíguo ("Sem acesso", "Lentidão"); o
        grupo é justamente o contexto que desambigua."""
        return f"{self.nome} ({self.grupo})" if self.grupo else self.nome


class PedidoClassificacao(BaseModel):
    descricao: str
    categorias: list[CategoriaCandidata] = Field(min_length=1)


class RespostaClassificacao(BaseModel):
    categoria_id: int | None
    confianca: float
    alternativas: list[dict] = []


@lru_cache(maxsize=1)
def obter_pipeline():
    """Carrega o modelo uma única vez, na primeira requisição.

    Fica fora do import para o processo subir rápido e para os testes poderem
    importar este módulo sem baixar 1 GB de pesos.
    """
    from transformers import pipeline

    logger.info("Carregando o modelo %s — a primeira vez pode demorar.", MODELO)
    return pipeline("zero-shot-classification", model=MODELO)


@app.get("/saude")
def saude():
    """Usado para checar se o serviço está de pé sem disparar o carregamento
    do modelo (que é o que `pronto` faz)."""
    return {"status": "ok", "modelo": MODELO}


@app.get("/pronto")
def pronto():
    """Força o carregamento do modelo e só responde quando ele estiver na
    memória — útil para aquecer o serviço antes de liberar o sistema."""
    obter_pipeline()
    return {"status": "pronto", "modelo": MODELO}


@app.post("/classificar", response_model=RespostaClassificacao)
def classificar(pedido: PedidoClassificacao):
    descricao = pedido.descricao.strip()
    if not descricao:
        return RespostaClassificacao(categoria_id=None, confianca=0.0)

    # O Django manda o catálogo inteiro a cada chamada; o mapa devolve do label
    # (texto) para o id, já que o modelo raciocina sobre texto e o Django
    # precisa de id.
    labels = [categoria.como_label() for categoria in pedido.categorias]
    label_para_id = {
        categoria.como_label(): categoria.id for categoria in pedido.categorias
    }

    resultado = obter_pipeline()(
        descricao,
        candidate_labels=labels,
        hypothesis_template=TEMPLATE_HIPOTESE,
        # multi_label=False faz as probabilidades competirem entre si (softmax
        # sobre as categorias) em vez de cada uma valer por si. É o que
        # queremos: o chamado pertence a UMA categoria, e assim a confiança do
        # vencedor já embute o quanto ele ganhou das outras — que é a leitura
        # que o limiar do Django faz.
        multi_label=False,
    )

    vencedor = resultado["labels"][0]
    confianca = float(resultado["scores"][0])

    return RespostaClassificacao(
        categoria_id=label_para_id.get(vencedor),
        confianca=confianca,
        # As próximas colocadas ajudam a calibrar o limiar e a depurar
        # ("por que ele escolheu essa?") — o Django hoje só lê as duas
        # primeiras chaves, então isto é informação de diagnóstico.
        alternativas=[
            {"categoria_id": label_para_id.get(label), "confianca": float(score)}
            for label, score in zip(resultado["labels"][1:4], resultado["scores"][1:4])
        ],
    )
