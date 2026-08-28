document.addEventListener('DOMContentLoaded', function () {
    var grupoSelect = document.getElementById('id_grupo');
    var categoriaSelect = document.getElementById('id_categoria_sugerida');
    var campoPatrimonio = document.getElementById('campo-patrimonio');
    var inputPatrimonio = document.getElementById('id_patrimonio');
    var campoNivelAtendimento = document.getElementById('campo-nivel-atendimento');

    // Quando o patrimônio não aparece, "Nível de atendimento" ocupa a linha
    // toda — senão sobra um vão vazio ao lado dele (metade da linha sem uso).
    function atualizarVisibilidade() {
        var opcaoSelecionada = categoriaSelect.options[categoriaSelect.selectedIndex];
        var requerPatrimonio = opcaoSelecionada ? opcaoSelecionada.getAttribute('data-requer-patrimonio') : null;
        if (requerPatrimonio === 'true') {
            campoPatrimonio.classList.remove('d-none');
            campoNivelAtendimento.classList.remove('col-md-12');
            campoNivelAtendimento.classList.add('col-md-6');
        } else {
            campoPatrimonio.classList.add('d-none');
            inputPatrimonio.value = '';
            campoNivelAtendimento.classList.remove('col-md-6');
            campoNivelAtendimento.classList.add('col-md-12');
        }
    }

    // Guarda a ordem original (alfabética) das categorias, pra poder
    // reordenar sem perder nenhuma opção quando o grupo muda.
    var opcaoPlaceholder = categoriaSelect.options[0];
    var opcoesOriginais = Array.prototype.slice.call(categoriaSelect.options, 1);

    function priorizarPorGrupo() {
        var grupoEscolhido = grupoSelect.value;
        var valorAtual = categoriaSelect.value;

        categoriaSelect.innerHTML = '';
        categoriaSelect.appendChild(opcaoPlaceholder);

        if (!grupoEscolhido) {
            opcoesOriginais.forEach(function (opcao) { categoriaSelect.appendChild(opcao); });
        } else {
            var doGrupo = opcoesOriginais.filter(function (o) { return o.getAttribute('data-grupo') === grupoEscolhido; });
            var outras = opcoesOriginais.filter(function (o) { return o.getAttribute('data-grupo') !== grupoEscolhido; });
            var labelGrupo = grupoSelect.options[grupoSelect.selectedIndex].text;

            var optgroupDoGrupo = document.createElement('optgroup');
            optgroupDoGrupo.label = labelGrupo;
            doGrupo.forEach(function (opcao) { optgroupDoGrupo.appendChild(opcao); });

            var optgroupOutras = document.createElement('optgroup');
            optgroupOutras.label = 'Outras categorias';
            outras.forEach(function (opcao) { optgroupOutras.appendChild(opcao); });

            categoriaSelect.appendChild(optgroupDoGrupo);
            categoriaSelect.appendChild(optgroupOutras);
        }

        categoriaSelect.value = valorAtual;
    }

    grupoSelect.addEventListener('change', priorizarPorGrupo);
    categoriaSelect.addEventListener('change', atualizarVisibilidade);
    atualizarVisibilidade();
    // Reaplica a priorização já no carregamento — necessário quando a página
    // volta com "grupo" já preenchido (erro de validação em outro campo,
    // como categoria não selecionada), já que o evento "change" do grupo só
    // dispara com uma interação do usuário, não com o valor pré-selecionado
    // vindo do servidor.
    priorizarPorGrupo();

    // Busca de setor: o <select> real fica escondido (d-none) e continua
    // sendo o que é de fato enviado no formulário; o campo de texto só
    // filtra a lista de sugestões e, ao escolher uma, preenche o select.
    var setorSelect = document.getElementById('id_setor');
    var setorBusca = document.getElementById('setorBusca');
    var setorSugestoes = document.getElementById('setorSugestoes');
    var opcoesSetor = Array.prototype.slice.call(setorSelect.options, 1).map(function (opcao) {
        return { valor: opcao.value, texto: opcao.text };
    });
    var itensAtuais = [];
    var indiceAtivo = -1;

    function fecharSugestoesSetor() {
        setorSugestoes.classList.add('d-none');
        setorSugestoes.innerHTML = '';
        itensAtuais = [];
        indiceAtivo = -1;
    }

    function selecionarSetor(item) {
        setorSelect.value = item.valor;
        setorBusca.value = item.texto;
        fecharSugestoesSetor();
    }

    function destacarSugestaoAtiva() {
        Array.prototype.forEach.call(setorSugestoes.children, function (el, indice) {
            el.classList.toggle('active', indice === indiceAtivo);
        });
    }

    function renderizarSugestoesSetor(lista) {
        itensAtuais = lista;
        indiceAtivo = -1;
        setorSugestoes.innerHTML = '';
        if (!lista.length) {
            fecharSugestoesSetor();
            return;
        }
        lista.forEach(function (item) {
            var botao = document.createElement('button');
            botao.type = 'button';
            botao.className = 'list-group-item list-group-item-action';
            botao.textContent = item.texto;
            botao.addEventListener('mousedown', function (evento) {
                evento.preventDefault();
                selecionarSetor(item);
            });
            setorSugestoes.appendChild(botao);
        });
        setorSugestoes.classList.remove('d-none');
    }

    setorBusca.addEventListener('input', function () {
        setorSelect.value = '';
        var termo = setorBusca.value.trim().toLowerCase();
        if (!termo) {
            fecharSugestoesSetor();
            return;
        }
        renderizarSugestoesSetor(opcoesSetor.filter(function (item) {
            return item.texto.toLowerCase().indexOf(termo) !== -1;
        }));
    });

    setorBusca.addEventListener('keydown', function (evento) {
        if (!itensAtuais.length) return;
        if (evento.key === 'ArrowDown') {
            evento.preventDefault();
            indiceAtivo = Math.min(indiceAtivo + 1, itensAtuais.length - 1);
            destacarSugestaoAtiva();
        } else if (evento.key === 'ArrowUp') {
            evento.preventDefault();
            indiceAtivo = Math.max(indiceAtivo - 1, 0);
            destacarSugestaoAtiva();
        } else if (evento.key === 'Enter' && indiceAtivo >= 0) {
            evento.preventDefault();
            selecionarSetor(itensAtuais[indiceAtivo]);
        } else if (evento.key === 'Escape') {
            fecharSugestoesSetor();
        }
    });

    setorBusca.addEventListener('blur', function () {
        setTimeout(fecharSugestoesSetor, 150);
    });

    if (setorSelect.value) {
        var setorJaSelecionado = opcoesSetor.filter(function (item) { return item.valor === setorSelect.value; })[0];
        if (setorJaSelecionado) setorBusca.value = setorJaSelecionado.texto;
    }

    // Sugestão de artigos da base de conhecimento a partir da descrição
    // digitada, antes de enviar o chamado.
    var campoDescricao = document.getElementById('id_descricao');
    var painelSugestoesArtigos = document.getElementById('sugestoesArtigos');
    var listaSugestoesArtigos = document.getElementById('listaSugestoesArtigos');
    var timerSugestoesArtigos = null;

    function buscarSugestoesArtigos() {
        var termo = campoDescricao.value.trim();
        if (termo.length < 5) {
            painelSugestoesArtigos.classList.add('d-none');
            return;
        }
        fetch(painelSugestoesArtigos.dataset.urlSugestoes + '?q=' + encodeURIComponent(termo))
            .then(function (resp) { return resp.json(); })
            .then(function (dados) {
                if (!dados.artigos.length) {
                    painelSugestoesArtigos.classList.add('d-none');
                    return;
                }
                listaSugestoesArtigos.innerHTML = '';
                dados.artigos.forEach(function (artigo) {
                    var link = document.createElement('a');
                    link.href = artigo.url;
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.className = 'card card-body py-2 text-decoration-none text-reset';

                    var titulo = document.createElement('div');
                    titulo.className = 'small fw-semibold';
                    titulo.textContent = '📄 ' + artigo.titulo;
                    link.appendChild(titulo);

                    if (artigo.resumo) {
                        var resumo = document.createElement('div');
                        resumo.className = 'small text-muted';
                        resumo.textContent = artigo.resumo;
                        link.appendChild(resumo);
                    }

                    listaSugestoesArtigos.appendChild(link);
                });
                painelSugestoesArtigos.classList.remove('d-none');
            });
    }

    campoDescricao.addEventListener('input', function () {
        clearTimeout(timerSugestoesArtigos);
        timerSugestoesArtigos = setTimeout(buscarSugestoesArtigos, 400);
    });

    var formulario = document.getElementById('formAbrirChamado');
    var botao = document.getElementById('botaoAbrirChamado');
    var botaoTexto = document.getElementById('botaoAbrirChamadoTexto');
    var botaoSpinner = document.getElementById('botaoAbrirChamadoSpinner');
    formulario.addEventListener('submit', function () {
        botao.disabled = true;
        botaoTexto.textContent = 'Abrindo chamado...';
        botaoSpinner.classList.remove('d-none');
    });
});
