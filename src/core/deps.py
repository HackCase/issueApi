from functools import lru_cache

from .guardrails.sanitize import Sanitizador, carregar_clientes
from .guardrails.validators import Config, carregar_config
from .llm.providers import build_client
from .observability.cost import CustoLLM, carregar_precos
from .settings import Settings, get_settings
from .store import build_store


@lru_cache
def get_llm() -> CustoLLM:
    s = get_settings()
    return CustoLLM(build_client(s), carregar_precos(s.config_dir / "precos.yaml"))


@lru_cache
def get_store():
    return build_store(get_settings())


def novo_sanitizador(s: Settings) -> Sanitizador:
    return Sanitizador(carregar_clientes(s.config_dir))


def carregar_contexto(s: Settings) -> str:
    arq = s.config_dir / "contexto_mega.md"
    return arq.read_text(encoding="utf-8") if arq.exists() else ""


def get_config(s: Settings) -> Config:
    return carregar_config(s.config_dir)
