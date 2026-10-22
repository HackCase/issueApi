from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"
    llm_api_key: str = ""
    llm_model_fast: str = ""
    llm_model_strong: str = ""
    embedding_model: str = ""
    embedding_provider: str = ""  # vazio = o mesmo de LLM_PROVIDER (só "openai" tem embeddings)
    embedding_api_key: str = ""  # vazio = LLM_API_KEY
    embedding_dim: int = 1536  # deve bater com EMBEDDING_MODEL (text-embedding-3-small = 1536)
    database_url: str = ""  # vazio = estado em memória (dev/testes)
    atas_mode: Literal["local", "github"] = "local"
    atas_repo: str = ""
    atas_branch: str = "main"
    github_token: str = ""
    cors_origins: str = "http://localhost:5173"  # separadas por vírgula
    max_acoes: int = 12
    max_turnos_grill: int = 5
    dedup_threshold: float = 0.85
    auto_approve: bool = False
    dry_run: bool = True
    config_dir: Path = RAIZ / "config"
    out_dir: Path = RAIZ / "out"


@lru_cache
def get_settings() -> Settings:
    return Settings()
