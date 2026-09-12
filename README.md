# Sistema de Chamados de TI Hospitalar

TCC do curso de Análise e Desenvolvimento de Sistemas (SENAI): sistema de abertura,
classificação, priorização, controle de SLA e recomendação de chamados de TI para um
hospital, com apoio de um classificador de IA.

## Princípio central de design

Todos os pesos, SLAs, limiares de desvio e regras de recomendação ficam armazenados
no banco de dados (`Categoria`, `Setor`, `ParametroSistema`, `RegraRecomendacao`) —
nada é fixado no código da aplicação. Qualquer ajuste de negócio (peso de uma
categoria, SLA, limiar de desvio, fator de prioridade, texto de uma recomendação) é
feito pelo Django Admin, sem alterar uma linha de código.

## Stack

- **Backend**: Django 5.2 (Python 3.11+)
- **Banco de dados**: PostgreSQL
- **Frontend**: Django templates + Bootstrap 5 (via CDN)
- **Configuração**: `python-decouple` (lê o `.env`)
- **Sanitização de HTML**: `bleach` (conteúdo da base de conhecimento)
- **Desenvolvimento**: `django-debug-toolbar` (carregada só quando `DEBUG=True`)
- **Classificador de IA**: Hugging Face `mDeBERTa-v3-base-mnli-xnli` (zero-shot),
  em desenvolvimento separado — ainda não integrado a este projeto Django

## Estrutura do projeto

```
config/                    # projeto Django (settings, urls, wsgi/asgi, views de erro)
tickets/                   # app principal
  models.py                # as 21 entidades do modelo de dados
  admin.py                 # registro dos models no Django Admin
  forms.py                 # formulários (abertura, classificação, login, senha, equipamento...)
  views.py                 # views das telas de solicitante, técnico e gestor
  urls.py                  # rotas do app
  signals.py               # invalidação de cache de parâmetro + criação de PerfilTecnico
  context_processors.py    # papel do usuário e contador de notificações nos templates
  services/                # camada de negócio (RN01–RN17 + serviços auxiliares)
  templatetags/            # filtros usados nos templates
  migrations/              # schema + seeds de dados (catálogos, parâmetros, equipamentos)
  tests/                   # 199 testes automatizados
  templates/               # templates HTML (tickets/ e registration/)
  static/tickets/          # CSS, JS e imagens próprios
docs/diagrama_er.html      # diagrama ER do modelo de dados
```

## Papéis e controle de acesso

O sistema é todo autenticado — não há tela pública. O papel não é um campo próprio:
é derivado do usuário do Django (`is_staff`, `is_superuser`) e de `Setor.gestor`.

| Papel | Como é identificado | Acesso |
|---|---|---|
| **Usuário** (solicitante) | usuário comum, sem `is_staff` e sem setor sob gestão | abrir chamado, "Meus chamados", responder o técnico, notificações, base de conhecimento, perfil |
| **Técnico** | `is_staff=True` | tudo do usuário + fila, dashboard, histórico, SLA por categoria, CMDB, modelos de resposta, e as ações de atendimento |
| **Gestor de setor** | é `gestor` de algum `Setor` (sem `is_staff`) | mesmo acesso operacional do técnico, e controle total sobre chamados (não fica limitado aos seus) |
| **Administrador** | é gestor do setor de TI (`setor_ti_id`) | rótulo especial do gestor de TI; o `/admin/` em si exige `is_superuser` |

Duas regras importantes em `views.py`:

- `_tem_acesso_operacional` — técnicos, gestores de setor e superusuários têm o mesmo
  nível de acesso às telas operacionais. Só o Django Admin (`/admin/`) continua
  exclusivo de superusuários.
- `_pode_gerenciar_chamado` — classificar e fechar são ações de dono do chamado: um
  técnico só mexe no chamado que é dele; gestor/superusuário mantém controle total.

O nível de atendimento do técnico (N1/N2/N3) fica em `PerfilTecnico`, criado
automaticamente por signal para todo `is_staff` — nasce em N1, e o gestor promove
para N2/N3 pelo Admin.

## Modelo de dados

### Catálogo e configuração

- **Setor** — setores do hospital, cada um com `peso_setor` (1–5, criticidade) e um
  `gestor` opcional.
- **Categoria** — serviços/sintomas de TI, com `grupo` (impressora, computador, rede,
  acesso, clínico, suporte), `tipo` (Incidente/Requisição), `nivel_atendimento`
  (N1/N2/N3), `peso_categoria` (1–5), `sla_horas` e `requer_patrimonio`.
