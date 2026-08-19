# Sistema de Chamados de TI Hospitalar

TCC do curso de Análise e Desenvolvimento de Sistemas (SENAI): sistema de abertura,
classificação, priorização e recomendação de chamados de TI para um hospital, com
apoio de um classificador de IA.

## Princípio central de design

Todos os pesos, SLAs, limiares de desvio e regras de recomendação ficam armazenados
no banco de dados (`Categoria`, `Setor`, `ParametroSistema`, `RegraRecomendacao`) —
nada é fixado no código da aplicação. Qualquer ajuste de negócio (peso de uma
categoria, SLA, limiar de desvio, texto de uma recomendação) é feito pelo Django
Admin, sem alterar uma linha de código.

## Stack

- **Backend**: Django 5.2 (Python)
- **Banco de dados**: PostgreSQL
- **Classificador de IA**: Hugging Face `mDeBERTa-v3-base-mnli-xnli` (zero-shot),
  em desenvolvimento separado — ainda não integrado a este projeto Django
- **Frontend**: Django templates + Bootstrap 5 (via CDN)

## Estrutura do projeto

```
config/                  # projeto Django (settings, urls, wsgi/asgi)
tickets/                 # app principal
  models.py              # as 9 entidades do modelo de dados
  admin.py                # registro de todos os models no Django Admin
  forms.py                # formulários (abertura de chamado, classificação)
  views.py                # views das telas de solicitante e técnico
  urls.py                 # rotas do app
  services/                # camada de negócio (RN01–RN17), ver seção abaixo
  migrations/              # schema + seeds de dados (catálogos, parâmetros)
  tests/                   # testes automatizados da camada de serviço
  templates/tickets/       # templates HTML (Bootstrap)
```

## Modelo de dados

- **Setor** — 47 setores do hospital, cada um com `peso_setor` (1–5, criticidade).
- **Categoria** — 36 serviços/sintomas de TI, agrupados em 5 `grupo`s (clínico,
  rede, suporte, equipamento, acesso), cada um com `peso_categoria` (1–5) e
  `sla_horas` fixo.
- **ExcecaoPrioridade** — override manual de prioridade para uma combinação
  (categoria, setor) específica, em vez de uma matriz completa 36×47.
- **ItemConfiguracao** — CMDB: equipamentos físicos do hospital (patrimônio, tipo,
  setor, status), linkável a um Ticket. *Em aberto*: se o técnico escolhe de uma
  lista pré-cadastrada ou digita/escaneia o patrimônio manualmente.
- **Ticket** — o chamado em si. Mantém três categorias separadas:
  - `categoria_sugerida`: escolhida pelo solicitante ao abrir o chamado.
  - `categoria_ia`: inferida pelo classificador de IA a partir da descrição
    (ainda não populada — integração pendente).
  - `categoria_final`: confirmada/corrigida pelo técnico — é essa que alimenta
    SLA e prioridade.
  - Também guarda `solicitante_nome`, `solicitante_ramal`, `solicitante_sala`.
- **HistoricoSLA** — 1:1 com Ticket, grava `tempo_real`, `tempo_esperado` e
  `desvio` quando o chamado é fechado.
- **ParametroSistema** — pares chave/valor configuráveis (limiares de desvio,
  janela de agregação, volume mínimo de tickets), lidos pela camada de serviço.
- **RegraRecomendacao** — mapeia um `tipo_desvio` ("atencao"/"critico") para uma
  `acao_sugerida` em texto livre.
- **Recomendacao** — gerada pelo motor de recomendação, vinculada a Categoria +
  Setor + a RegraRecomendacao que disparou.

## Regras de negócio (RN01–RN17) e onde encontrá-las

| Bloco | RNs | Arquivo |
|---|---|---|
| Classificação (dupla checagem) | RN01–RN04 | `tickets/services/classificacao.py` |
| Cálculo de prioridade | RN05–RN07 | `tickets/services/prioridade.py` |
| Controle de SLA | RN08–RN10 | `tickets/services/sla.py` |
| Detecção de desvio | RN11–RN14 | `tickets/services/desvio.py` |
| Geração de recomendação | RN15–RN17 | `tickets/services/recomendacao.py` |

Resumo da lógica:

