import base64

import httpx

from ..settings import Settings

API = "https://api.github.com"


def ata_path(reuniao_id: str) -> str:
    return f"docs/atas/{reuniao_id}.md"


def _commit_github(s: Settings, path: str, conteudo: str, client: httpx.Client) -> None:
    url = f"{API}/repos/{s.atas_repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {s.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    atual = client.get(url, params={"ref": s.atas_branch}, headers=headers)
    body = {
        "message": f"docs(atas): {path.rsplit('/', 1)[-1]}",
        "content": base64.b64encode(conteudo.encode()).decode(),
        "branch": s.atas_branch,
    }
    if atual.status_code == 200:
        body["sha"] = atual.json()["sha"]  # sobrescreve a ata existente
    elif atual.status_code != 404:
        atual.raise_for_status()
    client.put(url, json=body, headers=headers).raise_for_status()


def salvar_ata(
    reuniao_id: str, markdown: str, s: Settings, client: httpx.Client | None = None
) -> str:
    """Salva a ata e devolve o caminho dentro do repo de atas.

    Modo `local` e `DRY_RUN` gravam só em `out_dir` (nunca commitam); `github` sem
    `DRY_RUN` faz commit na branch configurada.
    """
    path = ata_path(reuniao_id)
    if s.atas_mode == "github" and not s.dry_run:
        with client or httpx.Client(timeout=30) as c:
            _commit_github(s, path, markdown, c)
    else:
        destino = s.out_dir / path
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(markdown, encoding="utf-8")
    return path
