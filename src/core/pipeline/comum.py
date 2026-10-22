import re
from collections.abc import Callable

from pydantic import ValidationError

from ..llm.base import LLMClient, T
from ..schemas import MeetingInput

# o texto vindo do usuário/LLM não pode abrir nem fechar as tags de delimitação
_TAGS = re.compile(r"</?\s*(reuniao|ata|grill|plano|historico)[^>]*>", re.IGNORECASE)


class SaidaInvalida(RuntimeError):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def delimitar(tag: str, texto: str) -> str:
    return f"<{tag}>\n{_TAGS.sub('', texto)}\n</{tag}>"


def texto_reuniao(r: MeetingInput) -> str:
    problemas = "\n".join(f"{pid}: {p}" for pid, p in zip(r.problema_ids, r.problemas, strict=True))
    return (
        f"Título: {r.titulo}\nData: {r.data:%d/%m/%Y}\n"
        f"Participantes: {', '.join(r.participantes) or '(não informado)'}\n\n"
        f"### Acompanhamento\n{r.acompanhamento}\n\n### Problemas\n{problemas}"
    )


def _erros_pydantic(e: ValidationError) -> list[str]:
    return [f"{'.'.join(map(str, x['loc'])) or '(raiz)'}: {x['msg']}" for x in e.errors()]


def chamar_json(
    llm: LLMClient,
    prompt: str,
    schema: type[T],
    *,
    system: str,
    etapa: str,
    prompt_versao: str,
    reuniao_id: str,
    validar: Callable[[T], list[str]] | None = None,
) -> T:
    """JSON validado pelo schema (e por `validar`); 1 retry com os erros, depois SaidaInvalida."""
    erros: list[str] = []
    for _ in range(2):
        p = prompt
        if erros:
            lista = "\n".join(f"- {e}" for e in erros)
            p += f"\n\nSua resposta anterior foi rejeitada. Corrija e responda só com o JSON:\n{lista}"  # noqa: E501
        try:
            dados = llm.complete_json(
                p,
                schema,
                system=system,
                forte=True,
                etapa=etapa,
                prompt_versao=prompt_versao,
                reuniao_id=reuniao_id,
            ).dados
        except ValidationError as e:
            erros = _erros_pydantic(e)
            continue
        erros = validar(dados) if validar else []
        if not erros:
            return dados
    raise SaidaInvalida(erros)