- **RN01–RN04**: o solicitante escolhe uma categoria (`categoria_sugerida`); a IA
  infere a sua própria (`categoria_ia`), independente da escolha do usuário; o
  técnico vê as duas lado a lado e confirma/corrige em `categoria_final`; só essa
  última alimenta SLA e prioridade.
- **RN05–RN07**: `prioridade = peso_categoria × peso_setor`, substituída por um
  valor manual quando existir uma `ExcecaoPrioridade` para aquela combinação.
  Recalculada sempre que a `categoria_final` é confirmada.
- **RN08–RN10**: o SLA esperado vem de `categoria_final.sla_horas`; ao fechar o
  chamado, grava-se `HistoricoSLA` com tempo real, esperado e o desvio entre eles.
- **RN11–RN14**: o desvio percentual de cada chamado fechado é agregado por
  categoria+setor (não por ticket isolado, nem só por categoria) numa janela de
  tempo, e classificado em `None` / `"atencao"` / `"critico"` conforme limiares
  configuráveis em `ParametroSistema`.
- **RN15–RN17**: quando uma agregação categoria+setor ultrapassa o limiar de uma
  `RegraRecomendacao` (com volume mínimo de tickets), gera-se uma `Recomendacao`
  vinculada a essa categoria, setor e regra — sem duplicar uma recomendação já
  emitida recentemente para a mesma combinação.

## Telas implementadas

| Papel | Rota | Descrição |
|---|---|---|
| Solicitante | `/tickets/abrir/` | Formulário de abertura: nome, ramal, sala, setor, categoria, descrição. Ao enviar, mostra número do chamado, categoria e SLA esperado. |
| Técnico | `/tickets/tecnico/` | Fila de chamados não fechados, ordenada por prioridade. |
| Técnico | `/tickets/tecnico/<id>/` | Detalhe do chamado: dupla checagem de categoria, confirmação da `categoria_final` e fechamento (grava `HistoricoSLA`). |
| Admin | `/admin/` | Django Admin — edição de todas as tabelas de configuração sem código. |

Ainda não há autenticação/controle de acesso por papel — todas as telas acima
estão abertas. Também não há dashboard de gestor (desvios agregados +
recomendações).

## Como rodar localmente

```bash
# ambiente virtual
python -m venv .venv
.venv\Scripts\activate      # Windows

# dependências
pip install -r requirements.txt

# variáveis de ambiente
copy .env.example .env      # e preencha DB_USER/DB_PASSWORD com um role do seu Postgres

# banco de dados
python manage.py migrate

# rodar
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/` (abre direto na tela de abertura de chamado) ou
`http://127.0.0.1:8000/admin/`.

### Variáveis de ambiente (`.env`)

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | chave secreta do Django |
| `DEBUG` | `True`/`False` |
| `ALLOWED_HOSTS` | lista separada por vírgula |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | conexão PostgreSQL |

## Testes

```bash
python manage.py test tickets
```

18 testes cobrindo os 5 blocos de serviço (prioridade, classificação, SLA, desvio,
recomendação), usando o banco de teste do Postgres (o role do `.env` precisa de
permissão `CREATEDB`).

## Dados semeados (migrations)

As migrations de dados populam o catálogo real do hospital e os parâmetros do
motor de recomendação — todos editáveis depois pelo Admin, sem precisar rodar
migration nova:

- `0002_seed_catalogo` / `0004_substituir_catalogo_setores`: 47 setores.
- `0002_seed_catalogo` / `0005_substituir_catalogo_categorias`: 36 categorias.
- `0003_seed_parametros_e_regras`: limiares de desvio (20%/50%), janela de
  agregação (30 dias), volume mínimo (5 tickets), e as regras de recomendação
  "atenção"/"crítico".

Os pesos, SLAs e limiares desses seeds são valores propostos para servirem de
ponto de partida — ajustáveis pelo Admin conforme os dados reais do hospital.

## Pendências conhecidas

- Autenticação e controle de acesso por papel (solicitante/técnico/gestor).
- Dashboard do gestor (desvios de SLA agregados + recomendações geradas).
- Integração do classificador mDeBERTa (hoje roda separado, lendo Excel) com
  `registrar_classificacao_ia()`.
- Decisão de como o técnico vincula um `ItemConfiguracao` (CMDB) ao ticket —
  lista pré-cadastrada ou entrada manual/scan.
