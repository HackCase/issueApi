from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import carregar_contexto, get_llm, get_store, novo_sanitizador
from ..erros import ErroApi
from ..pipeline import grill
from ..schemas import GrillSessao
from ..settings import Settings, get_settings
from ..store import ReuniaoRegistro, obter, salvar

router = APIRouter()


class RespostaGrill(BaseModel):
    resposta: str | None = None
    aceitar_recomendacao: bool = False


def _reuniao(store, reuniao_id: str) -> ReuniaoRegistro:
    reg = obter(store, "reuniao", reuniao_id, ReuniaoRegistro)
    if reg is None:
        raise ErroApi(404, "reuniao_nao_encontrada", reuniao_id)
    return reg


@router.post("/reunioes/{reuniao_id}/grill")
def iniciar_grill(
    reuniao_id: str,
    s: Settings = Depends(get_settings),
    llm=Depends(get_llm),
    store=Depends(get_store),
) -> GrillSessao:
    reg = _reuniao(store, reuniao_id)
    if reg.sessao_id:  # idempotente: uma sessão por reunião
        return obter(store, "grill", reg.sessao_id, GrillSessao)
    sessao = grill.iniciar(
        reg.reuniao, uuid4().hex, s.max_turnos_grill, llm, novo_sanitizador(s), carregar_contexto(s)
    )
    salvar(store, "grill", sessao.sessao_id, sessao)
    salvar(store, "reuniao", reuniao_id, reg.model_copy(update={"sessao_id": sessao.sessao_id}))
    return sessao


@router.post("/grill/{sessao_id}/respostas")
def responder_grill(
    sessao_id: str,
    corpo: RespostaGrill,
    s: Settings = Depends(get_settings),
    llm=Depends(get_llm),
    store=Depends(get_store),
) -> GrillSessao:
    sessao = obter(store, "grill", sessao_id, GrillSessao)
    if sessao is None:
        raise ErroApi(404, "sessao_nao_encontrada", sessao_id)
    reg = _reuniao(store, sessao.reuniao_id)
    nova = grill.responder(
        sessao,
        reg.reuniao,
        corpo.resposta,
        corpo.aceitar_recomendacao,
        llm,
        novo_sanitizador(s),
        carregar_contexto(s),
    )
    salvar(store, "grill", sessao_id, nova)
    return nova
