import pytest
from fastapi.testclient import TestClient

from core.deps import get_llm, get_memoria, get_store
from core.llm.fake import FakeLLM
from core.main import app
from core.memory.memoria import Memoria
from core.memory.vector import VetoresMem
from core.settings import Settings, get_settings
from core.store import MemoryStore
from tests.test_api_reunioes import BODY
from tests.test_ata import CORPO
from tests.test_plano import acao

RID = "2026-10-14-gestao-semanal"


def q(n):
    return {"pergunta": f"P{n}?", "recomendacao": f"R{n}", "concluido": False}


def montar(tmp_path, respostas, **cfg):
    llm = FakeLLM(respostas)
    (tmp_path / "labels.yaml").write_text(
        'diretorias: ["diretoria: pessoas"]\ntipos: ["tipo: acao"]'
    )
    (tmp_path / "membros.yaml").write_text("membros: [{nome: Ana}]")
    app.dependency_overrides[get_settings] = lambda: Settings(
        out_dir=tmp_path, config_dir=tmp_path, max_turnos_grill=2, database_url="", **cfg
    )
    app.dependency_overrides[get_llm] = lambda: llm
    store = MemoryStore()
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app), llm


@pytest.fixture(autouse=True)
def _limpar():
    yield
    app.dependency_overrides.clear()


def plano_ok():
    return {"acoes": [acao(titulo="Padronizar onboarding", responsavel=None)]}


def test_fluxo_completo(tmp_path):
    c, _ = montar(tmp_path, [CORPO, q(1), q(2), plano_ok()])
    assert c.post("/reunioes", json=BODY).status_code == 200

    s = c.post(f"/reunioes/{RID}/grill").json()
    assert s["status"] == "em_andamento" and s["turnos"][0]["pergunta"] == "P1?"
    assert c.post(f"/reunioes/{RID}/grill").json()["sessao_id"] == s["sessao_id"]  # idempotente

    # plano antes do fim do grill é bloqueado
    r = c.post(f"/reunioes/{RID}/plano")
    assert r.status_code == 409 and r.json()["erro"] == "grill_em_andamento"

    url = f"/grill/{s['sessao_id']}/respostas"
    assert c.post(url, json={"resposta": "dono é a Ana"}).json()["status"] == "em_andamento"
    fim = c.post(url, json={"aceitar_recomendacao": True}).json()  # 2º turno = max_turnos
    assert fim["status"] == "concluida" and fim["turnos"][1]["resposta"] == "R2"
    assert c.post(url, json={"resposta": "x"}).status_code == 409

    p = c.post(f"/reunioes/{RID}/plano").json()
    assert p["status"] == "rascunho" and p["acoes"][0]["id"] == "a1"

    editado = {**p, "acoes": [{**p["acoes"][0], "titulo": "Novo título"}], "status": "aprovado"}
    r = c.patch(f"/reunioes/{RID}/plano", json=editado).json()
    assert r["acoes"][0]["titulo"] == "Novo título" and r["status"] == "rascunho"  # não aprova

    assert c.post(f"/reunioes/{RID}/plano/aprovar").json()["status"] == "aprovado"
    for r in (c.patch(f"/reunioes/{RID}/plano", json=editado), c.post(f"/reunioes/{RID}/plano")):
        assert r.status_code == 409 and r.json()["erro"] == "plano_aprovado"


def test_patch_invalido_e_rejeitado_e_nao_altera(tmp_path):
    c, _ = montar(tmp_path, [CORPO, {"concluido": True, "justificativa": "ok"}, plano_ok()])
    c.post("/reunioes", json=BODY)
    c.post(f"/reunioes/{RID}/grill")
    p = c.post(f"/reunioes/{RID}/plano").json()
    ruim = {**p, "acoes": [{**p["acoes"][0], "labels": ["tipo: acao"]}]}
    r = c.patch(f"/reunioes/{RID}/plano", json=ruim)
    assert r.status_code == 422 and r.json()["erro"] == "plano_invalido"
    assert "exatamente 1" in r.json()["detalhe"]
    assert (
        c.post(f"/reunioes/{RID}/plano/aprovar").json()["acoes"][0]["labels"]
        == p["acoes"][0]["labels"]
    )


