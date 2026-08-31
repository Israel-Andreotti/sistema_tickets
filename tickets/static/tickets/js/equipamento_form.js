document.addEventListener('DOMContentLoaded', function () {
    var statusSelect = document.getElementById('id_status');
    var camposResguardo = document.getElementById('campos-resguardo');
    var nivelCargoSelect = document.getElementById('id_nivel_cargo_desligado');
    var dataInicioInput = document.getElementById('id_data_inicio_resguardo');
    var previsaoLiberacao = document.getElementById('previsao-liberacao-resguardo');

    if (!statusSelect || !camposResguardo) return;

    function atualizarVisibilidade() {
        camposResguardo.classList.toggle('d-none', statusSelect.value !== 'em_resguardo');
    }

    function atualizarPrevisao() {
        if (statusSelect.value !== 'em_resguardo' || !dataInicioInput.value || !nivelCargoSelect.value) {
            previsaoLiberacao.textContent = '';
            return;
        }
        var prazoDias = nivelCargoSelect.value === 'lideranca' ? 30 : 15;
        var dataInicio = new Date(dataInicioInput.value + 'T00:00:00');
        var dataFim = new Date(dataInicio.getTime() + prazoDias * 24 * 60 * 60 * 1000);
        var dataFormatada = dataFim.toLocaleDateString('pt-BR');
        previsaoLiberacao.textContent = 'Previsão de liberação: ' + dataFormatada + ' (' + prazoDias + ' dias de resguardo)';
    }

    statusSelect.addEventListener('change', function () {
        atualizarVisibilidade();
        atualizarPrevisao();
    });
    nivelCargoSelect.addEventListener('change', atualizarPrevisao);
    dataInicioInput.addEventListener('input', atualizarPrevisao);

    atualizarVisibilidade();
    atualizarPrevisao();
});