- **ExcecaoPrioridade** — override manual de prioridade para uma combinação
  (categoria, setor) específica, em vez de uma matriz completa.
- **ParametroSistema** — pares chave/valor configuráveis, lidos pela camada de serviço
  (com cache invalidado por signal ao salvar).
- **RegraRecomendacao** — mapeia um `tipo_desvio` ("atencao"/"critico") para uma
  `acao_sugerida` em texto livre.

### Chamado

- **Ticket** — o chamado. Mantém três categorias separadas:
  - `categoria_sugerida`: escolhida pelo solicitante ao abrir;
  - `categoria_ia`: inferida pelo classificador (ainda não populada);
  - `categoria_final`: confirmada/corrigida pelo técnico — é essa que alimenta SLA e
    prioridade.

  Guarda também `status` (aberto / em atendimento / pausado / fechado), `impacto`,
  `nivel_atual`, `prioridade_calculada`, `tecnico_responsavel`, o `solicitante`
  autenticado mais os dados de contato (`nome`, `ramal`, `sala`, `ip` capturado
  automaticamente), o equipamento vinculado e o código estável do chamado
  (`codigo_tipo` + `codigo_numero` → `INC123` / `REQ45`).
- **ContadorChamado** — contador atômico do último número usado por tipo, incrementado
  com `select_for_update` para não repetir número em criações simultâneas.
- **ComentarioTicket** — histórico do atendimento: nota interna, resposta ao usuário,
  resposta do solicitante e desfecho/solução final.
- **RespostaRapida** / **RespostaRapidaEdicao** — modelos de resposta para problemas
  repetitivos, inseridos com um clique, mais o log de auditoria de quem editou o
  modelo e quando.
- **EscalonamentoTicket** — log de escalonamento entre níveis (N1→N2→N3), com autor,
  níveis e justificativa.
- **SolicitacaoTransferencia** — pedido de um técnico para assumir chamado de outro;
  tem ciclo de vida real (pendente → aceita/recusada).
- **PausaSLA** — período em que o SLA ficou pausado (aguardando fornecedor, peça,
  usuário, aprovação ou outro motivo); esse tempo não conta contra a equipe.
- **HistoricoSLA** — 1:1 com Ticket, grava `tempo_real`, `tempo_esperado`,
  `tempo_pausado` e `desvio` quando o chamado é fechado.
- **Notificacao** — aviso in-app (mudança de status, novo comentário, escalonamento,
  transferência, resguardo liberado). Fica guardada depois de lida; só `lida` muda.

### CMDB e equipamentos

- **ItemConfiguracao** — equipamento físico rastreado: `patrimonio` (6 dígitos
  numéricos, validado), categoria, marca, modelo, setor, status (disponível, em uso,
  em triagem, em resguardo, resguardo encerrado, baixado), datas de aquisição e de
  validade da garantia, e os campos de resguardo por desligamento.
- **MovimentacaoEquipamento** — histórico de cada movimentação registrada num chamado
  (entrada, saída, motivo do retorno), inclusive a confirmação explícita de que não
  houve movimentação. Só é aplicada ao CMDB quando o chamado é fechado (`aplicada`).

### Gestão e conhecimento

- **Recomendacao** — gerada pelo motor de recomendação, vinculada a Categoria + Setor
  + a RegraRecomendacao que disparou.
- **ArtigoConhecimento** — tutoriais/artigos da base de conhecimento interna, com
  resumo, conteúdo, autor e categoria relacionada.
- **PerfilTecnico** — nível de atendimento (N1/N2/N3) do técnico.
- **CodigoRecuperacaoSenha** — código temporário de 6 dígitos do "esqueci minha senha".

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
  infere a sua própria (`categoria_ia`), independente da escolha do usuário; o técnico
  vê as duas lado a lado e confirma/corrige em `categoria_final`; só essa última
  alimenta SLA e prioridade.
- **RN05–RN07**: `prioridade = peso_categoria × peso_setor × fator_prioridade_<tipo>`,
  substituída pelo valor manual quando existir uma `ExcecaoPrioridade` para a
  combinação (aí o fator de tipo não se aplica). Recalculada sempre que a
  `categoria_final` é confirmada.
- **RN08–RN10**: o SLA esperado vem de `categoria_final.sla_horas`; o tempo real é
  medido entre abertura e fechamento, **descontado o tempo pausado**; ao fechar,
  grava-se `HistoricoSLA`. Fechar exige categoria final confirmada, técnico atribuído,
  movimentação de equipamento resolvida e nenhuma pausa em aberto — e é o momento em
  que as movimentações pendentes são aplicadas ao CMDB.