def test_nao_encontrado_e_auto_approve(tmp_path):
    c, _ = montar(tmp_path, [CORPO, plano_ok()], auto_approve=True)
    for r in (
        c.post("/reunioes/nada/grill"),
        c.post("/reunioes/nada/plano"),
        c.post("/grill/nada/respostas", json={"resposta": "x"}),
    ):
        assert r.status_code == 404
    c.post("/reunioes", json=BODY)
    assert (
        c.patch(f"/reunioes/{RID}/plano", json={"reuniao_id": RID, "acoes": []}).status_code == 404
    )
    assert (
        c.post(f"/reunioes/{RID}/plano").json()["status"] == "aprovado"
    )  # sem grill, auto-approve


def test_saida_invalida_do_llm_vira_502(tmp_path):
    c, _ = montar(tmp_path, [CORPO, {"acoes": []}, {"acoes": []}])
    c.post("/reunioes", json=BODY)
    r = c.post(f"/reunioes/{RID}/plano")
    assert r.status_code == 502 and r.json()["erro"] == "saida_invalida"


def test_issues_so_apos_aprovar_e_atualiza_a_ata(tmp_path):
    c, _ = montar(tmp_path, [CORPO, {"concluido": True, "justificativa": "ok"}, plano_ok()])
    (tmp_path / "membros.yaml").write_text("membros: [{nome: Ana, github: ana-gh}]")
    c.post("/reunioes", json=BODY)
    assert c.post(f"/reunioes/{RID}/issues").json()["erro"] == "plano_nao_encontrado"
    c.post(f"/reunioes/{RID}/grill")
    c.post(f"/reunioes/{RID}/plano")
    r = c.post(f"/reunioes/{RID}/issues")
    assert r.status_code == 409 and r.json()["erro"] == "plano_nao_aprovado"
    assert not (tmp_path / "issues").exists()  # nada parcial

    c.post(f"/reunioes/{RID}/plano/aprovar")
    r = c.post(f"/reunioes/{RID}/issues")
    assert r.status_code == 200
    [item] = r.json()
    assert item["acao_id"] == "a1" and item["path"] == f"out/issues/{RID}/a1.yml"
    arquivo = tmp_path / "issues" / RID / "a1.yml"
    assert arquivo.read_text(encoding="utf-8") == item["conteudo"]
    ata = (tmp_path / f"docs/atas/{RID}.md").read_text(encoding="utf-8")
    assert "`out/issues/" in ata and "Preenchido após" not in ata
    assert c.post(f"/reunioes/{RID}/issues").json() == r.json()  # reexecutar é idempotente


def test_memoria_integrada_recorrencia_e_duplicata_entre_reunioes(tmp_path):
    ata2 = CORPO.replace("onboarding", "onboarding de membros")
    sem_grill = {"concluido": True, "justificativa": "ok"}
    c, _ = montar(
        tmp_path, [CORPO, sem_grill, plano_ok(), ata2, sem_grill, plano_ok()], auto_approve=True
    )
    mem = Memoria(VetoresMem(), FakeLLM(), 0.85)
    app.dependency_overrides[get_memoria] = lambda: mem

    c.post("/reunioes", json=BODY)
    c.post(f"/reunioes/{RID}/grill")
    primeiro = c.post(f"/reunioes/{RID}/plano").json()
    assert primeiro["recorrencias"] == {} and primeiro["possiveis_duplicatas"] == {}
    assert c.post(f"/reunioes/{RID}/issues").status_code == 200  # indexa as issues

    outra = {**BODY, "titulo": "Gestão extra", "data": "2026-10-21"}
    rid2 = "2026-10-21-gestao-extra"
    c.post("/reunioes", json=outra)
    c.post(f"/reunioes/{rid2}/grill")
    p = c.post(f"/reunioes/{rid2}/plano").json()
    assert p["recorrencias"] == {"p1": 1}
    assert p["possiveis_duplicatas"]["a1"]["reuniao_id"] == RID
    assert p["avisos"] == []


def test_memoria_fora_do_ar_nao_quebra_nenhuma_rota(tmp_path):
    class Quebrada:
        def __getattr__(self, nome):
            def falha(*a, **k):
                raise ConnectionError("banco fora")

            return falha

    c, _ = montar(tmp_path, [CORPO, {"concluido": True, "justificativa": "ok"}, plano_ok()])
    app.dependency_overrides[get_memoria] = lambda: Quebrada()
    assert c.post("/reunioes", json=BODY).status_code == 200
    c.post(f"/reunioes/{RID}/grill")
    p = c.post(f"/reunioes/{RID}/plano").json()
    assert p["acoes"] and "banco fora" in p["avisos"][0]
    c.post(f"/reunioes/{RID}/plano/aprovar")
    assert c.post(f"/reunioes/{RID}/issues").status_code == 200
