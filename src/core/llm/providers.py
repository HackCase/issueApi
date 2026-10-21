import json
import re

import httpx

from ..settings import Settings, get_settings
from .base import Resposta, T

_JSON_INSTR = (
    "Responda APENAS com um objeto JSON válido que siga este JSON Schema, "
    "sem texto fora do JSON:\n{schema}"
)


def _extrair_json(texto: str) -> str:
    """Remove cercas ```json ... ``` que alguns modelos adicionam."""
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.DOTALL)
    return (m.group(1) if m else texto).strip()


class _Base:
    def __init__(self, s: Settings, timeout: float = 120):
        self.s = s
        self.http = httpx.Client(timeout=timeout)

    def _modelo(self, forte: bool) -> str:
        modelo = self.s.llm_model_strong if forte else self.s.llm_model_fast
        if not modelo:
            raise RuntimeError("defina LLM_MODEL_FAST e LLM_MODEL_STRONG")
        return modelo

    def _chamar(self, prompt: str, system: str | None, modelo: str) -> Resposta:
        raise NotImplementedError

    def complete(
        self, prompt, *, system=None, forte=False, etapa="", prompt_versao="", reuniao_id=None
    ) -> Resposta:
        return self._chamar(prompt, system, self._modelo(forte))

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
        instr = _JSON_INSTR.format(
            schema=json.dumps(schema.model_json_schema(), ensure_ascii=False)
        )
        r = self._chamar(prompt, f"{system}\n\n{instr}" if system else instr, self._modelo(forte))
        r.dados = schema.model_validate_json(_extrair_json(r.texto))
        return r

    def embed(self, textos: list[str]) -> list[list[float]]:
        raise NotImplementedError("este provedor não oferece embeddings")


class AnthropicClient(_Base):
    def _chamar(self, prompt, system, modelo):
        body = {
            "model": modelo,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        r = self.http.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.s.llm_api_key, "anthropic-version": "2023-06-01"},
            json=body,
        )
        r.raise_for_status()
        d = r.json()
        texto = "".join(b["text"] for b in d["content"] if b["type"] == "text")
        return Resposta(texto, d["model"], d["usage"]["input_tokens"], d["usage"]["output_tokens"])


class OpenAIClient(_Base):
    def _headers(self):
        return {"Authorization": f"Bearer {self.s.llm_api_key}"}

    def _chamar(self, prompt, system, modelo):
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body = {"model": modelo, "messages": msgs}
        # JSON mode exige a palavra "JSON" no prompt; complete_json sempre a inclui
        if system and "JSON" in system:
            body["response_format"] = {"type": "json_object"}
        r = self.http.post(
            "https://api.openai.com/v1/chat/completions", headers=self._headers(), json=body
        )
        r.raise_for_status()
        d = r.json()
        u = d["usage"]
        return Resposta(
            d["choices"][0]["message"]["content"],
            d["model"],
            u["prompt_tokens"],
            u["completion_tokens"],
        )

    def embed(self, textos):
        if not self.s.embedding_model:
            raise RuntimeError("defina EMBEDDING_MODEL")
        r = self.http.post(
            "https://api.openai.com/v1/embeddings",
            headers=self._headers(),
            json={"model": self.s.embedding_model, "input": textos},
        )
        r.raise_for_status()
        return [i["embedding"] for i in r.json()["data"]]


def build_client(settings: Settings | None = None):
    s = settings or get_settings()
    if s.llm_provider == "anthropic":
        return AnthropicClient(s)
    if s.llm_provider == "openai":
        return OpenAIClient(s)
    # ponytail: gemini não implementado; adicionar subclasse de _Base se for o escolhido
    raise NotImplementedError(f"provedor {s.llm_provider} ainda não implementado")
