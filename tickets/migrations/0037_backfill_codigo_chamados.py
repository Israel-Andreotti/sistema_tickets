from django.db import migrations


def backfill_codigos(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    ContadorChamado = apps.get_model("tickets", "ContadorChamado")

    contadores = {"incidente": 0, "requisicao": 0}
    tickets = (
        Ticket.objects.select_related("categoria_sugerida")
        .order_by("data_abertura", "pk")
    )
    for ticket in tickets:
        tipo = ticket.categoria_sugerida.tipo
        contadores[tipo] += 1
        ticket.codigo_tipo = tipo
        ticket.codigo_numero = contadores[tipo]
        ticket.save(update_fields=["codigo_tipo", "codigo_numero"])

    for tipo, ultimo_numero in contadores.items():
        ContadorChamado.objects.update_or_create(
            tipo=tipo, defaults={"ultimo_numero": ultimo_numero}
        )


def reverter_backfill(apps, schema_editor):
    ContadorChamado = apps.get_model("tickets", "ContadorChamado")
    ContadorChamado.objects.filter(tipo__in=["incidente", "requisicao"]).delete()
    # codigo_tipo/codigo_numero voltam ao valor que o AddField já deixou
    # (0/"incidente") — não precisa reverter ticket a ticket.


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0036_contadorchamado_ticket_codigo_numero_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_codigos, reverter_backfill),
    ]
