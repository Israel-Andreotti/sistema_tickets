import bleach
from bleach.css_sanitizer import CSSSanitizer
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils.html import strip_tags

from .models import (
    ArtigoConhecimento,
    Categoria,
    ComentarioTicket,
    ItemConfiguracao,
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


def _categorias_agrupadas():
    """Opções de categoria agrupadas por grupo (categoria "pai"), alfabéticas
    dentro de cada grupo. Retorna (choices_para_optgroup, requer_patrimonio_por_id)."""
    categorias = list(Categoria.objects.order_by("grupo", "nome"))
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
    de categoria de AbrirTicketForm para priorizar por grupo via JS."""
    return {
        str(categoria.pk): {
            "grupo": categoria.grupo, "requer_patrimonio": categoria.requer_patrimonio,
        }
        for categoria in Categoria.objects.all()
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
    solicitante_nome = forms.CharField(
        label="Nome",
        error_messages={"required": "Informe seu nome."},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    solicitante_ramal = forms.CharField(
        label="Ramal",
        error_messages={"required": "Informe o ramal."},
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    solicitante_sala = forms.CharField(
        label="Sala",
        error_messages={"required": "Informe a sala."},
        widget=forms.TextInput(attrs={"class": "form-control"}),
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
        help_text="Ajuda a encontrar a categoria certa na lista abaixo.",
    )
    categoria_sugerida = forms.ModelChoiceField(
        queryset=Categoria.objects.order_by("nome"),
        label="Categoria específica",
        error_messages={"required": "Selecione uma categoria."},
    )
    impacto = forms.ChoiceField(
        choices=Ticket.Impacto.choices,
        label="Nível de atendimento",
        help_text="Quem ou o que está sendo impactado pelo problema.",
        error_messages={"required": "Selecione o nível de atendimento."},
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
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 7, "style": "resize: vertical;"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["solicitante_nome"].initial = user.get_full_name() or user.username
        self.fields["grupo"].choices = [("", "Selecione um grupo...")] + list(Categoria.Grupo.choices)
        self.fields["categoria_sugerida"].widget = CategoriaSelect(
            attrs={"class": "form-select"}, categorias_meta=_categorias_meta()
        )
        categorias_ordenadas = [
            (str(categoria.pk), categoria.nome)
            for categoria in Categoria.objects.order_by("nome")
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices, _ = _categorias_agrupadas()
        self.fields["categoria_final"].choices = choices


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = ComentarioTicket
        fields = ["tipo", "texto"]
        widgets = {
            "tipo": forms.RadioSelect,
            "texto": forms.Textarea(attrs={
                "class": "form-control", "rows": 3,
                "placeholder": "Atualização, diagnóstico ou procedimento adotado neste chamado...",
            }),
        }


class CadastrarEquipamentoForm(forms.ModelForm):
    class Meta:
        model = ItemConfiguracao
        fields = [
            "patrimonio", "categoria", "marca", "modelo", "setor", "status",
            "data_aquisicao", "data_validade_garantia",
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
        }


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control"})
        self.fields["password"].widget.attrs.update({"class": "form-control"})


class TrocarSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})


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
        choices, _ = _categorias_agrupadas()
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