- **RN11–RN14**: o desvio percentual de cada chamado fechado é agregado por
  categoria+setor (não por ticket isolado, nem só por categoria) numa janela de tempo,
  e classificado em `None` / `"atencao"` / `"critico"` conforme limiares configuráveis
  em `ParametroSistema`.
- **RN15–RN17**: quando uma agregação categoria+setor ultrapassa o limiar de uma
  `RegraRecomendacao` (com volume mínimo de tickets), gera-se uma `Recomendacao`
  vinculada a essa categoria, setor e regra — sem duplicar uma recomendação já emitida
  dentro da janela.

### Serviços auxiliares (fora das RN01–17)

| Arquivo | Responsabilidade |
|---|---|
| `services/codigo.py` | numeração sequencial atômica por tipo de chamado (`INC`/`REQ`) |
| `services/pausa.py` | pausar/retomar o SLA e somar o tempo pausado |
| `services/equipamento.py` | movimentação de equipamento, elegibilidade de entrada/saída, resguardo por desligamento |
| `services/notificacoes.py` | notificações in-app para solicitante e para técnicos de um nível |
| `services/recuperacao_senha.py` | geração/validação do código de 6 dígitos por e-mail |
| `services/parametros.py` | leitura de `ParametroSistema` com cache e invalidação por signal |

**Resguardo de equipamento**: quando o técnico registra o retorno de um equipamento por
desligamento de colaborador, o equipamento entra em resguardo automaticamente — 30 dias
para liderança, 15 dias para os demais cargos. Vencido o prazo,
`liberar_resguardos_vencidos()` libera o equipamento para formatação e notifica o
técnico que registrou. A varredura roda ao carregar a fila e a lista de equipamentos —
não há agendador (cron/Celery) no projeto.

## Telas implementadas

Todas exigem login. A raiz (`/`) redireciona para o portal.

| Papel | Rota | Descrição |
|---|---|---|
| Todos | `/accounts/login/` | Login. Fluxo de recuperação de senha em `esqueci-senha/`, `confirmar-codigo/` e `nova-senha/` |
| Todos | `/tickets/` | Portal inicial, com os atalhos conforme o papel |
| Todos | `/tickets/abrir/` | Abertura de chamado: contato, setor, categoria, impacto, descrição e patrimônio quando a categoria exige |
| Usuário | `/tickets/meus/` e `/tickets/meus/<id>/` | "Meus chamados" e o detalhe, onde o solicitante acompanha e responde o técnico |
| Todos | `/tickets/notificacoes/` | Central de notificações (com dropdown e contador no topo) |
| Todos | `/tickets/perfil/<username>/` | Perfil: dados, papel/nível, troca de senha |
| Todos | `/tickets/base-conhecimento/` | Base de conhecimento — leitura para todos; criar/editar é de técnico |
| Técnico | `/tickets/tecnico/` | Fila de chamados, em lista ou kanban, com filtros e semáforo de SLA |
| Técnico | `/tickets/tecnico/<id>/` | Detalhe do chamado: dupla checagem, classificação, comentários, escalonamento, pausa, atribuição/transferência, movimentação de equipamento e fechamento (tudo em modais) |
| Técnico | `/tickets/tecnico/dashboard/` | Indicadores: abertos/fechados hoje, MTTA, MTTR, chamados críticos e estourados, volume por setor, fluxo diário |
| Técnico | `/tickets/tecnico/historico/` | Histórico de chamados fechados |
| Técnico | `/tickets/sla/` | SLA agregado por categoria |
| Técnico | `/tickets/equipamentos/` | CMDB: listar, cadastrar e consultar equipamento por patrimônio. Editar é permitido ao técnico **ou** ao gestor do setor em que o equipamento está lotado |
| Técnico | `/tickets/modelos-resposta/` | Modelos de resposta rápida: listar, criar, editar |
| Admin | `/admin/` | Django Admin — edição de todas as tabelas de configuração sem código (exige `is_superuser`) |

## Como rodar localmente

Pré-requisito: PostgreSQL rodando, com o banco criado (`CREATE DATABASE tcc_hospital;`).

```bash
# ambiente virtual
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux/macOS

# dependências
pip install -r requirements.txt

# variáveis de ambiente
copy .env.example .env      # cp no Linux/macOS
#   preencha DB_USER/DB_PASSWORD com um role do seu Postgres

# banco de dados (schema + seeds)
python manage.py migrate

# usuário administrador
python manage.py createsuperuser

# rodar
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/` (redireciona para o portal, pedindo login) ou
`http://127.0.0.1:8000/admin/`.

