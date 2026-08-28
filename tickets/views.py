import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count, OuterRef, Q, Subquery
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import (
    AbrirTicketForm,
    ArtigoForm,
    CadastrarEquipamentoForm,
    ComentarioForm,
    ConfirmarClassificacaoForm,
    EditarPerfilForm,
    TrocarSenhaForm,
)
from .models import (
    ArtigoConhecimento,
    Categoria,
    ComentarioTicket,
    HistoricoSLA,
    ItemConfiguracao,
    Notificacao,
    Setor,
    Ticket,
)
from .services.classificacao import abrir_ticket, atribuir_tecnico, confirmar_classificacao_final
from .services.desvio import classificar_desvio
from .services.equipamento import (
    equipamento_elegivel_para_entrada,
    equipamento_elegivel_para_saida,
    movimentar_equipamento,
    obter_setor_ti,
    registrar_sem_movimentacao,
)
from .services.notificacoes import marcar_como_lida, marcar_todas_como_lidas, notificar
from .services.parametros import ParametroNaoConfigurado
from .services.sla import fechar_ticket

def _tem_acesso_operacional(user):
    """Acesso operacional pleno ao sistema — fila, histórico, base de conhecimento,
    SLA por categoria e ações em chamados: técnicos, gestores de setor e
    superusuários têm todos o mesmo nível de acesso aqui. O Django admin (/admin/)
    é a única área que continua exclusiva a superusuários (is_staff sozinho não
    concede acesso a ele, e gestores não recebem is_staff)."""
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or Setor.objects.filter(gestor=user).exists()
    )


tecnico_required = user_passes_test(_tem_acesso_operacional, login_url="login")
acesso_equipamentos_required = tecnico_required
ver_slas_required = tecnico_required


@login_required
def portal_view(request):
    return render(request, "tickets/portal.html")


def obter_ip_cliente(request):
    """Prioriza X-Forwarded-For (caso a aplicação rode atrás de um proxy no
    hospital); cai para REMOTE_ADDR quando ausente."""
    encaminhado_por = request.META.get("HTTP_X_FORWARDED_FOR")
    if encaminhado_por:
        return encaminhado_por.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@login_required
def abrir_ticket_view(request):
    if request.method == "POST":
        form = AbrirTicketForm(request.POST, user=request.user)
        if form.is_valid():
            ticket = abrir_ticket(
                categoria_sugerida=form.cleaned_data["categoria_sugerida"],
                setor=form.cleaned_data["setor"],
                descricao=form.cleaned_data["descricao"],
                solicitante=request.user,
                solicitante_nome=form.cleaned_data["solicitante_nome"],
                solicitante_ramal=form.cleaned_data["solicitante_ramal"],
                solicitante_sala=form.cleaned_data["solicitante_sala"],
                item_configuracao=form.cleaned_data.get("item_configuracao"),
                solicitante_ip=obter_ip_cliente(request),
                impacto=form.cleaned_data["impacto"],
            )
            messages.success(
                request,
                f"Chamado #{ticket.pk} aberto com sucesso. "
                f"Categoria: {ticket.categoria_sugerida.nome} — "
                f"SLA esperado: {ticket.categoria_sugerida.sla_horas}h. "
                f"Anote o número #{ticket.pk} — você vai precisar dele para consultar "
                f"o andamento do chamado depois.",
            )
            return redirect("tickets:abrir_ticket")
    else:
        form = AbrirTicketForm(user=request.user)

    return render(request, "tickets/abrir_ticket.html", {"form": form})


@login_required
@never_cache
def meus_tickets_view(request):
    numero = request.GET.get("numero", "").strip()
    data_de = request.GET.get("data_de", "").strip()
    data_ate = request.GET.get("data_ate", "").strip()
    erro = None
    resultados = None

    if numero:
        if not numero.isdigit():
            erro = "Digite apenas o número do chamado."
        elif not Ticket.objects.filter(pk=numero, solicitante=request.user).exists():
            erro = f"Nenhum chamado seu encontrado com o número {numero}."
        else:
            return redirect("tickets:meu_ticket_detalhe", pk=numero)
    elif data_de or data_ate:
        resultados = (
            Ticket.objects.filter(solicitante=request.user)
            .select_related("categoria_sugerida", "categoria_final", "setor")
            .order_by("-data_abertura")
        )
        if data_de:
            resultados = resultados.filter(data_abertura__date__gte=data_de)
        if data_ate:
            resultados = resultados.filter(data_abertura__date__lte=data_ate)
        if not resultados.exists():
            erro = "Nenhum chamado seu encontrado nesse período."
            resultados = None

    return render(request, "tickets/meus_tickets.html", {
        "numero": numero,
        "data_de": data_de,
        "data_ate": data_ate,
        "erro": erro,
        "resultados": resultados,
    })


