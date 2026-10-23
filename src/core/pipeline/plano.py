import logging

from pydantic import BaseModel, ConfigDict

from ..guardrails.sanitize import Sanitizador
from ..guardrails.validators import Config, validar_plano
from ..llm.base import LLMClient
from ..memory.memoria import Memoria
from ..prompts import carregar_prompt
from ..schemas import Acao, GrillSessao, MeetingInput, PlanoAcao
from .comum import chamar_json, delimitar, texto_reuniao
from .grill import historico

PROMPT = "plano.v1"
logger = logging.getLogger(__name__)


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
    memoria: Memoria | None = None,
) -> PlanoAcao:
    """Rascunho validado pelo schema e pelos guardrails (5.4); 1 retry, depois SaidaInvalida.

    Com `memoria`, inclui recorrência no contexto e sinaliza possíveis duplicatas; se a memória
    falhar, o plano sai sem ela e com um aviso (modo degradado).
    """
    rid = reuniao.reuniao_id
    avisos: list[str] = []
    recorrencias: dict[str, int] = {}
    historico_mem = ""
    if memoria:
        try:
            recorrencias, historico_mem = memoria.historico_problemas(reuniao, san)
        except Exception as e:  # noqa: BLE001 - qualquer falha da memória é degradação
            logger.warning("memória vetorial falhou (histórico): %s", e)
            avisos.append(f"memória vetorial indisponível: {e}")
    prompt = "\n".join(
        [
            delimitar("reuniao", texto_reuniao(san.mascarar_reuniao(reuniao))),
            delimitar("ata", san.mascarar(ata_md)),
            delimitar(
                "grill", san.mascarar(historico(grill.rodadas) if grill else "") or "(sem grill)"
            ),
            *([delimitar("historico", san.mascarar(historico_mem))] if historico_mem else []),
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
    plano = PlanoAcao(reuniao_id=rid, status="rascunho", **dados)

    duplicatas = {}
    if memoria and not avisos:  # se o histórico já falhou, a memória toda está fora
        try:
            duplicatas = memoria.duplicatas(plano, san)
        except Exception as e:  # noqa: BLE001
            logger.warning("memória vetorial falhou (duplicatas): %s", e)
            avisos.append(f"memória vetorial indisponível: {e}")
    return plano.model_copy(
        update={"recorrencias": recorrencias, "possiveis_duplicatas": duplicatas, "avisos": avisos}
    )
