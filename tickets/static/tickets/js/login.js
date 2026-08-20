document.addEventListener('DOMContentLoaded', function () {
    var botao = document.getElementById('togglePassword');
    var campoSenha = document.getElementById('id_password');
    var olhoAberto = document.getElementById('iconeOlhoAberto');
    var olhoFechado = document.getElementById('iconeOlhoFechado');

    botao.addEventListener('click', function () {
        var mostrando = campoSenha.type === 'text';
        campoSenha.type = mostrando ? 'password' : 'text';
        olhoAberto.classList.toggle('d-none', !mostrando);
        olhoFechado.classList.toggle('d-none', mostrando);
        var rotulo = mostrando ? 'Mostrar senha' : 'Ocultar senha';
        botao.setAttribute('aria-label', rotulo);
        botao.setAttribute('title', rotulo);
    });
});
