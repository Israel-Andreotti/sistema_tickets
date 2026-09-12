"""Testes do serviço de classificação, sem baixar o modelo.

O pipeline do transformers é substituído por um dublê, então estes testes
rodam em segundo e não exigem os 1,1 GB de pesos — o que se verifica aqui é o
contrato HTTP e o mapeamento label → id, não a qualidade do modelo.

    pip install fastapi pydantic httpx pytest
    pytest classificador/test_servico.py
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from classificador.servico import TEMPLATE_HIPOTESE, app

CATEGORIAS = [
    {"id": 12, "nome": "Impressora com papel atolado", "grupo": "Impressora"},
    {"id": 31, "nome": "Sem acesso", "grupo": "Acessos e permissões"},
    {"id": 44, "nome": "Sem acesso", "grupo": "Rede e telefonia"},
]

cliente = TestClient(app)


@pytest.fixture
def pipeline_falso():
    """Devolve sempre o primeiro label como vencedor e registra o que recebeu."""
    recebido = {}

    def pipeline(descricao, candidate_labels, hypothesis_template, multi_label):
        recebido.update(
            descricao=descricao, labels=candidate_labels,
            template=hypothesis_template, multi_label=multi_label,
        )
        return {"labels": list(candidate_labels), "scores": [0.81, 0.12, 0.07]}

    with patch("classificador.servico.obter_pipeline", return_value=pipeline):
        yield recebido


def test_devolve_o_id_da_categoria_vencedora(pipeline_falso):
    resposta = cliente.post(
        "/classificar", json={"descricao": "a impressora atolou", "categorias": CATEGORIAS}
    )
    assert resposta.status_code == 200
    assert resposta.json()["categoria_id"] == 12
    assert resposta.json()["confianca"] == pytest.approx(0.81)


def test_devolve_as_alternativas_para_calibrar_o_limiar(pipeline_falso):
    resposta = cliente.post(
        "/classificar", json={"descricao": "a impressora atolou", "categorias": CATEGORIAS}
    )
    assert [a["categoria_id"] for a in resposta.json()["alternativas"]] == [31, 44]


def test_o_grupo_desambigua_categorias_de_mesmo_nome(pipeline_falso):
    """Duas categorias chamadas "Sem acesso" em grupos diferentes precisam virar
    labels distintos — se colidissem, o mapa label→id perderia uma delas e o
    serviço devolveria o id errado."""
    cliente.post(
        "/classificar", json={"descricao": "não consigo entrar", "categorias": CATEGORIAS}
    )
    labels = pipeline_falso["labels"]
    assert len(set(labels)) == len(CATEGORIAS)
    assert "Sem acesso (Acessos e permissões)" in labels
    assert "Sem acesso (Rede e telefonia)" in labels


def test_usa_o_template_em_portugues_e_rotulo_unico(pipeline_falso):
    cliente.post("/classificar", json={"descricao": "teste", "categorias": CATEGORIAS})
    assert pipeline_falso["template"] == TEMPLATE_HIPOTESE
    # multi_label=False faz as categorias competirem entre si, que é a leitura
    # que o limiar de confiança do Django espera.
    assert pipeline_falso["multi_label"] is False


def test_descricao_vazia_nao_chega_a_incomodar_o_modelo(pipeline_falso):
    resposta = cliente.post("/classificar", json={"descricao": "   ", "categorias": CATEGORIAS})
    assert resposta.json()["categoria_id"] is None
    assert pipeline_falso == {}


def test_catalogo_vazio_e_rejeitado():
    resposta = cliente.post("/classificar", json={"descricao": "x", "categorias": []})
    assert resposta.status_code == 422


def test_saude_nao_carrega_o_modelo():
    """/saude tem que responder mesmo antes de o modelo estar na memória —
    é o que permite checar se o processo subiu sem esperar o carregamento."""
    resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"
