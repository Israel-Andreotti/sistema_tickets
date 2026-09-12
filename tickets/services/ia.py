"""RN02: classificação automática da descrição do chamado pelo modelo de IA.

O modelo (mDeBERTa-v3-base zero-shot) **não** roda dentro do Django. Ele fica
num serviço HTTP separado — ver a pasta `classificador/` na raiz do projeto —
por três motivos:

- o Django não precisa de torch/transformers no requirements, e o deploy do
  sistema continua leve (o modelo sozinho passa de 1 GB);
- o modelo é carregado uma vez na memória do serviço, em vez de uma cópia por
  worker do servidor web;
- o serviço pode rodar em outra máquina — inclusive numa com mais memória que
  o servidor do sistema.

O Django conhece apenas o contrato HTTP:

    POST {IA_CLASSIFICADOR_URL}
    {"descricao": "a impressora não puxa papel",
     "categorias": [{"id": 12, "nome": "Impressora com atolamento"}, ...]}

    200 {"categoria_id": 12, "confianca": 0.87}

As categorias candidatas são sempre enviadas pelo Django a partir do banco —
o serviço não tem catálogo próprio. Assim, cadastrar uma categoria nova no
Admin já a torna classificável, sem tocar no serviço nem no código (é o mesmo
princípio das outras regras de negócio deste projeto).

Nada aqui pode derrubar a abertura de um chamado: toda falha do classificador
(serviço fora do ar, timeout, resposta malformada) é registrada em log e o
ticket simplesmente fica sem `categoria_ia`, que é o estado que o sistema já
sabia tratar — o técnico vê "ainda não classificado pela IA" na tela.
"""
import json
import logging
import threading
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.db import connection

from ..models import Categoria, Ticket
from .classificacao import registrar_classificacao_ia
from .parametros import ParametroNaoConfigurado, get_parametro

logger = logging.getLogger(__name__)

# Confiança mínima abaixo da qual o palpite da IA é descartado. Fica em
# ParametroSistema (ajustável pelo Admin), não aqui — é um limiar de negócio,
# igual aos de desvio de SLA. O default só protege a instalação que ainda não
# rodou o seed.
CHAVE_CONFIANCA_MINIMA = "ia_confianca_minima"
CONFIANCA_MINIMA_PADRAO = 0.30


class ClassificadorIndisponivel(Exception):
    """O serviço de classificação não respondeu, ou respondeu algo inesperado."""


def classificador_configurado() -> bool:
    return bool(getattr(settings, "IA_CLASSIFICADOR_URL", ""))


def _categorias_candidatas() -> list[dict]:
    """Todas as categorias do catálogo viram labels do zero-shot.

    O nome sozinho é um label pobre pro modelo ("Sem acesso" diz pouco), então
    mandamos junto o grupo — que é exatamente a informação que desambigua
    ("Sem acesso" em "Acessos e permissões" vs. em "Rede e telefonia").
    """
    return [
        {
            "id": categoria.pk,
            "nome": categoria.nome,
            "grupo": categoria.get_grupo_display(),
        }
        for categoria in Categoria.objects.all().order_by("pk")
    ]


def consultar_classificador(descricao: str, categorias: list[dict]) -> dict:
    """Faz a chamada HTTP ao serviço e devolve o corpo da resposta.

    Levanta ClassificadorIndisponivel em qualquer falha — quem chama decide o
    que fazer (em produção, ignorar; nos testes, deixar estourar).
    """
    url = getattr(settings, "IA_CLASSIFICADOR_URL", "")
    if not url:
        raise ClassificadorIndisponivel("IA_CLASSIFICADOR_URL não configurada.")

    corpo = json.dumps({"descricao": descricao, "categorias": categorias}).encode("utf-8")
    requisicao = urllib.request.Request(
        url, data=corpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    timeout = getattr(settings, "IA_CLASSIFICADOR_TIMEOUT", 30)

    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ClassificadorIndisponivel(f"Falha ao consultar {url}: {erro}") from erro
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise ClassificadorIndisponivel(f"Resposta ilegível de {url}: {erro}") from erro


def _confianca_minima() -> float:
    try:
        return get_parametro(CHAVE_CONFIANCA_MINIMA, cast=float)
    except (ParametroNaoConfigurado, ValueError):
        return CONFIANCA_MINIMA_PADRAO


def classificar_ticket(ticket: Ticket) -> Categoria | None:
    """RN02: consulta o classificador e grava o resultado no ticket.

    Devolve a Categoria gravada, ou None quando a IA não opinou, errou o
    formato ou ficou abaixo da confiança mínima. Só levanta exceção se o
    serviço estiver indisponível — o chamador em produção captura.
    """
    categorias = _categorias_candidatas()
    if not categorias:
        return None

    resposta = consultar_classificador(ticket.descricao, categorias)

    categoria_id = resposta.get("categoria_id")
    if categoria_id is None:
        logger.warning("Classificador não devolveu categoria_id para o chamado %s.", ticket.codigo)
        return None

    try:
        confianca = float(resposta.get("confianca", 0))
    except (TypeError, ValueError):
        logger.warning("Confiança ilegível do classificador para o chamado %s.", ticket.codigo)
        return None

    minima = _confianca_minima()
    if confianca < minima:
        logger.info(
            "Palpite da IA descartado para o chamado %s: confiança %.2f < mínima %.2f.",
            ticket.codigo, confianca, minima,
        )
        return None

    # O serviço pode devolver o id de uma categoria apagada entre o envio e a
    # resposta — e nada impede alguém de apontar IA_CLASSIFICADOR_URL pra um
    # serviço que inventa ids, então o id volta validado contra o banco.
    categoria = Categoria.objects.filter(pk=categoria_id).first()
    if categoria is None:
        logger.warning(
            "Classificador devolveu categoria_id=%s, que não existe no catálogo.", categoria_id
        )
        return None

    registrar_classificacao_ia(ticket, categoria, confianca=Decimal(str(round(confianca, 4))))
    return categoria


def classificar_ticket_em_segundo_plano(ticket: Ticket) -> None:
    """Dispara a classificação numa thread, para não segurar a resposta ao
    solicitante — o zero-shot com o catálogo inteiro leva alguns segundos, e
    quem abriu o chamado não tem por que esperar por isso.

    Sem Celery/Redis no projeto, uma thread é o mecanismo mais simples que
    resolve; como cada chamado dispara no máximo uma, e o trabalho pesado
    acontece do lado do serviço de IA, não há risco de inundar o processo.
    """
    if not classificador_configurado():
        return

    thread = threading.Thread(
        target=_classificar_em_thread, args=(ticket.pk,), daemon=True,
        name=f"classificar-ia-{ticket.pk}",
    )
    thread.start()


def _classificar_em_thread(ticket_id: int) -> None:
    """Corpo da thread. Recarrega o ticket pelo id em vez de receber o objeto,
    porque a instância do request pode estar desatualizada quando a thread
    finalmente roda."""
    try:
        ticket = Ticket.objects.filter(pk=ticket_id).first()
        if ticket is None:
            return
        classificar_ticket(ticket)
    except ClassificadorIndisponivel as erro:
        logger.warning("Classificação de IA indisponível para o chamado #%s: %s", ticket_id, erro)
    except Exception:
        # A thread roda fora do ciclo de request: uma exceção aqui não
        # apareceria em lugar nenhum se não fosse registrada.
        logger.exception("Erro inesperado ao classificar o chamado #%s.", ticket_id)
    finally:
        # Cada thread abre sua própria conexão com o banco; sem fechar, elas
        # vazam (o Django só limpa as do ciclo de request).
        connection.close()
