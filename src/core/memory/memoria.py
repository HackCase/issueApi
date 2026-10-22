from ..guardrails.sanitize import Sanitizador
from ..schemas import Acao, Duplicata, MeetingInput, PlanoAcao
from .dedupe import melhor_duplicata, recorrencia
from .vector import Item


class Memoria:
    """Memória vetorial entre reuniões. Ao embedder vai texto mascarado; o banco guarda o original.

    Quem usa trata falhas daqui como modo degradado (segue sem memória e registra aviso).
    """

    def __init__(self, vetores, embedder, limiar: float, k: int = 3):
        self.vetores, self.embedder, self.limiar, self.k = vetores, embedder, limiar, k

    def _embed(self, textos: list[str], san: Sanitizador) -> list[list[float]]:
        return self.embedder.embed([san.mascarar(t) for t in textos]) if textos else []

    def registrar_ata(self, reuniao: MeetingInput, san: Sanitizador) -> None:
        refs = [*reuniao.problema_ids, "acompanhamento"]
        textos = [*reuniao.problemas, reuniao.acompanhamento]
        titulos = [f"Problema {r}" for r in reuniao.problema_ids] + ["Acompanhamento"]
        itens = [
            Item(r, t, x, v)
            for r, t, x, v in zip(refs, titulos, textos, self._embed(textos, san), strict=True)
        ]
        self.vetores.substituir("atas_chunks", reuniao.reuniao_id, itens)

    def historico_problemas(
        self, reuniao: MeetingInput, san: Sanitizador
    ) -> tuple[dict[str, int], str]:
        """({problema_id: nº de reuniões anteriores com o mesmo problema}, texto p/ o prompt)."""
        rid = reuniao.reuniao_id
        vetores = self._embed(reuniao.problemas, san)
        contagens: dict[str, int] = {}
        linhas: list[str] = []
        for pid, v in zip(reuniao.problema_ids, vetores, strict=True):
            n, fortes = recorrencia(self.vetores.buscar("atas_chunks", v, self.k, rid), self.limiar)
            if n:
                contagens[pid] = n
                linhas.append(f"{pid} já apareceu em {n} reunião(ões) anterior(es):")
                linhas += [f"- ({a.reuniao_id}) {san.mascarar(a.texto)}" for a in fortes]
        return contagens, "\n".join(linhas)

    def _textos_acoes(self, acoes: list[Acao]) -> list[str]:
        return [f"{a.titulo}\n\n{a.descricao}" for a in acoes]

    def registrar_issues(self, plano: PlanoAcao, san: Sanitizador) -> None:
        textos = self._textos_acoes(plano.acoes)
        itens = [
            Item(a.id, a.titulo, t, v)
            for a, t, v in zip(plano.acoes, textos, self._embed(textos, san), strict=True)
        ]
        self.vetores.substituir("issues_hist", plano.reuniao_id, itens)

    def duplicatas(self, plano: PlanoAcao, san: Sanitizador) -> dict[str, Duplicata]:
        vetores = self._embed(self._textos_acoes(plano.acoes), san)
        achou = {}
        for a, v in zip(plano.acoes, vetores, strict=True):
            d = melhor_duplicata(
                self.vetores.buscar("issues_hist", v, self.k, plano.reuniao_id), self.limiar
            )
            if d:
                achou[a.id] = d
        return achou
