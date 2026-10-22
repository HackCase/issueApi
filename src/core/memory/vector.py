import math
from dataclasses import dataclass

from .db import TABELAS, conectar


@dataclass(frozen=True)
class Item:
    ref: str  # atas_chunks: "p1".."pN" ou "acompanhamento"; issues_hist: id da ação
    titulo: str
    texto: str
    vetor: list[float]


@dataclass(frozen=True)
class Achado:
    reuniao_id: str
    ref: str
    titulo: str
    texto: str
    similaridade: float  # cosseno, 1 = idêntico


def cosseno(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


class VetoresMem:
    """Mesma interface do PgVetores, em memória (testes)."""

    def __init__(self):
        self.linhas: dict[str, dict[str, list[Item]]] = {t: {} for t in TABELAS}

    def substituir(self, tabela: str, reuniao_id: str, itens: list[Item]) -> None:
        self.linhas[tabela][reuniao_id] = list(itens)

    def buscar(self, tabela: str, vetor: list[float], k: int, excluir: str) -> list[Achado]:
        achados = [
            Achado(rid, i.ref, i.titulo, i.texto, cosseno(vetor, i.vetor))
            for rid, itens in self.linhas[tabela].items()
            if rid != excluir
            for i in itens
        ]
        return sorted(achados, key=lambda a: -a.similaridade)[:k]


def _vec(v: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


class PgVetores:
    def __init__(self, url: str, dim: int):
        self.url, self.dim = url, dim

    def substituir(self, tabela: str, reuniao_id: str, itens: list[Item]) -> None:
        assert tabela in TABELAS
        with conectar(self.url, self.dim) as c:  # uma transação: apaga e reinsere
            c.execute(f"DELETE FROM {tabela} WHERE reuniao_id = %s", (reuniao_id,))
            for i in itens:
                c.execute(
                    f"""INSERT INTO {tabela} (reuniao_id, ref, titulo, texto, embedding)
                        VALUES (%s, %s, %s, %s, %s::vector)""",
                    (reuniao_id, i.ref, i.titulo, i.texto, _vec(i.vetor)),
                )

    def buscar(self, tabela: str, vetor: list[float], k: int, excluir: str) -> list[Achado]:
        assert tabela in TABELAS
        with conectar(self.url, self.dim) as c:
            rows = c.execute(
                f"""SELECT reuniao_id, ref, titulo, texto, 1 - (embedding <=> %s::vector)
                    FROM {tabela} WHERE reuniao_id <> %s
                    ORDER BY embedding <=> %s::vector LIMIT %s""",
                (_vec(vetor), excluir, _vec(vetor), k),
            ).fetchall()
        return [Achado(*r) for r in rows]
