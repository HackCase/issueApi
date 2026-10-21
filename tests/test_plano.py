from datetime import date

import pytest

from core.guardrails.sanitize import Sanitizador
from core.guardrails.validators import Config
from core.llm.fake import FakeLLM
from core.pipeline.comum import SaidaInvalida
from core.pipeline.plano import gerar_plano
from core.schemas import GrillSessao, GrillTurno, MeetingInput

CFG = Config(frozenset({"diretoria: pessoas"}), frozenset({"tipo: acao"}), frozenset({"Ana"}))
R = MeetingInput(
    titulo="Gestão",
    data=date(2026, 10, 14),
    acompanhamento="Rotina normal, cliente Acme pediu prazo",
    problemas=["Falta de onboarding dos novos membros"],
)
GRILL = GrillSessao(
    sessao_id="s",
    reuniao_id=R.reuniao_id,
    turnos=[GrillTurno(pergunta="Quem é o dono?", resposta="Ana, para a Acme")],
    status="concluida",
)


def acao(**kw):
    base = {
        "id": "a1",
        "titulo": "Padronizar onboarding da [CLIENTE_1]",
        "descricao": "d",
        "criterios_aceite": ["template publicado"],
        "labels": ["diretoria: pessoas", "tipo: acao"],
        "prioridade": "alta",
        "severidade": "media",
        "estimativa": 3,
        "responsavel": "Ana",
        "prazo": "2026-10-30",
        "problema_origem": "p1",
    }
    return {**base, **kw}


def gerar(llm):
    return gerar_plano(R, "# ata", GRILL, CFG, 12, llm, Sanitizador(["Acme"]), "ctx")


def test_plano_valido_vira_rascunho_com_dados_revertidos():
    llm = FakeLLM([{"acoes": [acao()]}])
    p = gerar(llm)
    assert p.status == "rascunho" and p.reuniao_id == R.reuniao_id
    assert p.acoes[0].titulo == "Padronizar onboarding da Acme"
    c = llm.chamadas[0]
    assert "Acme" not in c["prompt"] and "Ana, para" in c["prompt"] and c["etapa"] == "plano"
    assert '"diretoria: pessoas"' in c["system"] and '"Ana"' in c["system"]  # allowlists no prompt


def test_json_invalido_faz_um_retry_com_o_erro_do_pydantic():
    llm = FakeLLM([{"acoes": [acao(estimativa=4)]}, {"acoes": [acao()]}])
    assert gerar(llm).acoes[0].estimativa == 3
    retry = llm.chamadas[1]["prompt"]
    assert "rejeitada" in retry and "estimativa" in retry


def test_falha_de_guardrail_tambem_faz_retry_e_depois_falha_explicita():
    ruim = {"acoes": [acao(labels=["diretoria: inventada"])]}
    llm = FakeLLM([ruim, {"acoes": [acao()]}])
    gerar(llm)
    assert "allowlist" in llm.chamadas[1]["prompt"]
    llm = FakeLLM([ruim, ruim])
    with pytest.raises(SaidaInvalida) as e:
        gerar(llm)
    assert len(llm.chamadas) == 2 and any("allowlist" in x for x in e.value.erros)


def test_campos_extras_do_llm_sao_rejeitados():
    llm = FakeLLM([{"acoes": [acao()], "status": "aprovado"}, {"acoes": [acao()]}])
    assert gerar(llm).status == "rascunho"
    assert len(llm.chamadas) == 2


def test_justificativa_cobre_problema_sem_acao():
    r2 = R.model_copy(update={"problemas": ["a", "b"]})
    llm = FakeLLM([{"acoes": [acao()], "justificativas": {"p2": "fora do escopo"}}])
    p = gerar_plano(r2, "# ata", None, CFG, 12, llm, Sanitizador())
    assert (
        p.justificativas == {"p2": "fora do escopo"} and "(sem grill)" in llm.chamadas[0]["prompt"]
    )