Para acessar de outra máquina da rede, rode com `python manage.py runserver 0.0.0.0:8000`
e inclua o IP da máquina em `ALLOWED_HOSTS`.

### Variáveis de ambiente (`.env`)

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | chave secreta do Django |
| `DEBUG` | `True`/`False` — em `True`, carrega a Debug Toolbar e libera as telas de preview de erro |
| `ALLOWED_HOSTS` | lista separada por vírgula |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | conexão PostgreSQL |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | relay SMTP (Brevo) usado na recuperação de senha |
| `EMAIL_BACKEND` | opcional; em desenvolvimento, `django.core.mail.backends.console.EmailBackend` imprime o e-mail no terminal em vez de enviar |

## Testes

```bash
python manage.py test tickets
```

**199 testes**, cobrindo os cinco blocos de serviço (prioridade, classificação, SLA,
desvio, recomendação) e também níveis de atendimento, notificações, transferência,
pausa de SLA, resguardo e movimentação de equipamento, respostas rápidas, filtros da
fila, permissões, código do chamado, tipo de chamado, login, recuperação de senha e
páginas de erro. Usam o banco de teste do Postgres — o role do `.env` precisa de
permissão `CREATEDB`.

## Dados semeados (migrations)

As migrations de dados populam o catálogo real do hospital e os parâmetros do motor de
recomendação — todos editáveis depois pelo Admin, sem precisar rodar migration nova:

- **45 setores** — `0002_seed_catalogo`, substituído por `0004_substituir_catalogo_setores`.
- **38 categorias** — `0002_seed_catalogo`, substituído por
  `0005_substituir_catalogo_categorias`; `0008_marcar_categorias_com_patrimonio` marca
  as 10 que exigem patrimônio; `0032` adiciona "Instalar impressora".
- **13 equipamentos** de exemplo no CMDB — `0032_seed_equipamentos_e_categoria_instalar_impressora`.
- **2 modelos de resposta rápida** — `0041_seed_respostas_rapidas`, agrupados em `0043`.
- **Parâmetros e regras** — `0003_seed_parametros_e_regras` (limiares de desvio, janela,
  volume mínimo e as regras "atenção"/"crítico"), `0012_seed_parametro_setor_ti` e
  `0035_seed_fatores_prioridade_tipo`.

Parâmetros semeados hoje:

| Chave | Valor | Para que serve |
|---|---|---|
| `desvio_atencao_pct` | 20 | estouro médio de SLA que caracteriza desvio leve |
| `desvio_critico_pct` | 50 | estouro médio de SLA que caracteriza desvio crítico |
| `janela_recomendacao_dias` | 30 | janela de agregação dos desvios |
| `min_tickets_para_recomendacao` | 5 | volume mínimo para uma agregação virar recomendação |
| `fator_prioridade_incidente` | 1.0 | multiplicador de prioridade para Incidente |
| `fator_prioridade_requisicao` | 1.0 | multiplicador de prioridade para Requisição |
| `setor_ti_id` | 49 | setor de TI para onde o equipamento substituído retorna |

Os pesos, SLAs e limiares desses seeds são valores propostos para servirem de ponto de
partida — ajustáveis pelo Admin conforme os dados reais do hospital.

## Pendências conhecidas

- **Integração do classificador de IA**: `registrar_classificacao_ia()` já existe e é
  testada, mas nenhuma view a chama — o mDeBERTa roda separado, lendo Excel, e
  `categoria_ia` continua vazia em produção.
- **Motor de recomendação sem gatilho e sem tela**: `gerar_recomendacoes()` está
  implementado e testado, mas só é chamado nos testes; não há agendamento nem tela que
  exiba as `Recomendacao` geradas ao gestor.
- **Tipo e nível nas categorias**: todas as 38 categorias semeadas estão como
  Incidente/N1 — a curadoria de quais são Requisição e quais exigem N2/N3 ainda precisa
  ser feita pelo Admin.
- **Varredura de resguardo sem agendador**: `liberar_resguardos_vencidos()` roda ao
  carregar a fila e a lista de equipamentos; sem acesso a essas telas, o prazo não é
  liberado.
- **Preparo para produção**: falta `STATIC_ROOT` (então `collectstatic` não roda),
  servidor WSGI (gunicorn/waitress não estão no `requirements.txt`) e um `.env` de
  produção com `DEBUG=False` e `SECRET_KEY` própria.
