import bleach
from bleach.css_sanitizer import CSSSanitizer
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.db.models import Q
from django.utils.html import strip_tags

from .models import (
    ArtigoConhecimento,
    Categoria,
    ComentarioTicket,
    ItemConfiguracao,
    RespostaRapida,
    Setor,
    Ticket,
    patrimonio_validator,
)

ARTIGO_TAGS_PERMITIDAS = [
    "p", "br", "strong", "em", "u", "s", "span", "a",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "h1", "h2", "h3", "sub", "sup",
]
ARTIGO_ATRIBUTOS_PERMITIDOS = {
    "a": ["href", "target", "rel"],
    "span": ["style"],
    "p": ["style"],
    "li": ["style"],
    "blockquote": ["style"],
}
ARTIGO_CSS_PERMITIDO = CSSSanitizer(
    allowed_css_properties=["color", "background-color", "font-size", "text-align"]
)


def _categorias_agrupadas(incluir_pk=None):
    """Opções de categoria agrupadas por grupo (categoria "pai"), alfabéticas
    dentro de cada grupo. Só lista categorias ativas — exceto `incluir_pk`,
    que mantém visível a categoria já associada a um registro existente
    (ticket/artigo) mesmo que tenha virado inativa depois. Retorna
    (choices_para_optgroup, requer_patrimonio_por_id)."""
    categorias = list(
        Categoria.objects.filter(Q(ativo=True) | Q(pk=incluir_pk)).order_by("grupo", "nome")
    )
    grupo_labels = dict(Categoria.Grupo.choices)

    agrupadas = []
    grupo_atual = None
    opcoes_do_grupo = []
    for categoria in categorias:
        if categoria.grupo != grupo_atual:
            if opcoes_do_grupo:
                agrupadas.append((grupo_labels[grupo_atual], opcoes_do_grupo))
            grupo_atual = categoria.grupo
            opcoes_do_grupo = []
        opcoes_do_grupo.append((categoria.pk, categoria.nome))
    if opcoes_do_grupo:
        agrupadas.append((grupo_labels[grupo_atual], opcoes_do_grupo))

    requer_patrimonio_por_id = {
        str(categoria.pk): categoria.requer_patrimonio for categoria in categorias
    }
    return agrupadas, requer_patrimonio_por_id


def _categorias_meta():
    """Metadados por categoria (grupo e requer_patrimonio), usados pelo select
    de categoria de AbrirTicketForm para priorizar por grupo via JS. Só
    categorias ativas — a abertura de chamado nunca usa uma inativa."""
    return {
        str(categoria.pk): {
            "grupo": categoria.grupo, "requer_patrimonio": categoria.requer_patrimonio,
        }
        for categoria in Categoria.objects.filter(ativo=True)
    }


