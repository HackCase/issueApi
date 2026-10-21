from fastapi import APIRouter, Depends

from ..deps import carregar_contexto, get_config, get_llm, get_store, novo_sanitizador
from ..erros import ErroApi
from ..guardrails.validators import exigir_plano_valido
from ..pipeline.plano import gerar_plano
from ..rotas.grill import _reuniao
from ..schemas import GrillSessao, PlanoAcao
from ..settings import Settings, get_settings
from ..store import obter, salvar

router = APIRouter()


def _plano_rascunho(store, reuniao_id: str) -> PlanoAcao:
    plano = obter(store, "plano", reuniao_id, PlanoAcao)
    if plano is None:
        raise ErroApi(404, "plano_nao_encontrado", reuniao_id)
    if plano.status == "aprovado":
        raise ErroApi(409, "plano_aprovado", "o plano já foi aprovado e não pode mais ser editado")
    return plano


@router.post("/reunioes/{reuniao_id}/plano")
def gerar(
    reuniao_id: str,
    s: Settings = Depends(get_settings),
    llm=Depends(get_llm),
    store=Depends(get_store),
) -> PlanoAcao:
    reg = _reuniao(store, reuniao_id)
    existente = obter(store, "plano", reuniao_id, PlanoAcao)
    if existente and existente.status == "aprovado":
        raise ErroApi(409, "plano_aprovado", "já existe um plano aprovado")
    sessao = obter(store, "grill", reg.sessao_id, GrillSessao) if reg.sessao_id else None
    if sessao and sessao.status != "concluida":
        raise ErroApi(409, "grill_em_andamento", "conclua a sessão de grill antes do plano")
    plano = gerar_plano(
        reg.reuniao,
        reg.ata_md,
        sessao,
        get_config(s),
        s.max_acoes,
        llm,
        novo_sanitizador(s),
        carregar_contexto(s),
    )
    if s.auto_approve:  # só para testes (SPEC seção 4)
        plano = plano.model_copy(update={"status": "aprovado"})
    salvar(store, "plano", reuniao_id, plano)
    return plano


@router.patch("/reunioes/{reuniao_id}/plano")
def editar(
    reuniao_id: str,
    corpo: PlanoAcao,
    s: Settings = Depends(get_settings),
    store=Depends(get_store),
) -> PlanoAcao:
    reg = _reuniao(store, reuniao_id)
    _plano_rascunho(store, reuniao_id)
    # aprovar só pela rota própria; o id da reunião vem da URL
    plano = corpo.model_copy(update={"reuniao_id": reuniao_id, "status": "rascunho"})
    exigir_plano_valido(plano, reg.reuniao, get_config(s), s.max_acoes)
    salvar(store, "plano", reuniao_id, plano)
    return plano


@router.post("/reunioes/{reuniao_id}/plano/aprovar")
def aprovar(
    reuniao_id: str,
    s: Settings = Depends(get_settings),
    store=Depends(get_store),
) -> PlanoAcao:
    reg = _reuniao(store, reuniao_id)
    plano = obter(store, "plano", reuniao_id, PlanoAcao)
    if plano is None:
        raise ErroApi(404, "plano_nao_encontrado", reuniao_id)
    exigir_plano_valido(plano, reg.reuniao, get_config(s), s.max_acoes)
    plano = plano.model_copy(update={"status": "aprovado"})
    salvar(store, "plano", reuniao_id, plano)
    return plano
