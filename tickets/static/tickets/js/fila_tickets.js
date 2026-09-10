document.addEventListener('DOMContentLoaded', function () {
    var banner = document.getElementById('bannerNovosChamados');
    var texto = document.getElementById('textoNovosChamados');
    var tituloOriginal = document.title;
    var ultimoId = banner.dataset.ultimoId || 0;

    var params = new URLSearchParams(window.location.search);
    params.set('desde', ultimoId);
    var url = banner.dataset.urlNovos + '?' + params.toString();

    var intervalo = setInterval(function () {
        fetch(url)
            .then(function (resp) { return resp.json(); })
            .then(function (dados) {
                if (dados.novos > 0) {
                    texto.textContent = dados.novos === 1
                        ? '1 novo chamado disponível.'
                        : dados.novos + ' novos chamados disponíveis.';
                    banner.classList.remove('d-none');
                    document.title = '🔔 (' + dados.novos + ') ' + tituloOriginal;
                    clearInterval(intervalo);
                }
            });
    }, 20000);

    // Alternância lista/kanban — preferência salva no localStorage, mesmo
    // mecanismo do tema claro/escuro (o atributo em <html> já vem certo
    // desde tema-inicial.js; aqui só reflete isso nos botões e reage ao clique).
    var botaoLista = document.getElementById('botaoVisualizacaoLista');
    var botaoKanban = document.getElementById('botaoVisualizacaoKanban');

    function aplicarVisualizacao(visualizacao) {
        if (visualizacao === 'kanban') {
            document.documentElement.setAttribute('data-fila-visualizacao', 'kanban');
        } else {
            document.documentElement.removeAttribute('data-fila-visualizacao');
        }
        botaoKanban.classList.toggle('btn-primary', visualizacao === 'kanban');
        botaoKanban.classList.toggle('btn-outline-primary', visualizacao !== 'kanban');
        botaoLista.classList.toggle('btn-primary', visualizacao !== 'kanban');
        botaoLista.classList.toggle('btn-outline-primary', visualizacao === 'kanban');
    }

    aplicarVisualizacao(localStorage.getItem('filaVisualizacao') === 'kanban' ? 'kanban' : 'lista');

    botaoLista.addEventListener('click', function () {
        localStorage.setItem('filaVisualizacao', 'lista');
        aplicarVisualizacao('lista');
    });
    botaoKanban.addEventListener('click', function () {
        localStorage.setItem('filaVisualizacao', 'kanban');
        aplicarVisualizacao('kanban');
    });
});
