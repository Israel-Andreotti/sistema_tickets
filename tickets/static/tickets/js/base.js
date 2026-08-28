// Ao voltar pela navegação do navegador, o Chrome/Firefox pode restaurar um
// retrato congelado da página (bfcache) em vez de buscar o estado atual do
// servidor — depois de marcar uma notificação como lida (ou qualquer outra
// ação que muda o servidor) isso faz a página "voltar" parecendo desfeita.
// Forçamos um reload nesse caso pra sempre refletir o estado real.
window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
        window.location.reload();
    }
});

document.addEventListener('DOMContentLoaded', function () {
    // A tela de login não tem sidebar — nenhum destes elementos existe nela,
    // já que base.js é compartilhado por todas as páginas.
    var toggleBtn = document.getElementById('toggleSidebar');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            var colapsada = document.documentElement.getAttribute('data-sidebar-collapsed') === 'true';
            document.documentElement.setAttribute('data-sidebar-collapsed', (!colapsada).toString());
            localStorage.setItem('sidebarCollapsed', (!colapsada).toString());
        });
    }

    var toggleMobileBtn = document.getElementById('toggleMobileMenu');
    var backdrop = document.getElementById('mobileMenuBackdrop');
    var sidebarPrincipal = document.getElementById('sidebarPrincipal');
    if (toggleMobileBtn && backdrop && sidebarPrincipal) {
        var definirMenuMobileAberto = function (aberto) {
            document.documentElement.setAttribute('data-mobile-menu-aberto', aberto.toString());
            toggleMobileBtn.setAttribute('aria-expanded', aberto.toString());
        };

        toggleMobileBtn.addEventListener('click', function () {
            var aberto = document.documentElement.getAttribute('data-mobile-menu-aberto') === 'true';
            definirMenuMobileAberto(!aberto);
        });
        backdrop.addEventListener('click', function () { definirMenuMobileAberto(false); });
        sidebarPrincipal.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () { definirMenuMobileAberto(false); });
        });
        window.addEventListener('resize', function () {
            if (window.innerWidth >= 768) definirMenuMobileAberto(false);
        });
    }

    // A tela de login não tem sidebar (logo esse botão não existe nela) —
    // por isso o guard, já que base.js é compartilhado por todas as páginas.
    var themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        var iconeSol = document.getElementById('iconeSol');
        var iconeLua = document.getElementById('iconeLua');

        var atualizarIconeTema = function (escuro) {
            iconeSol.classList.toggle('d-none', escuro);
            iconeLua.classList.toggle('d-none', !escuro);
        };

        atualizarIconeTema(document.documentElement.getAttribute('data-bs-theme') === 'dark');

        themeToggleBtn.addEventListener('click', function () {
            var escuroAtual = document.documentElement.getAttribute('data-bs-theme') === 'dark';
            var tema = escuroAtual ? 'light' : 'dark';
            document.documentElement.setAttribute('data-bs-theme', tema);
            localStorage.setItem('theme', tema);
            atualizarIconeTema(!escuroAtual);
        });
    }

    // A tela de login não tem sino de notificações — por isso o guard.
    var notificacaoWrapper = document.getElementById('notificacaoDropdownWrapper');
    var notificacaoBtn = document.getElementById('notificacaoBtn');
    var notificacaoMenu = document.getElementById('notificacaoMenu');
    var notificacaoBadge = document.getElementById('notificacaoBadge');
    if (notificacaoWrapper && notificacaoBtn && notificacaoMenu && notificacaoBadge) {
        notificacaoWrapper.addEventListener('show.bs.dropdown', function () {
            fetch(notificacaoBtn.dataset.urlDropdown)
                .then(function (resp) { return resp.text(); })
                .then(function (html) { notificacaoMenu.innerHTML = html; });
        });

        var atualizarBadgeNotificacoes = function () {
            fetch(notificacaoBtn.dataset.urlNovas)
                .then(function (resp) { return resp.json(); })
                .then(function (dados) {
                    if (dados.total_nao_lidas > 0) {
                        notificacaoBadge.textContent = dados.total_nao_lidas;
                        notificacaoBadge.classList.remove('d-none');
                    } else {
                        notificacaoBadge.classList.add('d-none');
                    }
                });
        };
        setInterval(atualizarBadgeNotificacoes, 20000);
    }
});
