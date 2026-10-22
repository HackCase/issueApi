import logging
from functools import lru_cache

from .guardrails.sanitize import Sanitizador, carregar_clientes
from .guardrails.validators import Config, carregar_config
from .llm.providers import build_client, build_embedder
from .memory.memoria import Memoria
from .memory.vector import PgVetores
from .observability.cost import CustoLLM, carregar_precos
from .settings import Settings, get_settings
from .store import build_store

logger = logging.getLogger(__name__)


@lru_cache
def get_llm() -> CustoLLM:
    s = get_settings()
    return CustoLLM(build_client(s), carregar_precos(s.config_dir / "precos.yaml"))


@lru_cache
def get_store():
    return build_store(get_settings())


@lru_cache
def get_memoria() -> Memoria | None:
    """None (memória desligada) sem DATABASE_URL ou sem provedor de embeddings."""
    s = get_settings()
    embedder = build_embedder(s)
    if not s.database_url or embedder is None:
        logger.info("memória vetorial desligada (sem DATABASE_URL ou provedor de embeddings)")
        return None
    return Memoria(PgVetores(s.database_url, s.embedding_dim), embedder, s.dedup_threshold)


def novo_sanitizador(s: Settings) -> Sanitizador:
    return Sanitizador(carregar_clientes(s.config_dir))


def carregar_contexto(s: Settings) -> str:
    arq = s.config_dir / "contexto_mega.md"
    return arq.read_text(encoding="utf-8") if arq.exists() else ""


def get_config(s: Settings) -> Config:
    return carregar_config(s.config_dir)
