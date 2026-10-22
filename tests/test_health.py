from fastapi.testclient import TestClient

from core.main import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_metricas_sem_banco_vira_503(monkeypatch):
    from core.settings import get_settings

    monkeypatch.setattr(get_settings(), "database_url", "")
    r = TestClient(app).get("/issues/summary")
    assert r.status_code == 503 and r.json()["erro"] == "sem_banco"


def test_cors_libera_post_e_patch():
    r = TestClient(app).options(
        "/reunioes",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PATCH"},
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "PATCH" in r.headers["access-control-allow-methods"]
