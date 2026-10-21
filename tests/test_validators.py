from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from core.guardrails.validators import (
    Config,
    PlanoInvalido,
    carregar_config,
    exigir_plano_valido,
    validar_plano,
)
from core.schemas import Acao, MeetingInput, PlanoAcao

CFG = Config(
    diretorias=frozenset({"diretoria: pessoas", "diretoria: projetos"}),
    tipos=frozenset({"tipo: acao"}),
    membros=frozenset({"Ana"}),
)
REUNIAO = MeetingInput(
    titulo="Gestão", data=date(2026, 10, 14), acompanhamento="ok", problemas=["x", "y"]
)


def acao(**kw) -> Acao:
    base = dict(
        id="a1",
        titulo="Padronizar onboarding",
        descricao="d",
        criterios_aceite=["c"],
        labels=["diretoria: pessoas", "tipo: acao"],
        prioridade="alta",
        severidade="media",
        estimativa=3,
        problema_origem="p1",
    )
    return Acao(**{**base, **kw})


def plano(*acoes: Acao, **kw) -> PlanoAcao:
    return PlanoAcao(reuniao_id="2026-10-14-gestao", acoes=list(acoes), **kw)


def erros(p: PlanoAcao, max_acoes: int = 12) -> list[str]:
    return validar_plano(p, REUNIAO, CFG, max_acoes)


def test_plano_valido():
    p = plano(acao(), acao(id="a2", titulo="Outro", problema_origem="p2"))
    assert erros(p) == []
    exigir_plano_valido(p, REUNIAO, CFG)


def test_label_fora_da_allowlist():
    assert any(
        "allowlist" in e
        for e in erros(
            plano(
                acao(labels=["diretoria: pessoas", "x"]),
                acao(id="a2", titulo="O", problema_origem="p2"),
            )
        )
    )


@pytest.mark.parametrize("labels", [["tipo: acao"], ["diretoria: pessoas", "diretoria: projetos"]])
def test_exatamente_uma_diretoria(labels):
    p = plano(acao(labels=labels), acao(id="a2", titulo="O", problema_origem="p2"))
    assert any("exatamente 1" in e for e in erros(p))


def test_problema_origem_inexistente():
    assert any("inexistente" in e for e in erros(plano(acao(problema_origem="p9"))))


def test_limites_de_acoes():
    assert any("entre 1 e" in e for e in erros(plano()))
    p = plano(acao(), acao(id="a2", titulo="O", problema_origem="p2"))
    assert any("entre 1 e" in e for e in erros(p, max_acoes=1))


def test_responsavel_e_prazo():
    p = plano(
        acao(responsavel="Zé", prazo=date(2026, 10, 1)),
        acao(
            id="a2", titulo="O", problema_origem="p2", responsavel="Ana", prazo=date(2026, 10, 14)
        ),
    )
    e = erros(p)
    assert any("responsável" in x for x in e) and any("prazo" in x for x in e)
    assert len(e) == 2  # a2 (Ana, prazo == data da reunião) é válida


def test_titulo_duplicado():
    p = plano(acao(), acao(id="a2", titulo=" padronizar ONBOARDING", problema_origem="p2"))
    assert any("duplicado" in e for e in erros(p))


def test_problema_sem_acao_exige_justificativa():
    assert any("p2" in e for e in erros(plano(acao())))
    assert erros(plano(acao(), justificativas={"p2": "fora do escopo"})) == []
    assert any("inexistente" in e for e in erros(plano(acao(), justificativas={"p9": "x"})))


def test_exigir_levanta_com_todos_os_erros():
    with pytest.raises(PlanoInvalido) as exc:
        exigir_plano_valido(plano(acao(problema_origem="p9")), REUNIAO, CFG)
    assert len(exc.value.erros) >= 2


def test_schemas_rejeitam_valores_invalidos():
    with pytest.raises(ValidationError):
        acao(estimativa=4)
    with pytest.raises(ValidationError):
        acao(criterios_aceite=[])
    with pytest.raises(ValidationError):
        acao(prioridade="critica")
    with pytest.raises(ValidationError):
        MeetingInput(titulo="t", data=date.today(), acompanhamento="a", problemas=[])


def test_carregar_config_do_repo():
    cfg = carregar_config(Path(__file__).parents[1] / "config")
    assert cfg.diretorias and cfg.membros


def test_carregar_config(tmp_path):
    (tmp_path / "labels.yaml").write_text(yaml.dump({"diretorias": ["d"]}))
    (tmp_path / "membros.yaml").write_text(yaml.dump({"membros": [{"nome": "Ana"}]}))
    assert carregar_config(tmp_path) == Config(frozenset({"d"}), frozenset(), frozenset({"Ana"}))
