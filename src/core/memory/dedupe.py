from ..schemas import Duplicata
from .vector import Achado


def recorrencia(achados: list[Achado], limiar: float) -> tuple[int, list[Achado]]:
    """Em quantas reuniões anteriores o problema já apareceu, e os achados que provam isso."""
    fortes = [a for a in achados if a.similaridade >= limiar]
    return len({a.reuniao_id for a in fortes}), fortes


def melhor_duplicata(achados: list[Achado], limiar: float) -> Duplicata | None:
    """Issue anterior mais parecida, se passar do limiar (o humano decide o que fazer)."""
    if not achados or achados[0].similaridade < limiar:
        return None
    a = max(achados, key=lambda a: a.similaridade)
    return Duplicata(
        reuniao_id=a.reuniao_id,
        acao_id=a.ref,
        titulo=a.titulo,
        similaridade=round(a.similaridade, 4),
    )
