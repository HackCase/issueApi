from pydantic import BaseModel, ConfigDict

from ..guardrails.sanitize import Sanitizador
from ..guardrails.validators import Config, validar_plano
from ..llm.base import LLMClient
from ..prompts import carregar_prompt
from ..schemas import Acao, GrillSessao, MeetingInput, PlanoAcao
from .comum import chamar_json, delimitar, texto_reuniao
from .grill import historico

PROMPT = "plano.v1"


class PlanoGerado(BaseModel):
    """O que o LLM devolve; reuniao_id e status são do código, não do modelo."""

    model_config = ConfigDict(extra="forbid")

    acoes: list[Acao]
    justificativas: dict[str, str] = {}


def _system(cfg: Config, max_acoes: int, contexto: str) -> str:
    def lista(xs):
        return ", ".join(f'"{x}"' for x in sorted(xs)) or "(nenhum)"

    return (
        carregar_prompt(PROMPT)
        .replace("{{contexto}}", contexto.strip() or "(não informado)")
        .replace("{{max_acoes}}", str(max_acoes))
        .replace("{{labels_diretoria}}", lista(cfg.diretorias))
        .replace("{{labels_tipo}}", lista(cfg.tipos))
        .replace("{{membros}}", lista(cfg.membros))
    )


def gerar_plano(
    reuniao: MeetingInput,
    ata_md: str,
    grill: GrillSessao | None,
    cfg: Config,
    max_acoes: int,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str = "",
) -> PlanoAcao:
    """Rascunho validado pelo schema e pelos guardrails (5.4); 1 retry, depois SaidaInvalida."""
    rid = reuniao.reuniao_id
    prompt = "\n".join(
        [
            delimitar("reuniao", texto_reuniao(san.mascarar_reuniao(reuniao))),
            delimitar("ata", san.mascarar(ata_md)),
            delimitar(
                "grill", san.mascarar(historico(grill.turnos) if grill else "") or "(sem grill)"
            ),
        ]
    )

    def validar(g: PlanoGerado) -> list[str]:
        p = PlanoAcao(reuniao_id=rid, acoes=g.acoes, justificativas=g.justificativas)
        return validar_plano(p, reuniao, cfg, max_acoes)

    gerado = chamar_json(
        llm,
        prompt,
        PlanoGerado,
        system=_system(cfg, max_acoes, contexto),
        etapa="plano",
        prompt_versao=PROMPT,
        reuniao_id=rid,
        validar=validar,
    )
    dados = san.reverter_dados(gerado.model_dump(mode="json"))
    return PlanoAcao(reuniao_id=rid, status="rascunho", **dados)
