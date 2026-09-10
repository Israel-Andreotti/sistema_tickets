"""Views só pra pré-visualizar as telas de erro (403.html/500.html) durante o
desenvolvimento — renderizam o template direto, sem depender de provocar o
erro de verdade (que o Django só troca pelo template customizado quando
DEBUG=False). A checagem de DEBUG fica aqui dentro (não só no urls.py) pra
essas rotas responderem 404 em produção mesmo que continuem registradas."""
from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def preview_erro_403(request):
    if not settings.DEBUG:
        raise Http404()
    return render(request, "403.html", status=403)


def preview_erro_500(request):
    if not settings.DEBUG:
        raise Http404()
    return render(request, "500.html", status=500)
