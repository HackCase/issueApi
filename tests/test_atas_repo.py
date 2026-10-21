import base64
import json

import httpx

from core.integrations.atas_repo import salvar_ata
from core.settings import Settings


def test_local_grava_em_out(tmp_path):
    s = Settings(atas_mode="local", out_dir=tmp_path)
    assert salvar_ata("2026-10-14-x", "# ata", s) == "docs/atas/2026-10-14-x.md"
    assert (tmp_path / "docs/atas/2026-10-14-x.md").read_text() == "# ata"


def test_dry_run_nao_commita(tmp_path):
    s = Settings(atas_mode="github", dry_run=True, out_dir=tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: 1 / 0))  # qualquer chamada falha
    salvar_ata("r", "x", s, client)
    assert (tmp_path / "docs/atas/r.md").exists()


def _github(existe: bool):
    reqs = []

    def handler(req: httpx.Request) -> httpx.Response:
        reqs.append(req)
        if req.method == "GET":
            return httpx.Response(200, json={"sha": "abc"}) if existe else httpx.Response(404)
        return httpx.Response(201, json={})

    return reqs, httpx.Client(transport=httpx.MockTransport(handler))


def test_github_cria_e_atualiza(tmp_path):
    s = Settings(
        atas_mode="github",
        dry_run=False,
        atas_repo="o/r",
        atas_branch="main",
        github_token="t",
        out_dir=tmp_path,
    )
    for existe in (False, True):
        reqs, client = _github(existe)
        salvar_ata("r", "olá", s, client)
        put = reqs[-1]
        assert put.method == "PUT" and put.url.path == "/repos/o/r/contents/docs/atas/r.md"
        body = json.loads(put.content)
        assert base64.b64decode(body["content"]).decode() == "olá"
        assert body["branch"] == "main" and ("sha" in body) is existe
        assert put.headers["authorization"] == "Bearer t"
    assert not any(tmp_path.iterdir())
