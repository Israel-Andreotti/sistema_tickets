"""Feedback de utilidade (👍/👎) em artigos da base de conhecimento sugeridos
durante a abertura de chamado."""
from ..models import ArtigoConhecimento, FeedbackArtigoConhecimento


def registrar_feedback_artigo(artigo: ArtigoConhecimento, usuario, *, util: bool) -> FeedbackArtigoConhecimento:
    """Dar feedback de novo no mesmo artigo atualiza o voto anterior — uma
    pessoa não acumula múltiplos votos pro mesmo artigo, só o mais recente
    conta."""
    feedback, _ = FeedbackArtigoConhecimento.objects.update_or_create(
        artigo=artigo, usuario=usuario, defaults={"util": util},
    )
    return feedback