@login_required
@never_cache
def meu_ticket_detalhe_view(request, pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related("categoria_sugerida", "categoria_final", "setor", "tecnico_responsavel"),
        pk=pk, solicitante=request.user,
    )
    comentarios = list(
        ticket.comentarios
        .filter(tipo__in=[ComentarioTicket.Tipo.RESPOSTA_USUARIO, ComentarioTicket.Tipo.DESFECHO])
        .select_related("autor")
    )
    for comentario in comentarios:
        comentario.badge_classe, comentario.badge_emoji, comentario.badge_label = {
            "resposta_usuario": ("info", "💬", "Resposta ao usuário"),
            "desfecho": ("success", "✅", "Desfecho / solução"),
        }[comentario.tipo]

    return render(request, "tickets/meu_ticket_detalhe.html", {"ticket": ticket, "comentarios": comentarios})


@login_required
@never_cache
def notificacoes_view(request):
    notificacoes = Notificacao.objects.filter(destinatario=request.user).select_related("ticket")
    paginator = Paginator(notificacoes, 20)
    pagina = paginator.get_page(request.GET.get("pagina"))
    return render(request, "tickets/notificacoes.html", {"pagina": pagina})


@login_required
@never_cache
def notificacoes_dropdown_view(request):
    notificacoes = Notificacao.objects.filter(destinatario=request.user).select_related("ticket")[:8]
    return render(request, "tickets/_notificacoes_dropdown.html", {"notificacoes": notificacoes})


@login_required
@never_cache
def notificacoes_novas_view(request):
    total_nao_lidas = Notificacao.objects.filter(destinatario=request.user, lida=False).count()
    return JsonResponse({"total_nao_lidas": total_nao_lidas})


@login_required
@require_POST
def marcar_notificacao_lida_view(request, pk):
    notificacao = get_object_or_404(Notificacao, pk=pk, destinatario=request.user)
    marcar_como_lida(notificacao)
    return redirect("tickets:meu_ticket_detalhe", pk=notificacao.ticket_id)


@login_required
@require_POST
def marcar_todas_notificacoes_lidas_view(request):
    marcar_todas_como_lidas(request.user)
    return redirect(request.META.get("HTTP_REFERER") or reverse("tickets:notificacoes"))


def _cargo_usuario(usuario):
    """Os papéis reais são só usuário e técnico — "superuser" é uma conta
    técnica do Django, não o cargo de ninguém. Quem gerencia o setor de TI
    é, na prática, o administrador do sistema, daí o rótulo especial."""
    setores_geridos = list(Setor.objects.filter(gestor=usuario))
    try:
        setor_ti_id = obter_setor_ti().pk
    except (ParametroNaoConfigurado, Setor.DoesNotExist):
        setor_ti_id = None
    if setor_ti_id is not None and any(setor.pk == setor_ti_id for setor in setores_geridos):
        return "Administrador"
    if usuario.is_staff:
        return "Técnico"
    if setores_geridos:
        return "Gestor de " + ", ".join(setor.nome for setor in setores_geridos)
    return "Usuário"


@login_required
@never_cache
def perfil_view(request, username):
    usuario = get_object_or_404(get_user_model(), username=username)
    eh_proprio_perfil = usuario == request.user

    # Só quem está vendo o próprio perfil enxerga/usa os formulários de senha
    # e de dados de contato — pra qualquer outra pessoa, a tela é só a parte
    # pública (nome, cargo, avatar).
    form_senha = None
    form_perfil = None
    if eh_proprio_perfil:
        if request.method == "POST" and request.POST.get("form") == "senha":
            form_senha = TrocarSenhaForm(user=request.user, data=request.POST)
            form_perfil = EditarPerfilForm(instance=usuario)
            if form_senha.is_valid():
                form_senha.save()
                update_session_auth_hash(request, form_senha.user)
                messages.success(request, "Senha alterada com sucesso.")
                return redirect("tickets:perfil", username=usuario.username)
        elif request.method == "POST" and request.POST.get("form") == "perfil":
            form_perfil = EditarPerfilForm(request.POST, instance=usuario)
            form_senha = TrocarSenhaForm(user=request.user)
            if form_perfil.is_valid():
                form_perfil.save()
                messages.success(request, "Dados de contato atualizados com sucesso.")
                return redirect("tickets:perfil", username=usuario.username)
        else:
            form_senha = TrocarSenhaForm(user=request.user)
            form_perfil = EditarPerfilForm(instance=usuario)

    return render(request, "tickets/perfil.html", {
        "usuario": usuario,
        "cargo": _cargo_usuario(usuario),
        "form_senha": form_senha,
        "form_perfil": form_perfil,
        "eh_proprio_perfil": eh_proprio_perfil,
    })


