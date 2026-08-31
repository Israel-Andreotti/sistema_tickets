// Melhora todo <select class="form-select"> visível da página com um botão +
// painel flutuante (.menu-flutuante) no lugar do popup nativo — evita um bug
// de renderização do Chromium em modo escuro onde o hover de cada opção só
// cobre a largura do texto, não a linha inteira, e deixa o hover/seleção com
// a cor de marca do app em vez do cinza genérico do navegador.
//
// O <select> original continua no DOM (só escondido) e é o que de fato vale
// pro formulário — clicar num item do painel só ajusta o valor dele e dispara
// um evento "change" de verdade, então qualquer lógica que já escuta esse
// select (ex: abrir_ticket.js reordenando categorias por grupo, mostrando o
// campo de patrimônio) continua funcionando sem precisar saber que esse
// componente existe.
//
// Selects que já têm sua própria interface customizada (ex: a busca de setor
// em abrir_ticket.js) devem vir com "d-none" desde o carregamento da página,
// pra esse script pular eles.
document.addEventListener('DOMContentLoaded', function () {
    function melhorarSelect(select) {
        select.classList.add('d-none');

        var botao = document.createElement('button');
        botao.type = 'button';
        botao.className = select.className.replace('d-none', '').trim() + ' text-start';
        botao.setAttribute('aria-haspopup', 'listbox');
        botao.setAttribute('aria-expanded', 'false');
        if (select.disabled) botao.disabled = true;

        // O <label for="..."> continua apontando pro <select> escondido —
        // sem isso, clicar no rótulo do campo não focaria mais em nada.
        if (select.id) {
            botao.id = select.id + '_botao';
            var rotulo = document.querySelector('label[for="' + select.id + '"]');
            if (rotulo) rotulo.setAttribute('for', botao.id);
        }

        var textoBotao = document.createElement('span');
        botao.appendChild(textoBotao);

        var menu = document.createElement('div');
        menu.className = 'menu-flutuante d-none';
        menu.setAttribute('role', 'listbox');
        menu.style.position = 'absolute';
        menu.style.zIndex = '1050';
        menu.style.width = '100%';

        var wrapper = document.createElement('div');
        wrapper.className = 'position-relative';
        select.insertAdjacentElement('afterend', wrapper);
        wrapper.appendChild(botao);
        wrapper.appendChild(menu);

        function opcoesFocaveis() {
            return Array.prototype.slice.call(menu.querySelectorAll('button[data-valor]'));
        }

        function criarItem(opcao) {
            var item = document.createElement('button');
            item.type = 'button';
            item.className = 'menu-flutuante-item' + (opcao.value === select.value ? ' ativo' : '');
            item.setAttribute('role', 'option');
            item.dataset.valor = opcao.value;
            item.textContent = opcao.text;
            item.addEventListener('click', function () {
                select.value = opcao.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                atualizarTextoBotao();
                fecharMenu();
                botao.focus();
            });
            item.addEventListener('keydown', navegarComTeclado);
            return item;
        }

        function construirOpcoes() {
            menu.innerHTML = '';
            Array.prototype.forEach.call(select.children, function (filho) {
                if (filho.tagName === 'OPTGROUP') {
                    var rotulo = document.createElement('div');
                    rotulo.className = 'menu-flutuante-grupo';
                    rotulo.textContent = filho.label;
                    menu.appendChild(rotulo);
                    Array.prototype.forEach.call(filho.children, function (opcao) {
                        menu.appendChild(criarItem(opcao));
                    });
                } else if (filho.tagName === 'OPTION') {
                    menu.appendChild(criarItem(filho));
                }
            });
        }

        function navegarComTeclado(evento) {
            var itens = opcoesFocaveis();
            var indice = itens.indexOf(evento.target);
            if (evento.key === 'ArrowDown') {
                evento.preventDefault();
                (itens[indice + 1] || itens[0]).focus();
            } else if (evento.key === 'ArrowUp') {
                evento.preventDefault();
                (itens[indice - 1] || itens[itens.length - 1]).focus();
            } else if (evento.key === 'Escape') {
                fecharMenu();
                botao.focus();
            }
        }

        function fecharMenu() {
            menu.classList.add('d-none');
            botao.setAttribute('aria-expanded', 'false');
        }

        function abrirMenu() {
            construirOpcoes();
            menu.classList.remove('d-none');
            botao.setAttribute('aria-expanded', 'true');
        }

        function atualizarTextoBotao() {
            var opcaoAtual = select.options[select.selectedIndex];
            textoBotao.textContent = opcaoAtual ? opcaoAtual.text : '';
        }

        botao.addEventListener('click', function () {
            if (menu.classList.contains('d-none')) {
                abrirMenu();
            } else {
                fecharMenu();
            }
        });

        botao.addEventListener('keydown', function (evento) {
            if (evento.key === 'ArrowDown' || evento.key === 'Enter' || evento.key === ' ') {
                evento.preventDefault();
                abrirMenu();
                var itens = opcoesFocaveis();
                if (itens[0]) itens[0].focus();
            }
        });

        document.addEventListener('click', function (evento) {
            if (!botao.contains(evento.target) && !menu.contains(evento.target)) {
                fecharMenu();
            }
        });

        select.addEventListener('change', atualizarTextoBotao);
        atualizarTextoBotao();
    }

    document.querySelectorAll('select.form-select:not(.d-none)').forEach(melhorarSelect);
});
