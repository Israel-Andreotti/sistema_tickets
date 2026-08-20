document.addEventListener('DOMContentLoaded', function () {
    var toggleBtn = document.getElementById('toggleSidebar');
    toggleBtn.addEventListener('click', function () {
        var colapsada = document.documentElement.getAttribute('data-sidebar-collapsed') === 'true';
        document.documentElement.setAttribute('data-sidebar-collapsed', (!colapsada).toString());
        localStorage.setItem('sidebarCollapsed', (!colapsada).toString());
    });

    var themeSwitch = document.getElementById('themeSwitch');
    var iconeSol = document.getElementById('iconeSol');
    var iconeLua = document.getElementById('iconeLua');

    function atualizarIconeTema(escuro) {
        iconeSol.classList.toggle('d-none', escuro);
        iconeLua.classList.toggle('d-none', !escuro);
    }

    var temaEscuro = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    themeSwitch.checked = temaEscuro;
    atualizarIconeTema(temaEscuro);

    themeSwitch.addEventListener('change', function () {
        var tema = themeSwitch.checked ? 'dark' : 'light';
        document.documentElement.setAttribute('data-bs-theme', tema);
        localStorage.setItem('theme', tema);
        atualizarIconeTema(themeSwitch.checked);
    });

    // Campos de data em dd/mm/aaaa forçado: o <input type="date"> nativo
    // mostra o formato do sistema operacional de quem usa (nem sempre
    // dd/mm/aaaa, mesmo com lang="pt-BR"), então usamos texto com
    // máscara e só convertemos pra ISO (yyyy-mm-dd) ao enviar o form.
    document.querySelectorAll('input[data-date-mask]').forEach(function (campo) {
        if (campo.value && /^\d{4}-\d{2}-\d{2}$/.test(campo.value)) {
            var partesIso = campo.value.split('-');
            campo.value = partesIso[2] + '/' + partesIso[1] + '/' + partesIso[0];
        }

        campo.addEventListener('input', function () {
            var digitos = campo.value.replace(/\D/g, '').slice(0, 8);
            var formatado = digitos;
            if (digitos.length > 4) {
                formatado = digitos.slice(0, 2) + '/' + digitos.slice(2, 4) + '/' + digitos.slice(4);
            } else if (digitos.length > 2) {
                formatado = digitos.slice(0, 2) + '/' + digitos.slice(2);
            }
            campo.value = formatado;
        });

        var formularioDoCampo = campo.closest('form');
        if (formularioDoCampo) {
            formularioDoCampo.addEventListener('submit', function () {
                var partesBr = campo.value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
                campo.value = partesBr ? (partesBr[3] + '-' + partesBr[2] + '-' + partesBr[1]) : '';
            });
        }
    });
});
