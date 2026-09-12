"""Classifica chamados que ficaram sem categoria_ia.

A classificação normal acontece na abertura do chamado (views.abrir_ticket_view),
em segundo plano. Quando o serviço de IA está fora do ar naquele instante, o
chamado segue sem palpite — e não há nada que tente de novo sozinho. Este
comando é essa segunda chance: rode depois de subir o serviço, ou
periodicamente (Agendador de Tarefas do Windows / cron), para varrer o que
ficou pra trás.
"""
from django.core.management.base import BaseCommand, CommandError

from tickets.models import Ticket
from tickets.services.ia import (
    ClassificadorIndisponivel,
    classificador_configurado,
    classificar_ticket,
)


class Command(BaseCommand):
    help = "Classifica com a IA os chamados que ainda não têm categoria_ia."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite", type=int, default=50,
            help="Máximo de chamados a classificar nesta execução (padrão: 50).",
        )
        parser.add_argument(
            "--incluir-fechados", action="store_true",
            help="Também classifica chamados já fechados — por padrão só os abertos, "
                  "já que num chamado fechado o palpite não ajuda mais ninguém.",
        )

    def handle(self, *args, **opcoes):
        verbosidade = opcoes["verbosity"]

        def relatar(texto):
            if verbosidade >= 1:
                self.stdout.write(texto)

        if not classificador_configurado():
            raise CommandError(
                "IA_CLASSIFICADOR_URL não está configurada no .env — "
                "suba o serviço da pasta classificador/ e aponte a variável pra ele."
            )

        pendentes = Ticket.objects.filter(categoria_ia__isnull=True)
        if not opcoes["incluir_fechados"]:
            pendentes = pendentes.exclude(status=Ticket.Status.FECHADO)
        pendentes = pendentes.order_by("data_abertura")[: opcoes["limite"]]

        total = len(pendentes)
        if total == 0:
            relatar("Nenhum chamado pendente de classificação.")
            return

        classificados = 0
        descartados = 0
        for ticket in pendentes:
            try:
                categoria = classificar_ticket(ticket)
            except ClassificadorIndisponivel as erro:
                # Sem serviço não adianta insistir nos demais: aborta e relata.
                raise CommandError(f"Classificador indisponível: {erro}") from erro

            if categoria is None:
                descartados += 1
                relatar(f"  {ticket.codigo}: sem palpite aceito.")
            else:
                classificados += 1
                relatar(
                    self.style.SUCCESS(f"  {ticket.codigo}: {categoria} ({ticket.confianca_ia})")
                )

        relatar(
            self.style.SUCCESS(
                f"{classificados} de {total} chamado(s) classificado(s); "
                f"{descartados} sem palpite aceito."
            )
        )
