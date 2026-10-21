from fastapi import APIRouter, Depends

from ..deps import carregar_contexto, get_llm, get_store, novo_sanitizador
from ..integrations.atas_repo import salvar_ata
from ..pipeline.ata import gerar_ata
from ..schemas import MeetingInput
from ..settings import Settings, get_settings
from ..store import ReuniaoRegistro, salvar

router = APIRouter()


@router.post("/reunioes")
def criar_reuniao(
    reuniao: MeetingInput,
    s: Settings = Depends(get_settings),
    llm=Depends(get_llm),
    store=Depends(get_store),
):
    ata = gerar_ata(reuniao, llm, novo_sanitizador(s), carregar_contexto(s))
    ata_path = salvar_ata(reuniao.reuniao_id, ata, s)
    # reenviar a mesma reunião recomeça o fluxo (sessão de grill e plano ficam órfãos)
    salvar(
        store,
        "reuniao",
        reuniao.reuniao_id,
        ReuniaoRegistro(reuniao=reuniao, ata_path=ata_path, ata_md=ata),
    )
    return {"reuniao_id": reuniao.reuniao_id, "ata_path": ata_path}
