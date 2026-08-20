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
});
