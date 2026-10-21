from fastapi import APIRouter, Depends

from ..deps import get_llm, novo_sanitizador
from ..integrations.atas_repo import salvar_ata
from ..pipeline.ata import gerar_ata
from ..schemas import MeetingInput
from ..settings import Settings, get_settings

router = APIRouter()


@router.post("/reunioes")
def criar_reuniao(reuniao: MeetingInput, s: Settings = Depends(get_settings), llm=Depends(get_llm)):
    contexto_arq = s.config_dir / "contexto_mega.md"
    contexto = contexto_arq.read_text(encoding="utf-8") if contexto_arq.exists() else ""
    ata = gerar_ata(reuniao, llm, novo_sanitizador(s), contexto)
    return {"reuniao_id": reuniao.reuniao_id, "ata_path": salvar_ata(reuniao.reuniao_id, ata, s)}
