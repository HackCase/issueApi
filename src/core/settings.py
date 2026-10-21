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
    database_url: str = "postgresql://user:pass@localhost:5432/atas"
    atas_mode: Literal["local", "github"] = "local"
    atas_repo: str = ""
    atas_branch: str = "main"
    github_token: str = ""
    max_acoes: int = 12
    max_turnos_grill: int = 5
    dedup_threshold: float = 0.85
    auto_approve: bool = False
    dry_run: bool = True
    config_dir: Path = RAIZ / "config"


@lru_cache
def get_settings() -> Settings:
    return Settings()
