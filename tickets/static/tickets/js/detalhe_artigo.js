document.addEventListener('DOMContentLoaded', function () {
    // 👍/👎 no artigo, quando a pessoa chegou aqui por uma sugestão durante
    // a abertura de chamado (ver detalhe_artigo_view: mostrar_feedback_artigo).
    var bloco = document.getElementById('feedbackArtigoBloco');
    if (!bloco) return;

    var botoes = document.getElementById('feedbackArtigoBotoes');
    var confirmacao = document.getElementById('feedbackArtigoConfirmacao');
    var csrfToken = bloco.querySelector('[name=csrfmiddlewaretoken]').value;

    botoes.querySelectorAll('button').forEach(function (botao) {
        botao.addEventListener('click', function () {
            var util = botao.dataset.util === 'true';
            fetch(bloco.dataset.urlFeedback, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ util: util }),
            }).then(function (resp) {
                if (!resp.ok) return;
                botoes.classList.add('d-none');
                confirmacao.classList.remove('d-none');
            });
        });
    });
});
