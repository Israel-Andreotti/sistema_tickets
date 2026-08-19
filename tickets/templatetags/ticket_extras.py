from django import template

register = template.Library()

_CORES_AVATAR = ["#0e6e68", "#2b5d7e", "#8a5a3b", "#6b5b95", "#a4342c", "#4c6b3a"]

# Faixas de exibição apenas — prioridade_calculada vai de 1 a 25
# (peso_categoria × peso_setor, ambos 1-5). Não é uma RN, é só como a
# tabela agrupa visualmente; ajuste aqui se quiser outra granularidade.
_FAIXAS_PRIORIDADE = [
    (17, "Urgente", "bg-danger"),
    (10, "Alta", "bg-warning text-dark"),
    (5, "Média", "bg-info text-dark"),
    (0, "Baixa", "bg-success"),
]


@register.filter
def iniciais(nome):
    partes = [p for p in (nome or "").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


@register.filter
def cor_avatar(nome):
    indice = sum(ord(c) for c in nome or "") % len(_CORES_AVATAR)
    return _CORES_AVATAR[indice]


@register.filter
def prioridade_label(valor):
    if valor is None:
        return "—"
    for limite, label, _classe in _FAIXAS_PRIORIDADE:
        if valor >= limite:
            return label
    return "Baixa"


@register.filter
def prioridade_classe(valor):
    if valor is None:
        return "bg-secondary"
    for limite, _label, classe in _FAIXAS_PRIORIDADE:
        if valor >= limite:
            return classe
    return "bg-success"