class CategoriaSelect(forms.Select):
    """Select de categoria que expõe requer_patrimonio e grupo de cada opção via
    data-requer-patrimonio/data-grupo, usados pelo JS para mostrar o campo de
    patrimônio e priorizar as categorias do grupo escolhido."""

    def __init__(self, *args, categorias_meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.categorias_meta = categorias_meta or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        meta = self.categorias_meta.get(str(value))
        if meta:
            if meta["requer_patrimonio"]:
                option["attrs"]["data-requer-patrimonio"] = "true"
            option["attrs"]["data-grupo"] = meta["grupo"]
        return option


class AbrirTicketForm(forms.Form):
    solicitante_ramal = forms.CharField(
        label="Ramal",
        error_messages={"required": "Informe o ramal."},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    solicitante_sala = forms.CharField(
        label="Sala (opcional)",
        required=False,
        help_text="Ajuda o técnico a localizar o equipamento, se for presencial.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 204"}),
    )
    setor = forms.ModelChoiceField(
        queryset=Setor.objects.order_by("nome"),
        label="Setor",
        empty_label="Selecione seu setor",
        error_messages={"required": "Selecione o setor."},
        widget=forms.Select(attrs={"class": "form-select d-none", "id": "id_setor"}),
    )
    grupo = forms.ChoiceField(
        label="Grupo do problema",
        error_messages={"required": "Selecione o grupo do problema."},
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Ajuda a encontrar a categoria certa no campo \"Categoria específica\".",
    )
    categoria_sugerida = forms.ModelChoiceField(
        queryset=Categoria.objects.filter(ativo=True).order_by("nome"),
        label="Categoria específica",
        error_messages={"required": "Selecione uma categoria."},
    )
    impacto = forms.ChoiceField(
        choices=Ticket.Impacto.choices,
        # "Nível de atendimento" já é o nome do N1/N2/N3 técnico (Ticket.nivel_atual,
        # usado no escalonamento) — chamar os dois campos pelo mesmo nome deixava
        # ambíguo, na tela do chamado, qual dos dois estava sendo mostrado.
        label="Abrangência do impacto",
        help_text="Quem ou o que está sendo impactado pelo problema.",
        error_messages={"required": "Selecione a abrangência do impacto."},
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    patrimonio = forms.CharField(
        label="Número de patrimônio do equipamento",
        required=False,
        validators=[patrimonio_validator],
        widget=forms.TextInput(attrs={
            "class": "form-control", "maxlength": "6",
            "placeholder": "6 dígitos, ex: 000123",
        }),
    )
    descricao = forms.CharField(
        label="Descreva o problema",
        help_text="Inclua mensagens de erro exatas, passos para reproduzir e horário do ocorrido.",
        error_messages={"required": "A descrição é obrigatória."},
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "style": "resize: vertical;"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo"].choices = [("", "Selecione um grupo...")] + list(Categoria.Grupo.choices)
        self.fields["categoria_sugerida"].widget = CategoriaSelect(
            attrs={"class": "form-select"}, categorias_meta=_categorias_meta()
        )
        categorias_ordenadas = [
            (str(categoria.pk), categoria.nome)
            for categoria in Categoria.objects.filter(ativo=True).order_by("nome")
        ]
        self.fields["categoria_sugerida"].choices = [("", "Sobre o que é seu problema?")] + categorias_ordenadas

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get("categoria_sugerida")
        patrimonio = cleaned_data.get("patrimonio", "").strip()

        if categoria and categoria.requer_patrimonio:
            if not patrimonio:
                self.add_error(
                    "patrimonio", "Informe o número de patrimônio do equipamento."
                )
            else:
                try:
                    cleaned_data["item_configuracao"] = ItemConfiguracao.objects.get(
                        patrimonio=patrimonio
                    )
                except ItemConfiguracao.DoesNotExist:
                    self.add_error(
                        "patrimonio", "Patrimônio não encontrado no cadastro de equipamentos."
                    )
        return cleaned_data


class ConfirmarClassificacaoForm(forms.Form):
    categoria_final = forms.ModelChoiceField(
        queryset=Categoria.objects.order_by("grupo", "nome"),
        label="Categoria final (confirmada pelo técnico)",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, categoria_atual_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Só categorias ativas — exceto a que o chamado já está usando, que
        # continua selecionável/visível mesmo se tiver virado inativa depois.
        self.fields["categoria_final"].queryset = Categoria.objects.filter(
            Q(ativo=True) | Q(pk=categoria_atual_id)
        ).order_by("grupo", "nome")
        choices, _ = _categorias_agrupadas(incluir_pk=categoria_atual_id)
        self.fields["categoria_final"].choices = choices


class CriarUsuarioAdmissaoForm(forms.Form):
    """Formulário do card "Criação de usuário" na tela do chamado — só
    aparece quando a categoria do chamado tem `habilita_criacao_usuario`
    marcado. E-mail é obrigatório porque é o que a pessoa vai usar depois
    pra definir a própria senha (ver services/recuperacao_senha.py)."""

    first_name = forms.CharField(
        label="Nome", error_messages={"required": "Informe o nome."},
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    last_name = forms.CharField(
        label="Sobrenome", error_messages={"required": "Informe o sobrenome."},
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    username = forms.CharField(
        label="Usuário (login)", error_messages={"required": "Informe o nome de usuário."},
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    email = forms.EmailField(
        label="E-mail",
        error_messages={"required": "Informe o e-mail.", "invalid": "Informe um e-mail válido."},
        widget=forms.EmailInput(attrs={"class": "form-control form-control-sm"}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username=username).exists():
            raise forms.ValidationError("Já existe um usuário com esse nome de login.")
        return username


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = ComentarioTicket
        fields = ["tipo", "texto"]
        widgets = {
            "tipo": forms.RadioSelect,
            "texto": forms.Textarea(attrs={
                "class": "form-control", "rows": 8,
                "placeholder": "Atualização, diagnóstico ou procedimento adotado neste chamado...",
            }),
        }


class ResponderTicketForm(forms.ModelForm):
    """Resposta do solicitante ao técnico — mesma tabela/área de
    ComentarioForm, mas sem o rádio de tipo: o tipo é sempre
    RESPOSTA_SOLICITANTE, fixado na view (ver responder_ticket_view)."""

    class Meta:
        model = ComentarioTicket
        fields = ["texto"]
        widgets = {
            "texto": forms.Textarea(attrs={
                "class": "form-control", "rows": 3,
                "placeholder": "Escreva sua resposta para o técnico...",
            }),
        }


class CadastrarEquipamentoForm(forms.ModelForm):
    class Meta:
        model = ItemConfiguracao
        fields = [
            "patrimonio", "categoria", "marca", "modelo", "setor", "status",
            "data_aquisicao", "data_validade_garantia",
            "nivel_cargo_desligado", "data_inicio_resguardo",
        ]
        widgets = {
            "patrimonio": forms.TextInput(attrs={"class": "form-control", "placeholder": "6 dígitos, ex: 000123"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "marca": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "setor": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "data_aquisicao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_validade_garantia": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "nivel_cargo_desligado": forms.Select(attrs={"class": "form-select"}),
            "data_inicio_resguardo": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean_marca(self):
        return self.cleaned_data["marca"].strip().title()

    def clean_modelo(self):
        return self.cleaned_data["modelo"].strip().title()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nivel_cargo_desligado"].required = False
        self.fields["nivel_cargo_desligado"].choices = [("", "Selecione...")] + list(
            ItemConfiguracao.NivelCargoDesligado.choices
        )
        self.fields["data_inicio_resguardo"].required = False

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("status") == ItemConfiguracao.Status.EM_RESGUARDO:
            if not cleaned_data.get("nivel_cargo_desligado"):
                self.add_error(
                    "nivel_cargo_desligado",
                    "Informe o cargo do funcionário desligado para calcular o prazo de resguardo.",
                )
            if not cleaned_data.get("data_inicio_resguardo"):
                self.add_error(
                    "data_inicio_resguardo",
                    "Informe a data de início do resguardo.",
                )
        return cleaned_data


class LoginForm(AuthenticationForm):
    manter_conectado = forms.BooleanField(
        label="Manter conectado",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control"})
        self.fields["password"].widget.attrs.update({"class": "form-control"})


class TrocarSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})


class EsqueciSenhaForm(forms.Form):
    username = forms.CharField(
        label="Usuário",
        error_messages={"required": "Informe seu usuário."},
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )


class ConfirmarCodigoForm(forms.Form):
    codigo = forms.CharField(
        label="Código recebido por e-mail",
        min_length=6, max_length=6,
        error_messages={"required": "Informe o código recebido por e-mail."},
        widget=forms.TextInput(attrs={
            "class": "form-control", "inputmode": "numeric",
            "autocomplete": "one-time-code", "placeholder": "000000",
        }),
    )


class RedefinirSenhaForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})


class EditarPerfilForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }
        labels = {
            "email": "E-mail institucional",
        }


class ArtigoForm(forms.ModelForm):
    class Meta:
        model = ArtigoConhecimento
        fields = ["titulo", "resumo", "categoria", "conteudo"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "resumo": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "conteudo": forms.Textarea(attrs={"class": "d-none", "id": "id_conteudo"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só categorias ativas — exceto a que o artigo já usa (se estiver
        # editando), que continua selecionável mesmo se tiver virado inativa.
        categoria_atual_id = self.instance.categoria_id
        self.fields["categoria"].queryset = Categoria.objects.filter(
            Q(ativo=True) | Q(pk=categoria_atual_id)
        )
        choices, _ = _categorias_agrupadas(incluir_pk=categoria_atual_id)
        self.fields["categoria"].choices = [("", "Nenhuma categoria relacionada")] + choices

    def clean_conteudo(self):
        conteudo = self.cleaned_data["conteudo"]
        limpo = bleach.clean(
            conteudo,
            tags=ARTIGO_TAGS_PERMITIDAS,
            attributes=ARTIGO_ATRIBUTOS_PERMITIDOS,
            css_sanitizer=ARTIGO_CSS_PERMITIDO,
            strip=True,
        )
        if not strip_tags(limpo).strip():
            raise forms.ValidationError("O conteúdo do artigo não pode ficar vazio.")
        return limpo


class RespostaRapidaForm(forms.ModelForm):
    class Meta:
        model = RespostaRapida
        fields = ["titulo", "grupo", "tipo_padrao", "texto"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "grupo": forms.Select(attrs={"class": "form-select"}),
            "tipo_padrao": forms.Select(attrs={"class": "form-select"}),
            "texto": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo"].required = False
        self.fields["grupo"].choices = [("", "Sem grupo")] + list(Categoria.Grupo.choices)
        self.fields["tipo_padrao"].required = False
        self.fields["tipo_padrao"].choices = [("", "Não marcar nenhum")] + [
            choice for choice in ComentarioTicket.Tipo.choices
            if choice[0] != ComentarioTicket.Tipo.RESPOSTA_SOLICITANTE
        ]
