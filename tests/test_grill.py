from datetime import date

import pytest

from core.erros import ErroApi
from core.guardrails.sanitize import Sanitizador
from core.llm.fake import FakeLLM
from core.pipeline.comum import SaidaInvalida
from core.pipeline.grill import MAX_PERGUNTAS_RODADA, historico, iniciar, responder
from core.schemas import MeetingInput

R = MeetingInput(
    titulo="Gestão",
    data=date(2026, 10, 14),
    acompanhamento="Rotina normal, cliente Acme pediu prazo",
    problemas=["Falta de onboarding dos novos membros", "Entregas sem revisão de código"],
)


def rodada(n, pids=("p1", "p2")):
    return {
        "perguntas": [
            {"problema_id": p, "pergunta": f"Pergunta {n}{p}?", "recomendacao": f"Sugestão {n}{p}"}
            for p in pids
        ],
        "concluido": False,
    }


FIM = {"concluido": True, "justificativa": "tudo claro"}


def comecar(llm, max_rodadas=3):
    return iniciar(R, "s1", max_rodadas, llm, Sanitizador(["Acme"]))


def resp(s, llm, respostas=None, aceitar=(), todas=False, max_rodadas=None):
    return responder(s, R, respostas or {}, set(aceitar), todas, llm, Sanitizador())


def test_inicia_com_uma_rodada_de_varias_perguntas():
    llm = FakeLLM([rodada(1)])
    s = comecar(llm)
    ps = s.rodadas[0].perguntas
    assert s.status == "em_andamento" and [p.id for p in ps] == ["r1q1", "r1q2"]
    assert [p.problema_id for p in ps] == ["p1", "p2"]
    assert ps[0].recomendacao == "Sugestão 1p1" and ps[0].resposta is None
    assert len(llm.chamadas) == 1 and llm.chamadas[0]["forte"]


def test_uma_rodada_gasta_uma_chamada_so():
    llm = FakeLLM([rodada(1), FIM])
    s = resp(comecar(llm), llm, {"r1q1": "a", "r1q2": "b"})
    assert s.status == "concluida" and len(s.rodadas) == 1 and len(llm.chamadas) == 2


def test_aceitar_uma_a_uma_e_todas():
    llm = FakeLLM([rodada(1), FIM])
    s = resp(comecar(llm), llm, {"r1q1": "meu texto"}, aceitar=["r1q2"])
    ps = s.rodadas[0].perguntas
    assert ps[0].resposta == "meu texto" and ps[1].resposta == "Sugestão 1p2"

    llm = FakeLLM([rodada(1), FIM])
    s = resp(comecar(llm), llm, {"r1q1": "meu texto"}, todas=True)
    ps = s.rodadas[0].perguntas
    assert ps[0].resposta == "meu texto" and ps[1].resposta == "Sugestão 1p2"  # texto vence


def test_resposta_incompleta_ou_desconhecida_nao_salva_nada():
    llm = FakeLLM([rodada(1)])
    s = comecar(llm)
    with pytest.raises(ErroApi) as e:
        resp(s, llm, {"r1q1": "só esta"})
    assert e.value.status == 422 and e.value.erro == "respostas_incompletas"
    assert e.value.detalhe == "r1q2"
    with pytest.raises(ErroApi) as e:
        resp(s, llm, {"r1q1": "a", "r1q2": "b", "r9q9": "x"})
    assert e.value.erro == "pergunta_desconhecida"
    with pytest.raises(ErroApi) as e:  # em branco não conta
        resp(s, llm, {"r1q1": "a", "r1q2": "   "})
    assert e.value.erro == "respostas_incompletas"
    assert all(p.resposta is None for p in s.rodadas[0].perguntas) and len(llm.chamadas) == 1


def test_segunda_rodada_so_com_lacunas_e_para_no_limite_sem_chamar_o_llm():
    llm = FakeLLM([rodada(1), rodada(2, pids=("p1",))])
    s = comecar(llm, max_rodadas=2)
    s = resp(s, llm, todas=True)
    assert s.status == "em_andamento" and len(s.rodadas) == 2
    assert [p.id for p in s.rodadas[1].perguntas] == ["r2q1"]
    assert "Resposta: Sugestão 1p1" in llm.chamadas[1]["prompt"]
    assert "rodada 2 de no máximo 2" in llm.chamadas[1]["prompt"]
    s = resp(s, llm, {"r2q1": "fim"})
    assert s.status == "concluida" and len(s.rodadas) == 2 and len(llm.chamadas) == 2


def test_sessao_concluida_nao_aceita_resposta():
    llm = FakeLLM([rodada(1), FIM])
    s = resp(comecar(llm), llm, todas=True)
    with pytest.raises(ErroApi) as e:
        resp(s, llm, todas=True)
    assert e.value.status == 409


def test_historico_para_o_plano():
    llm = FakeLLM([rodada(1), FIM])
    s = resp(comecar(llm), llm, {"r1q1": "Ana", "r1q2": "Beto"})
    h = historico(s.rodadas)
    assert "Pergunta r1q1 (p1): Pergunta 1p1?\nResposta: Ana" in h and "Resposta: Beto" in h


def test_llm_nao_ve_cliente_mas_a_sessao_guarda_o_original():
    llm = FakeLLM(
        [{"perguntas": [{"pergunta": "O que a [CLIENTE_1] pediu?"}], "concluido": False}, FIM]
    )
    s = comecar(llm)
    assert "Acme" not in llm.chamadas[0]["prompt"]
    assert s.rodadas[0].perguntas[0].pergunta == "O que a Acme pediu?"
    responder(s, R, {"r1q1": "A Acme quer prazo"}, set(), False, llm, Sanitizador(["Acme"]))
    assert "Acme" not in llm.chamadas[1]["prompt"] and "[CLIENTE_1]" in llm.chamadas[1]["prompt"]


def test_saida_invalida_faz_retry_e_depois_falha():
    llm = FakeLLM([{"concluido": False}, rodada(1)])  # 1ª sem perguntas
    assert len(comecar(llm).rodadas[0].perguntas) == 2
    assert "rejeitada" in llm.chamadas[1]["prompt"]
    with pytest.raises(SaidaInvalida):
        comecar(FakeLLM([{"concluido": True}, "não é json"]))  # sem justificativa; depois lixo


def test_problema_inexistente_e_excesso_de_perguntas_sao_rejeitados():
    ruim = rodada(1, pids=("p7",))
    assert len(comecar(FakeLLM([ruim, rodada(1)])).rodadas[0].perguntas) == 2
    muitas = {"perguntas": [{"pergunta": f"P{i}?"} for i in range(MAX_PERGUNTAS_RODADA + 1)]}
    llm = FakeLLM([muitas, rodada(1)])
    assert len(comecar(llm).rodadas[0].perguntas) == 2 and "rejeitada" in llm.chamadas[1]["prompt"]
