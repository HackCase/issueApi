from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class Resposta:
    texto: str
    modelo: str
    tokens_in: int = 0
    tokens_out: int = 0
    dados: Any = None  # modelo Pydantic validado (só em complete_json)


class LLMClient(Protocol):
    """Interface única; `forte=True` usa LLM_MODEL_STRONG, senão LLM_MODEL_FAST.

    `etapa`, `prompt_versao` e `reuniao_id` são metadados para o registro de custo.
    """

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        forte: bool = False,
        etapa: str = "",
        prompt_versao: str = "",
        reuniao_id: str | None = None,
    ) -> Resposta: ...

    def complete_json(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        forte: bool = False,
        etapa: str = "",
        prompt_versao: str = "",
        reuniao_id: str | None = None,
    ) -> Resposta:
        """Uma chamada; `dados` é a instância de `schema`.

        Levanta pydantic.ValidationError se o JSON não validar (o retry é do chamador).
        """
        ...

    def embed(self, textos: list[str]) -> list[list[float]]: ...
