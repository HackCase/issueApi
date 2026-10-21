from datetime import date

import pytest

from core.erros import ErroApi
from core.guardrails.sanitize import Sanitizador
from core.llm.fake import FakeLLM
from core.pipeline.comum import SaidaInvalida
from core.pipeline.grill import iniciar, responder
from core.schemas import MeetingInput

R = MeetingInput(
    titulo="Gestão",
    data=date(2026, 10, 14),
    acompanhamento="Rotina normal, cliente Acme pediu prazo",
    problemas=["Falta de onboarding dos novos membros"],
)


def q(n):
    return {"pergunta": f"Pergunta {n}?", "recomendacao": f"Sugestão {n}", "concluido": False}


FIM = {"concluido": True, "justificativa": "tudo claro"}


def comecar(llm, max_turnos=3):
    return iniciar(R, "s1", max_turnos, llm, Sanitizador(["Acme"]))


def test_inicia_com_primeira_pergunta_e_recomendacao():
    llm = FakeLLM([q(1)])
    s = comecar(llm)
    assert s.status == "em_andamento" and s.turnos[0].pergunta == "Pergunta 1?"
    assert s.turnos[0].recomendacao == "Sugestão 1" and s.turnos[0].resposta is None
    assert llm.chamadas[0]["forte"] and llm.chamadas[0]["etapa"] == "grill"


def test_para_em_max_turnos_sem_chamar_o_llm_de_novo():
    llm = FakeLLM([q(1), q(2)])
    s = comecar(llm, max_turnos=2)
    s = responder(s, R, "resp 1", False, llm, Sanitizador())
    assert s.status == "em_andamento" and len(s.turnos) == 2
    s = responder(s, R, "resp 2", False, llm, Sanitizador())
    assert s.status == "concluida" and len(s.turnos) == 2 and s.turnos[-1].resposta == "resp 2"
    assert len(llm.chamadas) == 2


def test_para_quando_o_modelo_conclui():
    llm = FakeLLM([q(1), FIM])
    s = responder(comecar(llm), R, "ok", False, llm, Sanitizador())
    assert s.status == "concluida" and len(s.turnos) == 1


def test_aceitar_recomendacao_usa_a_sugestao():
    llm = FakeLLM([q(1), FIM])
    s = responder(comecar(llm), R, None, True, llm, Sanitizador())
    assert s.turnos[0].resposta == "Sugestão 1"


def test_resposta_vazia_e_sessao_concluida():
    llm = FakeLLM([q(1), FIM])
    s = comecar(llm)
    with pytest.raises(ErroApi) as e:
        responder(s, R, "  ", False, llm, Sanitizador())
    assert e.value.erro == "resposta_vazia"
    s = responder(s, R, "ok", False, llm, Sanitizador())
    with pytest.raises(ErroApi) as e:
        responder(s, R, "mais", False, llm, Sanitizador())
    assert e.value.status == 409


def test_llm_nao_ve_cliente_mas_a_sessao_guarda_o_original():
    llm = FakeLLM([{"pergunta": "O que a [CLIENTE_1] pediu?", "concluido": False}, q(2)])
    s = comecar(llm)
    assert "Acme" not in llm.chamadas[0]["prompt"]
    assert s.turnos[0].pergunta == "O que a Acme pediu?"
    responder(s, R, "A Acme quer prazo", False, llm, Sanitizador(["Acme"]))
    assert "Acme" not in llm.chamadas[1]["prompt"] and "[CLIENTE_1]" in llm.chamadas[1]["prompt"]


def test_saida_invalida_faz_retry_e_depois_falha():
    llm = FakeLLM([{"concluido": False}, q(1)])  # 1ª sem pergunta
    assert comecar(llm).turnos[0].pergunta == "Pergunta 1?"
    assert "rejeitada" in llm.chamadas[1]["prompt"]
    with pytest.raises(SaidaInvalida):
        comecar(FakeLLM([{"concluido": True}, "não é json"]))  # sem justificativa; depois lixo
