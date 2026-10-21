import re

import yaml

from ..guardrails.sanitize import Sanitizador
from ..llm.base import LLMClient
from ..prompts import carregar_prompt
from ..schemas import MeetingInput
from .comum import delimitar, texto_reuniao

PROMPT = "ata.v1"
SECOES = ["## Resumo executivo", "## Acompanhamento", "## Problemas levantados"]
MIN_CARACTERES = 30  # ponytail: só tamanho mínimo; adicionar classificação barata se vier lixo


class EntradaInsuficiente(ValueError):
    pass


class AtaInvalida(RuntimeError):
    pass


def _limpar(corpo: str) -> str:
    corpo = corpo.strip()
    m = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*?)\n```", corpo, re.DOTALL)
    return (m.group(1) if m else corpo).strip()


def _estrutura_ok(corpo: str) -> bool:
    titulos = [ln.strip() for ln in corpo.splitlines() if ln.startswith("## ")]
    return titulos == SECOES


def _frontmatter(r: MeetingInput) -> str:
    meta = {
        "id": r.reuniao_id,
        "title": f"{r.titulo} — {r.data:%d/%m/%Y}",
        "date": r.data,
        "participantes": r.participantes,
    }
    yml = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=None)
    return f"---\n{yml}---\n"


def gerar_ata(
    reuniao: MeetingInput, llm: LLMClient, sanitizador: Sanitizador, contexto: str = ""
) -> str:
    """Markdown completo da ata (frontmatter Docusaurus + seções). O LLM só escreve o corpo."""
    if len(reuniao.acompanhamento.strip()) + sum(len(p.strip()) for p in reuniao.problemas) < (
        MIN_CARACTERES
    ):
        raise EntradaInsuficiente("informe mais contexto sobre o acompanhamento e os problemas")

    system = carregar_prompt(PROMPT).replace("{{contexto}}", contexto.strip() or "(não informado)")
    entrada = delimitar("reuniao", texto_reuniao(sanitizador.mascarar_reuniao(reuniao)))

    for _ in range(2):  # 1 retry
        r = llm.complete(
            entrada,
            system=system,
            etapa="ata",
            prompt_versao=PROMPT,
            reuniao_id=reuniao.reuniao_id,
        )
        corpo = sanitizador.reverter(_limpar(r.texto))
        if _estrutura_ok(corpo):
            decisoes = "## Decisões e próximos passos\n\n_Preenchido após a aprovação do plano._"
            return f"{_frontmatter(reuniao)}\n{corpo}\n\n{decisoes}\n"
    raise AtaInvalida("o modelo não devolveu as seções esperadas da ata")