def _filtrar_fila_tickets(request):
    """Aplica os filtros da tela de fila (setor, status, busca, data) e devolve
    o queryset resultante junto com os valores selecionados, para reaproveitar
    tanto na renderização da página quanto na checagem de chamados novos."""
    tickets_qs = (
        Ticket.objects
        .exclude(status=Ticket.Status.FECHADO)
        .select_related("categoria_sugerida", "categoria_ia", "categoria_final", "setor", "tecnico_responsavel")
    )

    setor_id = request.GET.get("setor", "").strip()
    status = request.GET.get("status", "").strip()
    busca = request.GET.get("busca", "").strip()
    data_de = request.GET.get("data_de", "").strip()
    data_ate = request.GET.get("data_ate", "").strip()

    if setor_id:
        tickets_qs = tickets_qs.filter(setor_id=setor_id)
    if status in (Ticket.Status.ABERTO, Ticket.Status.EM_ATENDIMENTO):
        tickets_qs = tickets_qs.filter(status=status)
    if busca:
        tickets_qs = tickets_qs.filter(
            Q(solicitante_nome__icontains=busca) | Q(descricao__icontains=busca)
        )
    if data_de:
        tickets_qs = tickets_qs.filter(data_abertura__date__gte=data_de)
    if data_ate:
        tickets_qs = tickets_qs.filter(data_abertura__date__lte=data_ate)

    filtros = {
        "setor_selecionado": setor_id,
        "status_selecionado": status,
        "busca": busca,
        "data_de": data_de,
        "data_ate": data_ate,
        "algum_filtro": bool(setor_id or status or busca or data_de or data_ate),
    }
    return tickets_qs, filtros


@tecnico_required
def fila_tickets_view(request):
    tickets_qs, filtros = _filtrar_fila_tickets(request)
    tickets = list(tickets_qs.order_by("-prioridade_calculada", "data_abertura"))

    agora = timezone.now()
    for ticket in tickets:
        categoria_referencia = ticket.categoria_final or ticket.categoria_sugerida
        ticket.prazo = ticket.data_abertura + timedelta(hours=float(categoria_referencia.sla_horas))
        ticket.prazo_estourado = ticket.prazo < agora
        ticket.prazo_proximo = not ticket.prazo_estourado and (ticket.prazo - agora) <= timedelta(hours=1)

    # "Abertos" e "Em atendimento" são estado atual — não fazem sentido presos
    # a uma janela de tempo (um chamado aberto há uma semana ainda está
    # aberto agora, e precisa aparecer). "Fechados" foi movido pro Dashboard.
    contagens = {
        "aberto": Ticket.objects.filter(status=Ticket.Status.ABERTO).count(),
        "em_atendimento": Ticket.objects.filter(status=Ticket.Status.EM_ATENDIMENTO).count(),
    }

    return render(request, "tickets/fila_tickets.html", {
        "tickets": tickets,
        "contagens": contagens,
        "setores": Setor.objects.order_by("nome"),
        "ultimo_id": max((t.pk for t in tickets), default=0),
        **filtros,
    })


# Peso de setor a partir do qual ele é considerado "vital" pro indicador de
# chamados críticos por setor (escala de peso_setor vai de 1 a 5).
def _formatar_horas(horas):
    """Converte um total de horas fracionário em texto "Xh Ym" ou, acima de
    um dia, "Xd Yh" — mais legível em relatório do que um decimal solto."""
    if horas is None:
        return None
    minutos_totais = round(horas * 60)
    dias, resto_minutos = divmod(minutos_totais, 24 * 60)
    horas_inteiras, minutos = divmod(resto_minutos, 60)
    if dias > 0:
        return f"{dias}d {horas_inteiras}h"
    return f"{horas_inteiras}h {minutos}m"


PESO_SETOR_VITAL = 4


