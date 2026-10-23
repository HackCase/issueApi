from pydantic import BaseModel, model_validator

from ..erros import ErroApi
from ..guardrails.sanitize import Sanitizador
from ..llm.base import LLMClient
from ..prompts import carregar_prompt
from ..schemas import GrillPergunta, GrillRodada, GrillSessao, MeetingInput
from .comum import chamar_json, delimitar, texto_reuniao

PROMPT = "grill.v2"
MAX_PERGUNTAS_RODADA = 8


class PerguntaSaida(BaseModel):
    problema_id: str | None = None
    pergunta: str
    recomendacao: str | None = None


class GrillSaida(BaseModel):
    perguntas: list[PerguntaSaida] = []
    concluido: bool = False
    justificativa: str | None = None

    @model_validator(mode="after")
    def _coerente(self):
        if self.concluido and not self.justificativa:
            raise ValueError("concluido=true exige justificativa")
        if not self.concluido and not self.perguntas:
            raise ValueError("sem perguntas e concluido=false")
        return self


def historico(rodadas: list[GrillRodada]) -> str:
    return "\n\n".join(
        f"Pergunta {p.id}" + (f" ({p.problema_id})" if p.problema_id else "") + f": {p.pergunta}\n"
        f"Resposta: {p.resposta}"
        for r in rodadas
        for p in r.perguntas
        if p.resposta is not None
    )


def _validar(reuniao: MeetingInput):
    def validar(saida: GrillSaida) -> list[str]:
        erros = []
        if len(saida.perguntas) > MAX_PERGUNTAS_RODADA:
            erros.append(f"no máximo {MAX_PERGUNTAS_RODADA} perguntas por rodada")
        for p in saida.perguntas:
            if p.problema_id is not None and p.problema_id not in reuniao.problema_ids:
                erros.append(f"problema_id inválido: {p.problema_id}")
        return erros

    return validar


def _proximo(
    reuniao: MeetingInput,
    rodadas: list[GrillRodada],
    max_rodadas: int,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str,
) -> GrillSaida:
    system = carregar_prompt(PROMPT).replace("{{contexto}}", contexto.strip() or "(não informado)")
    prompt = (
        delimitar("reuniao", texto_reuniao(san.mascarar_reuniao(reuniao)))
        + "\n"
        + delimitar("grill", san.mascarar(historico(rodadas)) or "(nenhuma resposta ainda)")
        + f"\n\nEsta será a rodada {len(rodadas) + 1} de no máximo {max_rodadas}."
    )
    saida = chamar_json(
        llm,
        prompt,
        GrillSaida,
        system=system,
        etapa="grill",
        prompt_versao=PROMPT,
        reuniao_id=reuniao.reuniao_id,
        validar=_validar(reuniao),
    )
    return GrillSaida.model_validate(san.reverter_dados(saida.model_dump()))


def _aplicar(sessao: GrillSessao, saida: GrillSaida) -> GrillSessao:
    if saida.concluido:
        return sessao.model_copy(update={"status": "concluida"})
    n = len(sessao.rodadas) + 1
    rodada = GrillRodada(
        perguntas=[
            GrillPergunta(id=f"r{n}q{i}", **p.model_dump())
            for i, p in enumerate(saida.perguntas, 1)
        ]
    )
    return sessao.model_copy(update={"rodadas": [*sessao.rodadas, rodada]})


def iniciar(
    reuniao: MeetingInput,
    sessao_id: str,
    max_rodadas: int,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str = "",
) -> GrillSessao:
    sessao = GrillSessao(
        sessao_id=sessao_id,
        reuniao_id=reuniao.reuniao_id,
        rodadas=[],
        status="em_andamento",
        max_rodadas=max_rodadas,
    )
    return _aplicar(sessao, _proximo(reuniao, [], max_rodadas, llm, san, contexto))


def _responder_rodada(
    rodada: GrillRodada, respostas: dict[str, str], aceitar: set[str], aceitar_todas: bool
) -> GrillRodada:
    """Texto digitado > aceitar a recomendação da pergunta > aceitar todas."""
    desconhecidas = sorted((set(respostas) | aceitar) - {p.id for p in rodada.perguntas})
    if desconhecidas:
        raise ErroApi(422, "pergunta_desconhecida", ", ".join(desconhecidas))
    novas, faltam = [], []
    for p in rodada.perguntas:
        texto = (respostas.get(p.id) or "").strip()
        if not texto and (aceitar_todas or p.id in aceitar):
            texto = (p.recomendacao or "").strip()
        if not texto:
            faltam.append(p.id)
        novas.append(p.model_copy(update={"resposta": texto or None}))
    if faltam:
        raise ErroApi(422, "respostas_incompletas", ", ".join(faltam))
    return GrillRodada(perguntas=novas)


def responder(
    sessao: GrillSessao,
    reuniao: MeetingInput,
    respostas: dict[str, str],
    aceitar: set[str],
    aceitar_todas: bool,
    llm: LLMClient,
    san: Sanitizador,
    contexto: str = "",
) -> GrillSessao:
    """`respostas`: id -> texto. `aceitar`: ids que usam a recomendação. Toda pergunta da rodada
    em aberto precisa terminar respondida, senão 422 e nada é salvo."""
    if sessao.status == "concluida":
        raise ErroApi(409, "grill_concluido", "a sessão já foi concluída")
    atual = _responder_rodada(sessao.rodadas[-1], respostas, aceitar, aceitar_todas)
    rodadas = [*sessao.rodadas[:-1], atual]
    sessao = sessao.model_copy(update={"rodadas": rodadas})
    if len(rodadas) >= sessao.max_rodadas:  # limite de rodadas: encerra sem nova chamada ao LLM
        return sessao.model_copy(update={"status": "concluida"})
    return _aplicar(sessao, _proximo(reuniao, rodadas, sessao.max_rodadas, llm, san, contexto))
