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
});
