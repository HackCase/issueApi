from .settings import RAIZ


def carregar_prompt(nome: str) -> str:
    """Lê prompts/<nome>.md (ex.: "ata.v1"); o nome é também a versão registrada no custo."""
    return (RAIZ / "prompts" / f"{nome}.md").read_text(encoding="utf-8")
