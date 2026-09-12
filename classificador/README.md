# Classificador de chamados (mDeBERTa zero-shot)

Serviço HTTP que classifica a descrição de um chamado em uma das categorias do
catálogo, usando o modelo `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`. Roda
separado do Django — ver `tickets/services/ia.py` do lado do sistema.

## Por que separado do Django

- o Django não precisa de `torch`/`transformers` no `requirements.txt`, e o
  deploy do sistema continua leve (só os pesos passam de 1 GB);
- o modelo é carregado **uma vez** na memória deste serviço, em vez de uma
  cópia por worker do servidor web;
- este serviço pode rodar noutra máquina — inclusive numa com mais memória que
  o servidor do sistema.

## Por que zero-shot

O hospital não tem uma base histórica de chamados rotulados para treinar um
classificador supervisionado. E mesmo que tivesse: o catálogo de categorias é
editável pelo Admin, então um modelo treinado precisaria ser retreinado a cada
categoria nova.

O zero-shot recebe as categorias como texto a cada chamada — uma categoria
criada agora no Admin já é classificável na abertura do próximo chamado, sem
retreino e sem mexer neste serviço.

O modelo é de **NLI** (inferência de linguagem natural). Para cada categoria
candidata, ele avalia o quanto a descrição do chamado (premissa) implica a
hipótese *"Este chamado de suporte de TI é sobre {categoria}"*. A categoria com
maior probabilidade vence.

## Como rodar

```bash
python -m venv .venv-ia
.venv-ia\Scripts\activate           # Windows
pip install -r classificador/requirements.txt

uvicorn classificador.servico:app --host 0.0.0.0 --port 8001
```

A primeira execução baixa ~1,1 GB de pesos do Hugging Face para
`~/.cache/huggingface`. Depois disso o serviço roda offline.

Com o venv já criado, `start_dev.bat` (na raiz do projeto) sobe este serviço
junto com o Django, cada um na sua janela.

Aponte o Django para ele no `.env`:

```
IA_CLASSIFICADOR_URL=http://localhost:8001/classificar
IA_CLASSIFICADOR_TIMEOUT=30
```

Sem essa variável, o sistema roda normalmente — apenas sem o palpite da IA na
dupla checagem.

### Aquecer antes de liberar

O modelo só é carregado na primeira requisição, que por isso demora bem mais
que as demais. Para carregá-lo antecipadamente:

```bash
curl http://localhost:8001/pronto
```

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/saude` | Diz que o serviço está de pé, **sem** carregar o modelo |
| `GET` | `/pronto` | Carrega o modelo e só responde quando ele estiver na memória |
| `POST` | `/classificar` | Classifica uma descrição |

### `POST /classificar`

O catálogo vem sempre do Django — este serviço não tem lista própria de
categorias.

```json
{
  "descricao": "a impressora da recepção não puxa papel",
  "categorias": [
    {"id": 12, "nome": "Impressora com atolamento", "grupo": "Impressora"},
    {"id": 31, "nome": "Sem acesso ao sistema", "grupo": "Acessos e permissões"}
  ]
}
```

```json
{
  "categoria_id": 12,
  "confianca": 0.87,
  "alternativas": [
    {"categoria_id": 31, "confianca": 0.04}
  ]
}
```

O campo `grupo` é enviado junto do nome porque o nome sozinho costuma ser
ambíguo para o modelo — "Sem acesso" em *Acessos e permissões* é coisa
diferente de "Sem acesso" em *Rede e telefonia*.

`alternativas` traz as três colocadas seguintes. O Django não as usa hoje; elas
servem para calibrar o limiar de confiança e para depurar escolhas estranhas.

## O limiar de confiança não fica aqui

Este serviço sempre devolve seu melhor palpite, com a confiança que ele tem.
Quem decide se o palpite é bom o bastante é o Django, lendo o parâmetro
`ia_confianca_minima` do banco (editável pelo Admin, como todas as outras
regras de negócio do projeto). Abaixo do limiar, o chamado fica sem
`categoria_ia` em vez de receber um palpite fraco.

Para calibrar: rode alguns chamados reais, olhe as `alternativas` e a confiança
do vencedor, e ajuste o parâmetro no Admin — sem tocar em código.

## Testes

```bash
pip install fastapi pydantic httpx pytest
pytest classificador/test_servico.py
```

Os testes substituem o pipeline do `transformers` por um dublê, então rodam em
menos de um segundo e não exigem os pesos do modelo. Eles verificam o contrato
HTTP e o mapeamento label → id — **não** a qualidade das classificações, que só
pode ser avaliada com o modelo real e chamados de verdade.
