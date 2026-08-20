document.addEventListener('DOMContentLoaded', function () {
    var Size = Quill.import('attributors/style/size');
    Size.whitelist = ['small', false, 'large', 'huge'];
    Quill.register(Size, true);

    var Align = Quill.import('attributors/style/align');
    Quill.register(Align, true);

    var Color = Quill.import('attributors/style/color');
    Quill.register(Color, true);

    var Background = Quill.import('attributors/style/background');
    Quill.register(Background, true);

    var campoOculto = document.getElementById('id_conteudo');
    var conteudoInicial = campoOculto.value;
    campoOculto.value = '';

    var quill = new Quill('#editor-conteudo', {
        theme: 'snow',
        modules: {
            toolbar: [
                [{ size: ['small', false, 'large', 'huge'] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ color: [] }, { background: [] }],
                [{ list: 'ordered' }, { list: 'bullet' }],
                [{ align: [] }],
                ['link', 'blockquote', 'code-block'],
                ['clean'],
            ],
        },
    });

    if (conteudoInicial.trim()) {
        quill.clipboard.dangerouslyPasteHTML(conteudoInicial);
    }

    campoOculto.closest('form').addEventListener('submit', function () {
        campoOculto.value = quill.root.innerHTML;
    });
});