@tecnico_required
def dashboard_view(request):
    agora = timezone.now()
    hoje = agora.date()
    desde_semana = agora - timedelta(days=7)

    tickets_ativos = list(
        Ticket.objects.exclude(status=Ticket.Status.FECHADO)
        .select_related("categoria_final", "categoria_sugerida", "setor", "tecnico_responsavel")
    )

    criticos_30min = 0
    criticos_60min = 0
    estourados = 0
    tickets_com_prazo = []
    for ticket in tickets_ativos:
        categoria_referencia = ticket.categoria_final or ticket.categoria_sugerida
        prazo = ticket.data_abertura + timedelta(hours=float(categoria_referencia.sla_horas))
        restante = prazo - agora
        if restante < timedelta(0):
            estourados += 1
        elif restante <= timedelta(minutes=30):
            criticos_30min += 1
        elif restante <= timedelta(hours=1):
            criticos_60min += 1
        tickets_com_prazo.append((restante, ticket, prazo))

    alertas = {
        "criticos_30min": criticos_30min,
        "criticos_60min": criticos_60min,
        "estourados": estourados,
        "sem_atribuicao": sum(1 for t in tickets_ativos if t.tecnico_responsavel_id is None),
        "setores_vitais": sum(1 for t in tickets_ativos if t.setor.peso_setor >= PESO_SETOR_VITAL),
    }

    tickets_com_prazo.sort(key=lambda item: item[0])
    chamados_criticos = [
        {
            "ticket": ticket,
            "prazo": prazo,
            "estourado": restante < timedelta(0),
        }
        for restante, ticket, prazo in tickets_com_prazo[:5]
    ]

    contagem_por_setor = {}
    for ticket in tickets_ativos:
        contagem_por_setor[ticket.setor.nome] = contagem_por_setor.get(ticket.setor.nome, 0) + 1
    volume_por_setor = sorted(contagem_por_setor.items(), key=lambda item: item[1], reverse=True)[:8]
    maior_volume_setor = max((total for _, total in volume_por_setor), default=0)

    abertos_hoje = Ticket.objects.filter(data_abertura__date=hoje).count()
    fechados_hoje = Ticket.objects.filter(data_fechamento__date=hoje).count()
    volume = {
        "abertos_hoje": abertos_hoje,
        "fechados_hoje": fechados_hoje,
        "saldo_hoje": abertos_hoje - fechados_hoje,
        "em_atendimento": Ticket.objects.filter(status=Ticket.Status.EM_ATENDIMENTO).count(),
    }

    mttr = HistoricoSLA.objects.filter(
        ticket__data_fechamento__gte=desde_semana
    ).aggregate(media=Avg("tempo_real"))["media"]

    # MTTA (tempo até a primeira resposta) não tem campo próprio — aproxima
    # pelo primeiro comentário em cada chamado aberto na semana. Subquery
    # correlacionada traz só o timestamp do primeiro comentário de cada
    # ticket direto do banco — nem um SELECT por ticket (N+1), nem os
    # comentários inteiros sendo carregados (como um prefetch_related faria).
    primeiro_comentario_em = (
        ComentarioTicket.objects.filter(ticket=OuterRef("pk"))
        .order_by("criado_em")
        .values("criado_em")[:1]
    )
    tickets_com_primeira_resposta = Ticket.objects.filter(data_abertura__gte=desde_semana).annotate(
        primeira_resposta_em=Subquery(primeiro_comentario_em)
    )
    tempos_primeira_resposta = []
    for ticket in tickets_com_primeira_resposta:
        if ticket.primeira_resposta_em:
            horas = (ticket.primeira_resposta_em - ticket.data_abertura).total_seconds() / 3600
            tempos_primeira_resposta.append(horas)
    mtta = sum(tempos_primeira_resposta) / len(tempos_primeira_resposta) if tempos_primeira_resposta else None

    eficiencia = {
        "mttr_horas": round(mttr, 1) if mttr is not None else None,
        "mtta_horas": round(mtta, 1) if mtta is not None else None,
        "mttr_formatado": _formatar_horas(mttr),
        "mtta_formatado": _formatar_horas(mtta),
    }

    # Volume diário dos últimos 7 dias: uma consulta agregada por campo de
    # data (abertura/fechamento) em vez de duas consultas por dia no loop.
    inicio_grafico = hoje - timedelta(days=6)
    abertos_por_dia = {
        linha["dia"]: linha["total"]
        for linha in (
            Ticket.objects.filter(data_abertura__date__gte=inicio_grafico)
            .annotate(dia=TruncDate("data_abertura"))
            .values("dia")
            .annotate(total=Count("id"))
        )
    }
    fechados_por_dia = {
        linha["dia"]: linha["total"]
        for linha in (
            Ticket.objects.filter(data_fechamento__date__gte=inicio_grafico)
            .annotate(dia=TruncDate("data_fechamento"))
            .values("dia")
            .annotate(total=Count("id"))
        )
    }

    fluxo_diario = []
    maior_volume_dia = 0
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        abertos_dia = abertos_por_dia.get(dia, 0)
        fechados_dia = fechados_por_dia.get(dia, 0)
        maior_volume_dia = max(maior_volume_dia, abertos_dia, fechados_dia)
        fluxo_diario.append({"dia": dia, "abertos": abertos_dia, "fechados": fechados_dia})

    escala = maior_volume_dia or 1
    largura, altura, margem_topo, margem_base = 640, 200, 16, 24

    def _pontos_svg(chave):
        passo = largura / (len(fluxo_diario) - 1) if len(fluxo_diario) > 1 else 0
        pontos = []
        for indice, ponto in enumerate(fluxo_diario):
            x = round(indice * passo, 1)
            y = round(margem_topo + (1 - ponto[chave] / escala) * (altura - margem_topo - margem_base), 1)
            pontos.append(f"{x},{y}")
        return " ".join(pontos)

    fluxo_svg = {
        "largura": largura,
        "altura": altura,
        "pontos_abertos": _pontos_svg("abertos"),
        "pontos_fechados": _pontos_svg("fechados"),
        "linha_base_y": round(margem_topo + (altura - margem_topo - margem_base), 1),
    }

    return render(request, "tickets/dashboard.html", {
        "alertas": alertas,
        "volume": volume,
        "eficiencia": eficiencia,
        "chamados_criticos": chamados_criticos,
        "volume_por_setor": volume_por_setor,
        "maior_volume_setor": maior_volume_setor,
        "fluxo_diario": fluxo_diario,
        "fluxo_svg": fluxo_svg,
    })


