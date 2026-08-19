"""Movimentação de equipamento vinculado a um ticket (troca/adição/remoção).

Não faz parte das RN01-17 originais — é a lógica por trás dos campos de
"patrimônio de saída" e "patrimônio de entrada" na tela do técnico:
- o equipamento de saída só pode ser um equipamento que esteja de fato
  lotado no setor deste ticket — não faz sentido "retirar" um equipamento
  de um setor onde ele não está; ao sair, ele retorna automaticamente para
  o setor de TI, para triagem/manutenção;
- o equipamento de entrada (se informado) só pode ser um equipamento que já
  esteja lotado na TI e com status Disponível — não dá pra "adicionar" um
  equipamento que está em uso em outro lugar ou fora de serviço.

Cada chamada (inclusive as confirmações de "sem movimentação") grava um
MovimentacaoEquipamento, formando o histórico exibido na tela do ticket.
"""
from ..models import ItemConfiguracao, MovimentacaoEquipamento, Setor, Ticket
from .parametros import get_parametro


def obter_setor_ti() -> Setor:
    setor_ti_id = get_parametro("setor_ti_id", cast=int)
    return Setor.objects.get(pk=setor_ti_id)


def equipamento_elegivel_para_entrada(equipamento: ItemConfiguracao) -> bool:
    return (
        equipamento.setor_id == obter_setor_ti().pk
        and equipamento.status == ItemConfiguracao.Status.ATIVO
    )


def equipamento_elegivel_para_saida(equipamento: ItemConfiguracao, ticket: Ticket) -> bool:
    return equipamento.setor_id == ticket.setor_id


def movimentar_equipamento(
    ticket: Ticket,
    *,
    autor,
    equipamento_saida: ItemConfiguracao | None = None,
    equipamento_entrada: ItemConfiguracao | None = None,
) -> MovimentacaoEquipamento:
    """Registra a movimentação como pendente (fica em stand-by): valida a
    elegibilidade e grava o registro, mas não altera o CMDB ainda — isso só
    acontece em aplicar_movimentacoes_pendentes(), chamada ao fechar o chamado."""
    if equipamento_saida and not equipamento_elegivel_para_saida(equipamento_saida, ticket):
        raise ValueError(
            f"O equipamento {equipamento_saida.patrimonio} não está lotado no "
            f"setor deste chamado ({ticket.setor}) — não é possível registrar a saída."
        )

    if equipamento_entrada and not equipamento_elegivel_para_entrada(equipamento_entrada):
        raise ValueError(
            "Só é possível adicionar equipamentos que estejam lotados na "
            "informática e com situação Disponível."
        )

    ticket.movimentacao_confirmada = True
    ticket.save(update_fields=["movimentacao_confirmada"])

    return MovimentacaoEquipamento.objects.create(
        ticket=ticket,
        autor=autor,
        equipamento_saida=equipamento_saida,
        equipamento_entrada=equipamento_entrada,
    )


def registrar_sem_movimentacao(ticket: Ticket, *, autor) -> MovimentacaoEquipamento:
    ticket.movimentacao_confirmada = True
    ticket.save(update_fields=["movimentacao_confirmada"])
    return MovimentacaoEquipamento.objects.create(
        ticket=ticket, autor=autor, sem_movimentacao=True, aplicada=True
    )


def aplicar_movimentacoes_pendentes(ticket: Ticket) -> None:
    """Efetiva no CMDB todas as movimentações registradas (em stand-by) para
    este chamado, na ordem em que foram feitas. Chamada só no fechamento do
    chamado — é o que torna o registro de patrimônio "definitivo"."""
    pendentes = (
        ticket.movimentacoes_equipamento
        .filter(aplicada=False, sem_movimentacao=False)
        .select_related("equipamento_saida", "equipamento_entrada")
        .order_by("criado_em")
    )
    for mov in pendentes:
        if mov.equipamento_saida:
            setor_ti = obter_setor_ti()
            mov.equipamento_saida.setor = setor_ti
            mov.equipamento_saida.status = ItemConfiguracao.Status.MANUTENCAO
            mov.equipamento_saida.save(update_fields=["setor", "status"])

        if mov.equipamento_entrada:
            mov.equipamento_entrada.setor = ticket.setor
            mov.equipamento_entrada.status = ItemConfiguracao.Status.ATIVO
            mov.equipamento_entrada.save(update_fields=["setor", "status"])
            ticket.item_configuracao = mov.equipamento_entrada
        elif mov.equipamento_saida and ticket.item_configuracao_id == mov.equipamento_saida.pk:
            ticket.item_configuracao = None

        mov.aplicada = True
        mov.save(update_fields=["aplicada"])

    if pendentes:
        ticket.save(update_fields=["item_configuracao"])
