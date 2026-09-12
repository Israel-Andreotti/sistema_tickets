"""Mede a acurácia do classificador de IA — primeiro passo antes de cogitar
qualquer treino do modelo (ver conversa: zero-shot não precisa de retreino a
cada categoria nova, então só vale a pena mexer nisso se a acurácia real
mostrar um problema).

Compara categoria_ia (palpite do modelo) com categoria_final (o que o
técnico de fato confirmou) nos chamados que já têm as duas — é a única
comparação justa, já que categoria_final é a "verdade" validada por humano.
"""
from collections import Counter

from django.core.management.base import BaseCommand

from tickets.models import Ticket


class Command(BaseCommand):
    help = "Mede a acurácia do classificador de IA comparando categoria_ia com categoria_final."

    def handle(self, *args, **opcoes):
        tickets = list(
            Ticket.objects.filter(
                categoria_ia__isnull=False, categoria_final__isnull=False,
            ).select_related("categoria_ia", "categoria_final")
        )

        total = len(tickets)
        if total == 0:
            self.stdout.write(
                "Nenhum chamado com categoria_ia e categoria_final preenchidas ainda — "
                "nada para medir. Isso só existe depois que a IA classificou e um técnico "
                "confirmou (ou corrigiu) a classificação final."
            )
            return

        acertos = 0
        confiancas_certas = []
        confiancas_erradas = []
        confusoes = Counter()

        for ticket in tickets:
            confianca = float(ticket.confianca_ia) if ticket.confianca_ia is not None else None
            if ticket.categoria_ia_id == ticket.categoria_final_id:
                acertos += 1
                if confianca is not None:
                    confiancas_certas.append(confianca)
            else:
                confusoes[(ticket.categoria_ia.nome, ticket.categoria_final.nome)] += 1
                if confianca is not None:
                    confiancas_erradas.append(confianca)

        acuracia = acertos / total * 100
        self.stdout.write(self.style.SUCCESS(
            f"{acertos} de {total} chamado(s) — acurácia de {acuracia:.1f}%."
        ))

        if confiancas_certas:
            media = sum(confiancas_certas) / len(confiancas_certas)
            self.stdout.write(f"Confiança média nos acertos: {media:.2f}")
        if confiancas_erradas:
            media = sum(confiancas_erradas) / len(confiancas_erradas)
            self.stdout.write(f"Confiança média nos erros:   {media:.2f}")

        if confusoes:
            self.stdout.write("\nConfusões mais comuns (IA chutou X, técnico confirmou Y):")
            for (chute_ia, confirmado), quantidade in confusoes.most_common(10):
                self.stdout.write(f'  {quantidade}x — IA: "{chute_ia}" | Confirmado: "{confirmado}"')
