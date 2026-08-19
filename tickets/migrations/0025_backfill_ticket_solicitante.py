"""Tenta recuperar o vínculo Ticket -> User para chamados abertos antes da
existência do campo Ticket.solicitante. É best-effort: solicitante_nome era
preenchido com request.user.get_full_name() or request.user.username no
momento da abertura, então tentamos casar por esses dois critérios. Chamados
sem correspondência exata ficam com solicitante=None (não aparecem em
"Meus chamados", mas continuam intactos e visíveis para os técnicos)."""
from django.db import migrations


def preencher_solicitante(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    User = apps.get_model("auth", "User")

    usuarios = list(User.objects.all())
    for ticket in Ticket.objects.filter(solicitante__isnull=True):
        candidato = next(
            (
                u for u in usuarios
                if ticket.solicitante_nome == (f"{u.first_name} {u.last_name}".strip() or u.username)
            ),
            None,
        )
        if candidato:
            ticket.solicitante = candidato
            ticket.save(update_fields=["solicitante"])


def reverter(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    Ticket.objects.update(solicitante=None)


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0024_ticket_solicitante"),
    ]

    operations = [
        migrations.RunPython(preencher_solicitante, reverter),
    ]
