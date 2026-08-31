document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('detalheTicket');
    var url = container.dataset.urlConsultarEquipamento;
    var ticketPk = container.dataset.ticketPk;

    document.querySelectorAll('input[data-consulta]').forEach(function (input) {
        var tipo = input.getAttribute('data-consulta');
        var info = document.getElementById('info-' + input.id);
        var timer = null;

        function consultar() {
            var patrimonio = input.value.trim();
            if (!patrimonio) {
                info.innerHTML = '';
                return;
            }
            fetch(url + '?patrimonio=' + encodeURIComponent(patrimonio) + '&ticket=' + ticketPk)
                .then(function (resp) { return resp.json(); })
                .then(function (dados) {
                    var indisponivel = !dados.encontrado ||
                        (tipo === 'entrada' && !dados.elegivel_entrada) ||
                        (tipo === 'saida' && !dados.elegivel_saida);
                    if (indisponivel) {
                        info.innerHTML = '<div class="text-danger small mt-1">Patrimônio indisponível. ' +
                            'Verifique que o patrimônio digitado corresponde ao do equipamento em questão.</div>';
                        return;
                    }
                    var linha = dados.categoria + ' ' + dados.marca + ' ' + dados.modelo +
                        ' — setor atual: ' + dados.setor + ' — status: ' + dados.status;
                    info.innerHTML = '<div class="small mt-1 text-success">' + linha + '</div>';
                });
        }

        input.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(consultar, 400);
        });
        consultar();
    });

    document.querySelectorAll('button[data-limpar]').forEach(function (botao) {
        botao.addEventListener('click', function () {
            var campo = document.getElementById(botao.getAttribute('data-limpar'));
            campo.value = '';
            campo.dispatchEvent(new Event('input'));
            campo.focus();
        });
    });

    var checkboxSemMovimentacao = document.getElementById('sem_movimentacao');
    var camposPatrimonio = document.querySelectorAll('input[data-consulta]');
    var botaoFecharChamado = document.getElementById('botaoFecharChamado');
    var hiddenConfirmarSemMovimentacao = document.getElementById('hiddenConfirmarSemMovimentacao');

    function atualizarBotaoFechar() {
        if (!botaoFecharChamado) return;
        var categoriaConfirmada = botaoFecharChamado.getAttribute('data-categoria-confirmada') === 'true';
        var tecnicoAtribuido = botaoFecharChamado.getAttribute('data-tecnico-atribuido') === 'true';
        var movimentacaoConfirmada = botaoFecharChamado.getAttribute('data-movimentacao-confirmada') === 'true';
        var semMovimentacaoMarcado = !!(checkboxSemMovimentacao && checkboxSemMovimentacao.checked);
        botaoFecharChamado.disabled = !(categoriaConfirmada && tecnicoAtribuido && (movimentacaoConfirmada || semMovimentacaoMarcado));
        if (hiddenConfirmarSemMovimentacao) {
            hiddenConfirmarSemMovimentacao.value = semMovimentacaoMarcado ? 'on' : '';
        }
    }

    if (checkboxSemMovimentacao) {
        checkboxSemMovimentacao.addEventListener('change', function () {
            camposPatrimonio.forEach(function (campo) {
                if (checkboxSemMovimentacao.checked) {
                    campo.value = '';
                    campo.dispatchEvent(new Event('input'));
                }
                campo.disabled = checkboxSemMovimentacao.checked;
            });
            atualizarBotaoFechar();
            // Marcar a caixa já é a confirmação em si — envia na hora, em vez
            // de depender de outro clique em "Movimentar equipamento" (que só
            // faz sentido pra quem está de fato registrando um patrimônio).
            // Sem isso, qualquer outra ação na página (ex: confirmar
            // classificação) recarrega a tela e perde essa marcação, já que
            // ela nunca tinha sido enviada ao servidor.
            if (checkboxSemMovimentacao.checked) {
                checkboxSemMovimentacao.closest('form').requestSubmit();
            }
        });
        camposPatrimonio.forEach(function (campo) {
            campo.addEventListener('input', function () {
                if (campo.value.trim() && checkboxSemMovimentacao.checked) {
                    checkboxSemMovimentacao.checked = false;
                    atualizarBotaoFechar();
                }
            });
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
