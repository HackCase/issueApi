from fastapi import APIRouter, Depends

from ..deps import get_config
from ..settings import Settings, get_settings

router = APIRouter()


@router.get("/config")
def config(s: Settings = Depends(get_settings)):
    """Listas que o editor de plano precisa (allowlists de config/ e limite de ações)."""
    cfg = get_config(s)
    return {
        "diretorias": sorted(cfg.diretorias),
        "tipos": sorted(cfg.tipos),
        "membros": [{"nome": n, "github": cfg.logins.get(n)} for n in sorted(cfg.membros)],
        "max_acoes": s.max_acoes,
    }
