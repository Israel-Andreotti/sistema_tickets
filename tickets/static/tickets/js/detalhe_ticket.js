document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('detalheTicket');
    var url = container.dataset.urlConsultarEquipamento;
    var ticketPk = container.dataset.ticketPk;

    // Movimentação de equipamento: um patrimônio de cada vez. Digitar aciona
    // a mesma consulta assíncrona de sempre (consultar_equipamento_view) —
    // a direção (saída/entrada) é sempre deduzida daqui pelo setor/status
    // atual do equipamento, nunca escolhida à mão. Se elegível, "Adicionar à
    // movimentação" empilha o item numa fila só do navegador (nada é salvo
    // ainda); só ao clicar em "Registrar movimentação" a fila inteira vira
    // um único POST (campo oculto "itens", JSON) — ver movimentar_equipamento_view.
    var MOTIVO_LABELS = { falta: 'Estragou', desligamento: 'Desligamento', troca_comum: 'Troca' };
    var CARGO_LABELS = { lideranca: 'Gestor ou diretor', colaborador: 'Outro cargo' };

    var dadosMovimentacaoEl = document.getElementById('dadosMovimentacao');
    if (dadosMovimentacaoEl) {
        var setorChamadoNome = dadosMovimentacaoEl.dataset.setorChamado;
        var setorTiNome = dadosMovimentacaoEl.dataset.setorTi;
        var buscaInput = document.getElementById('buscaPatrimonioMovimentacao');
        var botaoAdicionar = document.getElementById('botaoAdicionarMovimentacao');
        var previewEl = document.getElementById('previewMovimentacao');
        var filaEl = document.getElementById('filaMovimentacao');
        var filaVaziaEl = document.getElementById('filaMovimentacaoVazia');
        var itensInput = document.getElementById('itensMovimentacaoInput');
        var avisoPendenteEl = document.getElementById('avisoMovimentacaoPendente');
        var botaoRegistrar = document.getElementById('botaoRegistrarMovimentacao');
        var formMovimentacao = document.getElementById('formMovimentacaoEquipamento');
        var modalCargoEl = document.getElementById('modalCargoDesligado');
        var modalCargo = modalCargoEl && window.bootstrap ? new bootstrap.Modal(modalCargoEl) : null;

        var filaStaged = [];
        var proximoUid = 1;
        var itemValidado = null; // { patrimonio, direcao, categoria, marca, modelo }
        var temErro = false;
        var uidAguardandoCargo = null;

        function patrimoniosExistentes() {
            var lista = filaStaged.map(function (item) { return item.patrimonio; });
            document.querySelectorAll('[data-fila-patrimonio]').forEach(function (el) {
                lista.push(el.getAttribute('data-fila-patrimonio'));
            });
            return lista;
        }

        function limparPreview() {
            previewEl.innerHTML = '';
            itemValidado = null;
            temErro = false;
            botaoAdicionar.disabled = true;
            atualizarEstadoRegistrar();
        }

        function mostrarErro(mensagem, dados) {
            itemValidado = null;
            temErro = true;
            botaoAdicionar.disabled = true;
            var resumo = dados ? (dados.categoria + ' ' + dados.marca + ' ' + dados.modelo) : '';
            previewEl.innerHTML =
                '<div class="mov-preview-card mov-preview-erro">' +
                (resumo ? '<strong>' + resumo + '</strong><div class="small text-muted">' + dados.setor + ' · ' + dados.status + '</div>' : '') +
                '<div class="small mov-preview-motivo mt-1">' + mensagem + '</div>' +
                '</div>';
            atualizarEstadoRegistrar();
        }

        function mostrarSucesso(dados, direcao) {
            temErro = false;
            itemValidado = {
                patrimonio: dados.patrimonio, direcao: direcao,
                categoria: dados.categoria, marca: dados.marca, modelo: dados.modelo,
            };
            botaoAdicionar.disabled = false;
            var rotuloDirecao = direcao === 'saida' ? 'saída para a Informática' : 'entrada na ' + setorChamadoNome;
            previewEl.innerHTML = '<div class="small mov-preview-ok">' +
                dados.categoria + ' ' + dados.marca + ' ' + dados.modelo +
                ' — será registrado como ' + rotuloDirecao + '.</div>';
            atualizarEstadoRegistrar();
        }

        function consultar() {
            var patrimonio = buscaInput.value.trim();
            if (!/^\d{6}$/.test(patrimonio)) {
                limparPreview();
                return;
            }
            fetch(url + '?patrimonio=' + encodeURIComponent(patrimonio) + '&ticket=' + ticketPk)
                .then(function (resp) { return resp.json(); })
                .then(function (dados) {
                    if (buscaInput.value.trim() !== patrimonio) return; // resposta atrasada, já mudou o campo
                    if (!dados.encontrado) {
                        mostrarErro('Patrimônio não encontrado.');
                        return;
                    }
                    if (patrimoniosExistentes().indexOf(dados.patrimonio) !== -1) {
                        mostrarErro('Este patrimônio já está nesta movimentação.', dados);
                        return;
                    }
                    if (dados.elegivel_saida) {
                        mostrarSucesso(dados, 'saida');
                    } else if (dados.elegivel_entrada) {
                        mostrarSucesso(dados, 'entrada');
                    } else if (dados.setor === setorTiNome) {
                        mostrarErro('Só entram equipamentos com situação Disponível; este está em ' + dados.status + '.', dados);
                    } else {
                        mostrarErro('Este equipamento está lotado em outro setor (' + dados.setor + ') — não pode ser movimentado por este chamado.', dados);
                    }
                });
        }

        var timerConsulta = null;
        buscaInput.addEventListener('input', function () {
            clearTimeout(timerConsulta);
            timerConsulta = setTimeout(consultar, 400);
        });

        botaoAdicionar.addEventListener('click', function () {
            if (!itemValidado) return;
            var item = Object.assign({
                _uid: proximoUid++,
                motivoRetorno: 'falta',
                nivelCargoDesligado: '',
            }, itemValidado);
            filaStaged.push(item);
            buscaInput.value = '';
            limparPreview();
            renderizarFila();
        });

        function linhaSetores(direcao) {
            return direcao === 'saida'
                ? setorChamadoNome + ' → ' + setorTiNome
                : setorTiNome + ' → ' + setorChamadoNome;
        }

        function criarSelectMotivo(item) {
            var select = document.createElement('select');
            select.className = 'form-select form-select-sm w-auto mt-1';
            Object.keys(MOTIVO_LABELS).forEach(function (valor) {
                var option = document.createElement('option');
                option.value = valor;
                option.textContent = MOTIVO_LABELS[valor];
                if (valor === item.motivoRetorno) option.selected = true;
                select.appendChild(option);
            });
            select.addEventListener('change', function () {
                var anterior = item.motivoRetorno;
                item.motivoRetorno = select.value;
                if (select.value === 'desligamento' && !item.nivelCargoDesligado) {
                    uidAguardandoCargo = item._uid;
                    if (modalCargo) modalCargo.show();
                } else if (select.value !== 'desligamento') {
                    item.nivelCargoDesligado = '';
                }
                if (anterior !== select.value) renderizarFila();
            });
            return select;
        }

        function renderizarFila() {
            document.querySelectorAll('.mov-item[data-uid]').forEach(function (el) { el.remove(); });
            if (filaVaziaEl) filaVaziaEl.classList.toggle('d-none', filaStaged.length > 0);

            filaStaged.forEach(function (item) {
                var linha = document.createElement('div');
                linha.className = 'mov-item';
                linha.setAttribute('data-uid', item._uid);
                linha.setAttribute('data-fila-patrimonio', item.patrimonio);

                var info = document.createElement('div');
                var pill = document.createElement('span');
                pill.className = 'badge rounded-pill mb-1 ' + (item.direcao === 'saida' ? 'bg-warning text-dark' : 'bg-success');
                pill.textContent = item.direcao === 'saida' ? 'Saída' : 'Entrada';
                info.appendChild(pill);

                var linhaPatrimonio = document.createElement('div');
                linhaPatrimonio.className = 'small';
                linhaPatrimonio.innerHTML = '<strong>' + item.patrimonio + '</strong> — ' +
                    item.categoria + ' ' + item.marca + ' ' + item.modelo;
                info.appendChild(linhaPatrimonio);

                var linhaSetor = document.createElement('div');
                linhaSetor.className = 'timeline-transicao';
                linhaSetor.textContent = linhaSetores(item.direcao);
                info.appendChild(linhaSetor);

                if (item.direcao === 'saida') {
                    info.appendChild(criarSelectMotivo(item));
                    if (item.motivoRetorno === 'desligamento' && item.nivelCargoDesligado) {
                        var cargoResumo = document.createElement('div');
                        cargoResumo.className = 'small text-muted mt-1';
                        cargoResumo.textContent = 'Cargo: ' + CARGO_LABELS[item.nivelCargoDesligado] + ' — ';
                        var linkAlterarCargo = document.createElement('a');
                        linkAlterarCargo.href = '#';
                        linkAlterarCargo.textContent = 'alterar';
                        linkAlterarCargo.addEventListener('click', function (evento) {
                            evento.preventDefault();
                            uidAguardandoCargo = item._uid;
                            if (modalCargo) modalCargo.show();
                        });
                        cargoResumo.appendChild(linkAlterarCargo);
                        info.appendChild(cargoResumo);
                    }
                }

                linha.appendChild(info);

                var botaoRemover = document.createElement('button');
                botaoRemover.type = 'button';
                botaoRemover.className = 'mov-item-remover';
                botaoRemover.title = 'Remover';
                botaoRemover.textContent = '✕';
                botaoRemover.addEventListener('click', function () {
                    filaStaged = filaStaged.filter(function (outro) { return outro._uid !== item._uid; });
                    renderizarFila();
                });
                linha.appendChild(botaoRemover);

                filaEl.appendChild(linha);
            });

            atualizarEstadoRegistrar();
        }

        function atualizarEstadoRegistrar() {
            var bloqueado = filaStaged.length === 0 || temErro;
            botaoRegistrar.disabled = bloqueado;
            if (avisoPendenteEl) avisoPendenteEl.classList.toggle('d-none', !temErro);
        }

        if (modalCargoEl) {
            modalCargoEl.querySelectorAll('button[data-cargo]').forEach(function (botao) {
                botao.addEventListener('click', function () {
                    var item = filaStaged.find(function (candidato) { return candidato._uid === uidAguardandoCargo; });
                    if (item) item.nivelCargoDesligado = botao.dataset.cargo;
                    uidAguardandoCargo = null;
                    if (modalCargo) modalCargo.hide();
                    renderizarFila();
                });
            });
            modalCargoEl.addEventListener('hidden.bs.modal', function () {
                // Fechou sem escolher um cargo — não faz sentido deixar
                // "Desligamento" selecionado sem saber pra qual prazo de resguardo.
                if (uidAguardandoCargo === null) return;
                var item = filaStaged.find(function (candidato) { return candidato._uid === uidAguardandoCargo; });
                if (item && !item.nivelCargoDesligado) {
                    item.motivoRetorno = 'falta';
                    renderizarFila();
                }
                uidAguardandoCargo = null;
            });
        }

        formMovimentacao.addEventListener('submit', function (evento) {
            if (filaStaged.length === 0) {
                evento.preventDefault();
                return;
            }
            itensInput.value = JSON.stringify(filaStaged.map(function (item) {
                return {
                    patrimonio: item.patrimonio,
                    motivo_retorno: item.direcao === 'saida' ? item.motivoRetorno : '',
                    nivel_cargo_desligado: item.direcao === 'saida' ? item.nivelCargoDesligado : '',
                };
            }));
        });

        atualizarEstadoRegistrar();
    }

    // No modal de confirmação de fechamento, se ainda não há movimentação
    // registrada, o técnico precisa marcar "não houve movimentação" pra
    // liberar o botão "Confirmar fechamento" (o backend já sabe tratar esse
    // campo junto com o próprio fechamento — ver fechar_ticket_view).
    var checkboxSemMovimentacaoFechamento = document.getElementById('confirmar_sem_movimentacao');
    var botaoConfirmarFechamento = document.getElementById('botaoConfirmarFechamento');
    if (checkboxSemMovimentacaoFechamento && botaoConfirmarFechamento) {
        checkboxSemMovimentacaoFechamento.addEventListener('change', function () {
            botaoConfirmarFechamento.disabled = !checkboxSemMovimentacaoFechamento.checked;
        });
    }

    // Respostas rápidas: busca por título entre os modelos cadastrados e, ao
    // escolher um, insere o texto no comentário (sem apagar o que o técnico
    // já tiver digitado) e, se o template tiver um tipo padrão, já marca o
    // radio correspondente. Mesmo padrão de combo com busca usado em
    // "setor" na abertura de chamado (input + painel .menu-flutuante).
    var campoTextoComentario = document.getElementById('id_texto');
    var dadosRespostaRapidaEl = document.getElementById('dados-respostas-rapidas');
    var buscaRespostaRapida = document.getElementById('buscaRespostaRapida');
    var sugestoesRespostaRapida = document.getElementById('sugestoesRespostaRapida');

    if (dadosRespostaRapidaEl && buscaRespostaRapida && sugestoesRespostaRapida) {
        var respostasRapidas = JSON.parse(dadosRespostaRapidaEl.textContent);
        var itensAtuaisResposta = [];
        var indiceAtivoResposta = -1;

        function fecharSugestoesResposta() {
            sugestoesRespostaRapida.classList.add('d-none');
            sugestoesRespostaRapida.innerHTML = '';
            itensAtuaisResposta = [];
            indiceAtivoResposta = -1;
        }

        function selecionarResposta(item) {
            var textoAtual = campoTextoComentario.value.trim();
            campoTextoComentario.value = textoAtual
                ? textoAtual + '\n\n' + item.texto
                : item.texto;
            campoTextoComentario.focus();

            if (item.tipo) {
                var radio = document.getElementById('tipo_' + item.tipo);
                if (radio) radio.checked = true;
            }

            buscaRespostaRapida.value = '';
            fecharSugestoesResposta();
        }

        function destacarSugestaoAtivaResposta() {
            Array.prototype.forEach.call(sugestoesRespostaRapida.querySelectorAll('.menu-flutuante-item'), function (el, indice) {
                el.classList.toggle('ativo', indice === indiceAtivoResposta);
            });
        }

        function renderizarSugestoesResposta(lista) {
            itensAtuaisResposta = lista;
            indiceAtivoResposta = -1;
            sugestoesRespostaRapida.innerHTML = '';
            if (!lista.length) {
                fecharSugestoesResposta();
                return;
            }
            var grupoAnterior = null;
            lista.forEach(function (item) {
                if (item.grupo_label !== grupoAnterior) {
                    var rotulo = document.createElement('div');
                    rotulo.className = 'menu-flutuante-grupo';
                    rotulo.textContent = item.grupo_label;
                    sugestoesRespostaRapida.appendChild(rotulo);
                    grupoAnterior = item.grupo_label;
                }
                var botao = document.createElement('button');
                botao.type = 'button';
                botao.className = 'menu-flutuante-item';
                botao.textContent = item.tipo_label ? item.titulo + ' — ' + item.tipo_label : item.titulo;
                botao.addEventListener('mousedown', function (evento) {
                    evento.preventDefault();
                    selecionarResposta(item);
                });
                sugestoesRespostaRapida.appendChild(botao);
            });
            sugestoesRespostaRapida.classList.remove('d-none');
        }

        buscaRespostaRapida.addEventListener('input', function () {
            var termo = buscaRespostaRapida.value.trim().toLowerCase();
            if (!termo) {
                fecharSugestoesResposta();
                return;
            }
            renderizarSugestoesResposta(respostasRapidas.filter(function (item) {
                return item.titulo.toLowerCase().indexOf(termo) !== -1 ||
                    item.texto.toLowerCase().indexOf(termo) !== -1;
            }));
        });

        buscaRespostaRapida.addEventListener('focus', function () {
            if (!buscaRespostaRapida.value.trim()) {
                renderizarSugestoesResposta(respostasRapidas);
            }
        });

        buscaRespostaRapida.addEventListener('keydown', function (evento) {
            if (!itensAtuaisResposta.length) return;
            if (evento.key === 'ArrowDown') {
                evento.preventDefault();
                indiceAtivoResposta = Math.min(indiceAtivoResposta + 1, itensAtuaisResposta.length - 1);
                destacarSugestaoAtivaResposta();
            } else if (evento.key === 'ArrowUp') {
                evento.preventDefault();
                indiceAtivoResposta = Math.max(indiceAtivoResposta - 1, 0);
                destacarSugestaoAtivaResposta();
            } else if (evento.key === 'Enter' && indiceAtivoResposta >= 0) {
                evento.preventDefault();
                selecionarResposta(itensAtuaisResposta[indiceAtivoResposta]);
            } else if (evento.key === 'Escape') {
                fecharSugestoesResposta();
            }
        });

        buscaRespostaRapida.addEventListener('blur', function () {
            setTimeout(fecharSugestoesResposta, 150);
        });
    }
});
