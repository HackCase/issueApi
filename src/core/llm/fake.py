import hashlib
import json
from typing import Any

from pydantic import BaseModel

from .base import Resposta, T

DIM = 8


class FakeLLM:
    """Cliente para testes: devolve as respostas enfileiradas, na ordem."""

    def __init__(self, respostas: list[Any] | None = None):
        self.respostas = list(respostas or [])
        self.chamadas: list[dict] = []

    def _proxima(self) -> Any:
        if not self.respostas:
            raise AssertionError("FakeLLM sem respostas enfileiradas")
        return self.respostas.pop(0)

    def _registrar(self, metodo: str, prompt: str, forte: bool, **meta) -> None:
        self.chamadas.append({"metodo": metodo, "prompt": prompt, "forte": forte, **meta})

    def complete(
        self, prompt, *, system=None, forte=False, etapa="", prompt_versao="", reuniao_id=None
    ) -> Resposta:
        self._registrar("complete", prompt, forte, system=system, etapa=etapa)
        r = self._proxima()
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return Resposta(texto, "fake", len(prompt.split()), len(texto.split()))

    def complete_json(
        self,
        prompt,
        schema: type[T],
        *,
        system=None,
        forte=False,
        etapa="",
        prompt_versao="",
        reuniao_id=None,
    ) -> Resposta:
        self._registrar("complete_json", prompt, forte, system=system, etapa=etapa)
        r = self._proxima()
        if isinstance(r, BaseModel):
            r = r.model_dump(mode="json")
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        dados = schema.model_validate_json(texto)
        return Resposta(texto, "fake", len(prompt.split()), len(texto.split()), dados)

    def embed(self, textos: list[str]) -> list[list[float]]:
        # vetor determinístico por texto: textos iguais -> vetores iguais
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()[:DIM]] for t in textos]
