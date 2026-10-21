import pytest
from fastapi.testclient import TestClient

from core.deps import get_llm
from core.llm.fake import FakeLLM
from core.main import app
from core.settings import Settings, get_settings
from tests.test_ata import CORPO

BODY = {
    "titulo": "Gestão semanal",
    "data": "2026-10-14",
    "participantes": ["Ana"],
    "acompanhamento": "Rotina normal da semana, sem grandes mudanças.",
    "problemas": ["Falta de onboarding dos novos membros"],
}


@pytest.fixture
def client(tmp_path):
    llm = FakeLLM([CORPO])
    app.dependency_overrides[get_settings] = lambda: Settings(out_dir=tmp_path, atas_mode="local")
    app.dependency_overrides[get_llm] = lambda: llm
    yield TestClient(app), tmp_path, llm
    app.dependency_overrides.clear()


def test_post_reunioes_gera_e_salva_ata(client):
    c, out, _ = client
    r = c.post("/reunioes", json=BODY)
    assert r.status_code == 200
    assert r.json() == {
        "reuniao_id": "2026-10-14-gestao-semanal",
        "ata_path": "docs/atas/2026-10-14-gestao-semanal.md",
    }
    assert "## Resumo executivo" in (out / r.json()["ata_path"]).read_text()


def test_erros_no_formato_do_contrato(client):
    c, _, _ = client
    r = c.post("/reunioes", json={**BODY, "problemas": []})
    assert r.status_code == 422 and r.json()["erro"] == "entrada_invalida" and "detalhe" in r.json()
    r = c.post("/reunioes", json={**BODY, "acompanhamento": "ok", "problemas": ["x"]})
    assert r.status_code == 422 and r.json()["erro"] == "entrada_insuficiente"
    assert c.get("/nao-existe").json()["erro"] == "erro_http"


def test_ata_invalida_vira_502(client):
    c, _, llm = client
    llm.respostas[:] = ["lixo", "lixo"]
    r = c.post("/reunioes", json=BODY)
    assert r.status_code == 502 and r.json()["erro"] == "ata_invalida"