@tecnico_required
def fila_tickets_novos_view(request):
    tickets_qs, _ = _filtrar_fila_tickets(request)
    try:
        desde_id = int(request.GET.get("desde", "0"))
    except ValueError:
        desde_id = 0
    novos = tickets_qs.filter(pk__gt=desde_id).count()
    return JsonResponse({"novos": novos})


@tecnico_required
def historico_tickets_view(request):
    tickets_qs = (
        Ticket.objects
        .filter(status=Ticket.Status.FECHADO)
        .select_related("categoria_final", "setor", "historicosla")
        .order_by("-data_fechamento")
    )

    setor_id = request.GET.get("setor", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    busca = request.GET.get("busca", "").strip()
    data_de = request.GET.get("data_de", "").strip()
    data_ate = request.GET.get("data_ate", "").strip()
    mostrar_todos = request.GET.get("todos") == "1"
    algum_filtro = bool(setor_id or categoria_id or busca or data_de or data_ate)

    if setor_id:
        tickets_qs = tickets_qs.filter(setor_id=setor_id)
    if categoria_id:
        tickets_qs = tickets_qs.filter(categoria_final_id=categoria_id)
    if busca:
        tickets_qs = tickets_qs.filter(
            Q(solicitante_nome__icontains=busca) | Q(descricao__icontains=busca)
        )
    if data_de:
        tickets_qs = tickets_qs.filter(data_fechamento__date__gte=data_de)
    if data_ate:
        tickets_qs = tickets_qs.filter(data_fechamento__date__lte=data_ate)

    buscou = algum_filtro or mostrar_todos
    pagina = None
    if buscou:
        paginador = Paginator(tickets_qs, 25)
        pagina = paginador.get_page(request.GET.get("pagina"))

        for ticket in pagina:
            historico = getattr(ticket, "historicosla", None)
            if historico and historico.tempo_esperado:
                percentual = float(historico.desvio) / float(historico.tempo_esperado) * 100
                ticket.tipo_desvio = classificar_desvio(percentual)
            else:
                ticket.tipo_desvio = None

    filtros_ativos = request.GET.copy()
    filtros_ativos.pop("pagina", None)

    return render(request, "tickets/historico_tickets.html", {
        "pagina": pagina,
        "buscou": buscou,
        "setores": Setor.objects.order_by("nome"),
        "categorias": Categoria.objects.order_by("grupo", "nome"),
        "setor_selecionado": setor_id,
        "categoria_selecionada": categoria_id,
        "busca": busca,
        "data_de": data_de,
        "data_ate": data_ate,
        "querystring": filtros_ativos.urlencode(),
    })


@ver_slas_required
def sla_por_categoria_view(request):
    categorias = list(Categoria.objects.order_by("grupo", "nome"))
    grupos = {}
    for categoria in categorias:
        grupos.setdefault(categoria.get_grupo_display(), []).append(categoria)
    return render(request, "tickets/sla_por_categoria.html", {"grupos": grupos})


def _obter_ticket_detalhe(pk):
    return get_object_or_404(
        Ticket.objects.select_related(
            "categoria_sugerida", "categoria_ia", "categoria_final", "setor",
            "item_configuracao", "tecnico_responsavel",
        ),
        pk=pk,
    )


def _contexto_detalhe_ticket(ticket, *, patrimonio_saida_valor=None, patrimonio_entrada_valor=None):
    categoria_inicial = ticket.categoria_final or ticket.categoria_ia or ticket.categoria_sugerida
    form = ConfirmarClassificacaoForm(initial={"categoria_final": categoria_inicial})
    comentarios = list(ticket.comentarios.select_related("autor"))
    for comentario in comentarios:
        comentario.badge_classe, comentario.badge_emoji, comentario.badge_label = {
            "nota_interna": ("warning", "🔒", "Nota interna"),
            "resposta_usuario": ("info", "💬", "Resposta ao usuário"),
            "desfecho": ("success", "✅", "Desfecho / solução"),
        }[comentario.tipo]
    comentario_form = ComentarioForm()

    movimentacoes = list(
        ticket.movimentacoes_equipamento.select_related(
            "autor", "equipamento_saida", "equipamento_entrada"
        )
    )
    setor_ti = obter_setor_ti() if movimentacoes else None
    for mov in movimentacoes:
        if mov.sem_movimentacao:
            mov.badge_classe, mov.badge_label = "secondary", "Sem movimentação"
        elif mov.equipamento_saida and mov.equipamento_entrada:
            mov.badge_classe, mov.badge_label = "info", "Substituído"
        elif mov.equipamento_entrada:
            mov.badge_classe, mov.badge_label = "success", "Vinculado"
        else:
            mov.badge_classe, mov.badge_label = "danger", "Retornado"
        if not mov.aplicada and not mov.sem_movimentacao:
            mov.badge_classe = "warning"
            mov.badge_label += " (pendente)"

    return {
        "ticket": ticket,
        "form": form,
        "comentarios": comentarios,
        "comentario_form": comentario_form,
        "movimentacoes": movimentacoes,
        "setor_ti": setor_ti,
        "patrimonio_saida_valor": patrimonio_saida_valor,
        "patrimonio_entrada_valor": patrimonio_entrada_valor,
        "tecnicos": get_user_model().objects.filter(is_staff=True).order_by("first_name", "username"),
    }


@tecnico_required
@never_cache
def detalhe_ticket_view(request, pk):
    ticket = _obter_ticket_detalhe(pk)
    return render(request, "tickets/detalhe_ticket.html", _contexto_detalhe_ticket(ticket))


@tecnico_required
@require_POST
def adicionar_comentario_view(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.ticket = ticket
        comentario.autor = request.user
        comentario.save()
        if comentario.tipo in (ComentarioTicket.Tipo.RESPOSTA_USUARIO, ComentarioTicket.Tipo.DESFECHO):
            rotulo = (
                "uma nova resposta" if comentario.tipo == ComentarioTicket.Tipo.RESPOSTA_USUARIO
                else "o desfecho"
            )
            notificar(
                ticket, Notificacao.Tipo.NOVO_COMENTARIO,
                f"O técnico adicionou {rotulo} ao seu chamado #{ticket.pk}.",
            )
        messages.success(request, "Comentário adicionado.")
    else:
        messages.error(request, "Escreva algo antes de enviar o comentário.")
    return redirect("tickets:detalhe_ticket", pk=pk)


@tecnico_required
@require_POST
def classificar_ticket_view(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    form = ConfirmarClassificacaoForm(request.POST)
    if form.is_valid():
        confirmar_classificacao_final(ticket, form.cleaned_data["categoria_final"])
        messages.success(request, "Classificação confirmada e prioridade recalculada.")
    else:
        messages.error(request, "Selecione uma categoria válida.")
    return redirect("tickets:detalhe_ticket", pk=pk)


@tecnico_required
@require_POST
def atribuir_tecnico_view(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    tecnico_id = request.POST.get("tecnico_id", "").strip()
    if not tecnico_id:
        messages.error(request, "Selecione um técnico para atribuir o chamado.")
        return redirect("tickets:detalhe_ticket", pk=pk)

    tecnico = get_object_or_404(get_user_model(), pk=tecnico_id, is_staff=True)
    atribuir_tecnico(ticket, tecnico)
    messages.success(request, f"Chamado #{ticket.pk} atribuído a {tecnico.get_full_name() or tecnico.username}.")
    return redirect("tickets:detalhe_ticket", pk=pk)


@tecnico_required
@require_POST
def fechar_ticket_view(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not ticket.movimentacao_confirmada and request.POST.get("confirmar_sem_movimentacao") == "on":
        registrar_sem_movimentacao(ticket, autor=request.user)
    try:
        fechar_ticket(ticket)
        messages.success(request, f"Chamado #{ticket.pk} fechado.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("tickets:detalhe_ticket", pk=pk)


@tecnico_required
@require_POST
def movimentar_equipamento_view(request, pk):
    ticket = _obter_ticket_detalhe(pk)
    patrimonio_saida = request.POST.get("patrimonio_saida", "").strip()
    patrimonio_entrada = request.POST.get("patrimonio_entrada", "").strip()
    sem_movimentacao = request.POST.get("sem_movimentacao") == "on"

    def falha(mensagem):
        messages.error(request, mensagem)
        contexto = _contexto_detalhe_ticket(
            ticket,
            patrimonio_saida_valor=patrimonio_saida,
            patrimonio_entrada_valor=patrimonio_entrada,
        )
        return render(request, "tickets/detalhe_ticket.html", contexto)

    if not patrimonio_saida and not patrimonio_entrada:
        if not sem_movimentacao:
            return falha(
                "Informe o patrimônio de saída, de entrada, ou marque que não houve "
                "movimentação de equipamento."
            )
        registrar_sem_movimentacao(ticket, autor=request.user)
        messages.success(
            request,
            "Confirmado: nenhuma movimentação de equipamento foi necessária neste atendimento.",
        )
        return redirect("tickets:detalhe_ticket", pk=pk)

    equipamento_saida = None
    if patrimonio_saida:
        try:
            equipamento_saida = ItemConfiguracao.objects.get(patrimonio=patrimonio_saida)
        except ItemConfiguracao.DoesNotExist:
            return falha(f"Patrimônio de saída \"{patrimonio_saida}\" não encontrado.")

    equipamento_entrada = None
    if patrimonio_entrada:
        try:
            equipamento_entrada = ItemConfiguracao.objects.get(patrimonio=patrimonio_entrada)
        except ItemConfiguracao.DoesNotExist:
            return falha(f"Patrimônio de entrada \"{patrimonio_entrada}\" não encontrado.")

    try:
        registro = movimentar_equipamento(
            ticket, autor=request.user,
            equipamento_saida=equipamento_saida, equipamento_entrada=equipamento_entrada,
        )
    except ValueError as exc:
        return falha(str(exc))

    messages.success(
        request,
        f"{registro.descricao()} Fica pendente até o chamado ser fechado.",
    )
    return redirect("tickets:detalhe_ticket", pk=pk)


@tecnico_required
def consultar_equipamento_view(request):
    patrimonio = request.GET.get("patrimonio", "").strip()
    try:
        item = ItemConfiguracao.objects.select_related("setor").get(patrimonio=patrimonio)
    except ItemConfiguracao.DoesNotExist:
        return JsonResponse({"encontrado": False}, status=404)

    resposta = {
        "encontrado": True,
        "patrimonio": item.patrimonio,
        "categoria": item.get_categoria_display(),
        "marca": item.marca,
        "modelo": item.modelo,
        "setor": str(item.setor),
        "status": item.get_status_display(),
        "elegivel_entrada": equipamento_elegivel_para_entrada(item),
    }

    ticket_id = request.GET.get("ticket", "").strip()
    if ticket_id:
        ticket = get_object_or_404(Ticket, pk=ticket_id)
        resposta["elegivel_saida"] = equipamento_elegivel_para_saida(item, ticket)

    return JsonResponse(resposta)


@acesso_equipamentos_required
def listar_equipamentos_view(request):
    if request.user.is_staff:
        equipamentos = ItemConfiguracao.objects.select_related("setor")
    else:
        equipamentos = ItemConfiguracao.objects.filter(setor__gestor=request.user).select_related("setor")

    patrimonio = request.GET.get("patrimonio", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    status = request.GET.get("status", "").strip()
    setor_id = request.GET.get("setor", "").strip()
    mostrar_todos = request.GET.get("todos") == "1"
    algum_filtro = bool(patrimonio or categoria or status or setor_id)

    if patrimonio:
        equipamentos = equipamentos.filter(patrimonio__icontains=patrimonio)
    if categoria:
        equipamentos = equipamentos.filter(categoria=categoria)
    if status:
        equipamentos = equipamentos.filter(status=status)
    if setor_id:
        equipamentos = equipamentos.filter(setor_id=setor_id)

    buscou = algum_filtro or mostrar_todos
    equipamentos = equipamentos.order_by("patrimonio") if buscou else ItemConfiguracao.objects.none()

    contexto = {
        "equipamentos": equipamentos,
        "buscou": buscou,
        "patrimonio": patrimonio,
        "categoria_selecionada": categoria,
        "status_selecionado": status,
        "setor_selecionado": setor_id,
        "categorias": ItemConfiguracao.Categoria.choices,
        "status_choices": ItemConfiguracao.Status.choices,
    }
    if request.user.is_staff:
        contexto["setores"] = Setor.objects.order_by("nome")

    return render(request, "tickets/listar_equipamentos.html", contexto)


@tecnico_required
def cadastrar_equipamento_view(request):
    if request.method == "POST":
        form = CadastrarEquipamentoForm(request.POST)
        if form.is_valid():
            equipamento = form.save()
            messages.success(
                request, f"Equipamento {equipamento.patrimonio} cadastrado com sucesso."
            )
            return redirect("tickets:listar_equipamentos")
    else:
        form = CadastrarEquipamentoForm()

    return render(request, "tickets/cadastrar_equipamento.html", {"form": form})


@login_required
def editar_equipamento_view(request, pk):
    equipamento = get_object_or_404(ItemConfiguracao.objects.select_related("setor"), pk=pk)
    pode_editar = request.user.is_staff or equipamento.setor.gestor_id == request.user.id
    if not pode_editar:
        raise PermissionDenied

    if request.method == "POST":
        form = CadastrarEquipamentoForm(request.POST, instance=equipamento)
        if form.is_valid():
            form.save()
            messages.success(request, f"Equipamento {equipamento.patrimonio} atualizado.")
            return redirect("tickets:listar_equipamentos")
    else:
        form = CadastrarEquipamentoForm(instance=equipamento)

    return render(
        request, "tickets/editar_equipamento.html", {"form": form, "equipamento": equipamento}
    )


@login_required
def listar_artigos_view(request):
    artigos = ArtigoConhecimento.objects.select_related("autor", "categoria")

    busca = request.GET.get("busca", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()

    if busca:
        artigos = artigos.filter(
            Q(titulo__icontains=busca) | Q(resumo__icontains=busca) | Q(conteudo__icontains=busca)
        )
    if categoria_id:
        artigos = artigos.filter(categoria_id=categoria_id)

    return render(request, "tickets/listar_artigos.html", {
        "artigos": artigos,
        "busca": busca,
        "categorias": Categoria.objects.order_by("grupo", "nome"),
        "categoria_selecionada": categoria_id,
    })


@login_required
def sugestoes_artigos_view(request):
    """Sugestão de autoajuda: busca artigos da base de conhecimento a partir
    do texto que o solicitante já digitou na descrição do chamado, antes de
    enviar — chance de resolver sem precisar abrir o chamado."""
    termo = request.GET.get("q", "").strip()
    if len(termo) < 5:
        return JsonResponse({"artigos": []})

    # "icontains" verifica se o CAMPO contém o termo — uma descrição longa
    # nunca "cabe dentro" de um título curto, então a busca precisa ser por
    # palavras-chave da descrição, não pela frase inteira.
    palavras = {p for p in re.split(r"\W+", termo, flags=re.UNICODE) if len(p) >= 4}
    if not palavras:
        return JsonResponse({"artigos": []})

    condicao = Q()
    for palavra in palavras:
        condicao |= Q(titulo__icontains=palavra) | Q(resumo__icontains=palavra) | Q(conteudo__icontains=palavra)

    artigos = ArtigoConhecimento.objects.filter(condicao).distinct().order_by("titulo")[:3]

    return JsonResponse({
        "artigos": [
            {
                "titulo": artigo.titulo.title(),
                "resumo": artigo.resumo,
                "url": reverse("tickets:detalhe_artigo", args=[artigo.pk]),
            }
            for artigo in artigos
        ]
    })


@login_required
def detalhe_artigo_view(request, pk):
    artigo = get_object_or_404(ArtigoConhecimento.objects.select_related("autor", "categoria"), pk=pk)
    return render(request, "tickets/detalhe_artigo.html", {"artigo": artigo})


@tecnico_required
def criar_artigo_view(request):
    if request.method == "POST":
        form = ArtigoForm(request.POST)
        if form.is_valid():
            artigo = form.save(commit=False)
            artigo.autor = request.user
            artigo.save()
            messages.success(request, f'Artigo "{artigo.titulo}" publicado.')
            return redirect("tickets:detalhe_artigo", pk=artigo.pk)
    else:
        form = ArtigoForm()

    return render(request, "tickets/form_artigo.html", {"form": form, "modo": "criar"})


@tecnico_required
def editar_artigo_view(request, pk):
    artigo = get_object_or_404(ArtigoConhecimento, pk=pk)
    if request.method == "POST":
        form = ArtigoForm(request.POST, instance=artigo)
        if form.is_valid():
            form.save()
            messages.success(request, f'Artigo "{artigo.titulo}" atualizado.')
            return redirect("tickets:detalhe_artigo", pk=artigo.pk)
    else:
        form = ArtigoForm(instance=artigo)

    return render(request, "tickets/form_artigo.html", {"form": form, "modo": "editar", "artigo": artigo})
