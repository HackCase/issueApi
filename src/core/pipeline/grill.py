from pydantic import BaseModel, model_validator

from ..erros import ErroApi
from ..guardrails.sanitize import Sanitizador
from ..llm.base import LLMClient
from ..prompts import carregar_prompt
from ..schemas import GrillSessao, GrillTurno, MeetingInput
from .comum import chamar_json, delimitar, texto_reuniao

PROMPT = "grill.v1"


class GrillSaida(BaseModel):
    pergunta: str | None = None
    recomendacao: str | None = None
    concluido: bool = False
    justificativa: str | None = None

    @model_validator(mode="after")
    def _coerente(self):
        if self.concluido and not self.justificativa:
            raise ValueError("concluido=true exige justificativa")
        if not self.concluido and not self.pergunta:
            raise ValueError("sem pergunta e concluido=false")
        return self


def historico(turnos: list[GrillTurno]) -> str:
    return "\n\n".join(
        f"Pergunta {i}: {t.pergunta}\nResposta: {t.resposta}"
        for i, t in enumerate(turnos, 1)
        if t.resposta is not None
    )


def _proximo(
    reuniao: MeetingInput,
    turnos: list[GrillTurno],
    max_turnos: int,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str,
) -> GrillSaida:
    system = carregar_prompt(PROMPT).replace("{{contexto}}", contexto.strip() or "(não informado)")
    prompt = (
        delimitar("reuniao", texto_reuniao(san.mascarar_reuniao(reuniao)))
        + "\n"
        + delimitar("grill", san.mascarar(historico(turnos)) or "(nenhuma resposta ainda)")
        + f"\n\nEsta será a pergunta {len(turnos) + 1} de no máximo {max_turnos}."
    )
    saida = chamar_json(
        llm,
        prompt,
        GrillSaida,
        system=system,
        etapa="grill",
        prompt_versao=PROMPT,
        reuniao_id=reuniao.reuniao_id,
    )
    return GrillSaida.model_validate(san.reverter_dados(saida.model_dump()))


def _aplicar(sessao: GrillSessao, saida: GrillSaida) -> GrillSessao:
    if saida.concluido:
        return sessao.model_copy(update={"status": "concluida"})
    turno = GrillTurno(pergunta=saida.pergunta, recomendacao=saida.recomendacao)
    return sessao.model_copy(update={"turnos": [*sessao.turnos, turno]})


def iniciar(
    reuniao: MeetingInput,
    sessao_id: str,
    max_turnos: int,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str = "",
) -> GrillSessao:
    sessao = GrillSessao(
        sessao_id=sessao_id,
        reuniao_id=reuniao.reuniao_id,
        turnos=[],
        status="em_andamento",
        max_turnos=max_turnos,
    )
    return _aplicar(sessao, _proximo(reuniao, [], max_turnos, llm, san, contexto))


def responder(
    sessao: GrillSessao,
    reuniao: MeetingInput,
    resposta: str | None,
    aceitar_recomendacao: bool,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str = "",
) -> GrillSessao:
    if sessao.status == "concluida":
        raise ErroApi(409, "grill_concluido", "a sessão já foi concluída")
    atual = sessao.turnos[-1]
    if aceitar_recomendacao:
        resposta = atual.recomendacao
    if not (resposta and resposta.strip()):
        raise ErroApi(422, "resposta_vazia", "envie `resposta` ou `aceitar_recomendacao=true`")

    turnos = [*sessao.turnos[:-1], atual.model_copy(update={"resposta": resposta.strip()})]
    sessao = sessao.model_copy(update={"turnos": turnos})
    if len(turnos) >= sessao.max_turnos:  # limite de turnos: encerra sem nova chamada ao LLM
        return sessao.model_copy(update={"status": "concluida"})
    return _aplicar(sessao, _proximo(reuniao, turnos, sessao.max_turnos, llm, san, contexto))
