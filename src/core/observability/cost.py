import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..llm.base import LLMClient, Resposta


@dataclass
class Chamada:
    etapa: str
    modelo: str
    tokens_in: int
    tokens_out: int
    custo: float | None  # None = modelo sem preço em precos.yaml
    latencia_s: float
    prompt_versao: str
    reuniao_id: str | None


def carregar_precos(path: Path) -> dict[str, dict[str, float]]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("modelos") or {}


class CustoLLM:
    """Envolve um LLMClient e registra etapa, modelo, tokens, custo, latência e versão do prompt."""

    def __init__(self, inner: LLMClient, precos: dict[str, dict[str, float]]):
        self.inner = inner
        self.precos = precos
        self.chamadas: list[Chamada] = []  # ponytail: em memória; persistir no T9 (/custo)

    def _custo(self, r: Resposta) -> float | None:
        p = self.precos.get(r.modelo)
        if p is None:
            return None
        return (r.tokens_in * p["entrada_por_mtok"] + r.tokens_out * p["saida_por_mtok"]) / 1e6

    def _medir(self, fn, etapa, prompt_versao, reuniao_id, *args, **kw) -> Resposta:
        t0 = time.perf_counter()
        r = fn(*args, etapa=etapa, prompt_versao=prompt_versao, reuniao_id=reuniao_id, **kw)
        self.chamadas.append(
            Chamada(
                etapa,
                r.modelo,
                r.tokens_in,
                r.tokens_out,
                self._custo(r),
                time.perf_counter() - t0,
                prompt_versao,
                reuniao_id,
            )
        )
        return r

    def complete(self, prompt, *, etapa="", prompt_versao="", reuniao_id=None, **kw) -> Resposta:
        return self._medir(self.inner.complete, etapa, prompt_versao, reuniao_id, prompt, **kw)

    def complete_json(
        self, prompt, schema, *, etapa="", prompt_versao="", reuniao_id=None, **kw
    ) -> Resposta:
        return self._medir(
            self.inner.complete_json, etapa, prompt_versao, reuniao_id, prompt, schema, **kw
        )

    def embed(self, textos):
        return self.inner.embed(textos)

    def resumo(self, reuniao_id: str | None = None) -> dict[str, dict]:
        """Tokens e custo por etapa (custo ignora chamadas sem preço)."""
        out: dict[str, dict] = {}
        for c in self.chamadas:
            if reuniao_id is not None and c.reuniao_id != reuniao_id:
                continue
            e = out.setdefault(
                c.etapa, {"chamadas": 0, "tokens_in": 0, "tokens_out": 0, "custo": 0.0}
            )
            e["chamadas"] += 1
            e["tokens_in"] += c.tokens_in
            e["tokens_out"] += c.tokens_out
            e["custo"] += c.custo or 0.0
        return out
