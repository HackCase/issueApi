import json
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml

from core.erros import ErroApi
from core.guardrails.validators import Config, PlanoInvalido
from core.pipeline.issues_yaml import SECAO_DECISOES, atualizar_ata, gerar_issues, render
from core.schemas import Acao, MeetingInput, PlanoAcao

SCHEMA = json.loads((Path(__file__).parent / "issue.schema.json").read_text())
CFG = Config(
    frozenset({"diretoria: pessoas"}),
    frozenset({"tipo: acao"}),
    frozenset({"Ana", "Bia"}),
    {"Ana": "ana-gh"},
)
ATA = "docs/atas/2026-10-14-gestao.md"
R = MeetingInput(titulo="Gestão", data=date(2026, 10, 14), acompanhamento="a", problemas=["x", "y"])


def acao(i=1, **kw) -> Acao:
    base = dict(
        id=f"a{i}",
        titulo=f'Padronizar: onboarding #{i} "novo"',
        descricao="Linha 1\n\nLinha 3 com ação e ç",
        criterios_aceite=["template publicado", "time treinado"],
        labels=["diretoria: pessoas", "tipo: acao"],
        prioridade="alta",
        severidade="media",
        estimativa=3,
        responsavel="Ana",
        prazo=date(2026, 10, 30),
        problema_origem=f"p{i}",
    )
    return Acao(**{**base, **kw})


def plano(*acoes, status="aprovado", **kw) -> PlanoAcao:
    return PlanoAcao(reuniao_id=R.reuniao_id, status=status, acoes=list(acoes), **kw)


P = plano(acao(1), acao(2, responsavel="Bia", prazo=None))


def test_yamls_validam_no_json_schema_e_fazem_roundtrip():
    saida = render(P, ATA, CFG.logins)
    assert list(saida) == ["a1", "a2"]
    for acao_id, texto in saida.items():
        doc = yaml.safe_load(texto)
        jsonschema.validate(doc, SCHEMA)
        assert doc["acao_id"] == acao_id and doc["schema_version"] == 1
    a1 = yaml.safe_load(saida["a1"])
    assert a1["title"] == 'Padronizar: onboarding #1 "novo"'
    assert a1["body"] == (
        "## Contexto\nLinha 1\n\nLinha 3 com ação e ç\n\n"
        "## Critérios de aceite\n- [ ] template publicado\n- [ ] time treinado\n\n"
        f"## Origem\nProblema p1 · Ata: {ATA}\n"
    )
    assert a1["labels"] == ["diretoria: pessoas", "tipo: acao"]
    assert a1["project_fields"] == {
        "prioridade": "alta",
        "severidade": "media",
        "estimativa": 3,
        "prazo": "2026-10-30",
    }
    assert a1["source"] == {"ata_path": ATA, "problema_id": "p1"}


def test_body_em_bloco_literal_como_na_spec():
    assert "body: |\n  ## Contexto\n" in render(P, ATA)["a1"]


def test_assignees_so_com_login_mapeado_e_prazo_nulo():
    saida = render(P, ATA, CFG.logins)
    assert yaml.safe_load(saida["a1"])["assignees"] == ["ana-gh"]
    a2 = yaml.safe_load(saida["a2"])  # Bia sem login
    assert a2["assignees"] == [] and a2["project_fields"]["prazo"] is None
    assert yaml.safe_load(render(P, ATA)["a1"])["assignees"] == []


def test_deterministico():
    assert render(P, ATA, CFG.logins) == render(P.model_copy(deep=True), ATA, CFG.logins)


def test_so_roda_com_plano_aprovado_e_valido():
    with pytest.raises(ErroApi) as e:
        gerar_issues(plano(acao(), status="rascunho"), R, ATA, CFG, 12)
    assert e.value.erro == "plano_nao_aprovado"
    ruim = plano(acao(1, labels=["tipo: acao"]), acao(2))
    with pytest.raises(PlanoInvalido):
        gerar_issues(ruim, R, ATA, CFG, 12)
    assert set(gerar_issues(P, R, ATA, CFG, 12)) == {"a1", "a2"}


def test_atualizar_ata_e_idempotente():
    ata = (
        f"---\nid: x\n---\n\n## Resumo executivo\nok\n\n{SECAO_DECISOES}\n\n_Preenchido depois._\n"
    )
    p = plano(acao(1), acao(2), justificativas={"p3": "fora do escopo"})
    nova = atualizar_ata(ata, p)
    assert "_Preenchido depois._" not in nova and nova.startswith(ata.split("##")[0])
    assert f"`out/issues/{R.reuniao_id}/a1.yml`" in nova and "Sem ação para p3: fora" in nova
    assert atualizar_ata(nova, p) == nova
    assert atualizar_ata("## Resumo\nok", p).count(SECAO_DECISOES) == 1


def test_exemplo_do_parceiro_e_valido():
    exemplo = Path(__file__).parents[1] / "docs" / "exemplo-issue.yml"
    jsonschema.validate(yaml.safe_load(exemplo.read_text(encoding="utf-8")), SCHEMA)
