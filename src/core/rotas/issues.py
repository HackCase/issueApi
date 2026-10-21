from fastapi import APIRouter, Depends

from ..deps import get_config, get_store
from ..erros import ErroApi
from ..integrations.atas_repo import salvar_ata
from ..pipeline.issues_yaml import atualizar_ata, caminho_yaml, gerar_issues
from ..rotas.grill import _reuniao
from ..schemas import PlanoAcao
from ..settings import Settings, get_settings
from ..store import obter, salvar

router = APIRouter()


@router.post("/reunioes/{reuniao_id}/issues")
def gerar(reuniao_id: str, s: Settings = Depends(get_settings), store=Depends(get_store)):
    reg = _reuniao(store, reuniao_id)
    plano = obter(store, "plano", reuniao_id, PlanoAcao)
    if plano is None:
        raise ErroApi(404, "plano_nao_encontrado", reuniao_id)
    yamls = gerar_issues(plano, reg.reuniao, reg.ata_path, get_config(s), s.max_acoes)

    pasta = s.out_dir / "issues" / reuniao_id  # sempre dentro de out/, inclusive com DRY_RUN
    pasta.mkdir(parents=True, exist_ok=True)
    for acao_id, texto in yamls.items():
        (pasta / f"{acao_id}.yml").write_text(texto, encoding="utf-8")

    ata = atualizar_ata(reg.ata_md, plano)
    salvar_ata(reuniao_id, ata, s)
    salvar(store, "reuniao", reuniao_id, reg.model_copy(update={"ata_md": ata}))
    return [
        {"acao_id": a, "path": caminho_yaml(reuniao_id, a), "conteudo": t} for a, t in yamls.items()
    ]
