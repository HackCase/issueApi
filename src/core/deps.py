from functools import lru_cache

from .guardrails.sanitize import Sanitizador, carregar_clientes
from .llm.providers import build_client
from .observability.cost import CustoLLM, carregar_precos
from .settings import Settings, get_settings


@lru_cache
def get_llm() -> CustoLLM:
    s = get_settings()
    return CustoLLM(build_client(s), carregar_precos(s.config_dir / "precos.yaml"))


def novo_sanitizador(s: Settings) -> Sanitizador:
    return Sanitizador(carregar_clientes(s.config_dir))
