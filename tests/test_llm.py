import json

import pytest
from pydantic import BaseModel, ValidationError

from core.llm.fake import FakeLLM
from core.llm.providers import _extrair_json, build_client
from core.observability.cost import CustoLLM
from core.settings import Settings


class Saida(BaseModel):
    x: int


def test_fake_json_valido_e_invalido():
    llm = FakeLLM(['{"x": 1}', {"x": 2}, '{"x": "a"}'])
    assert llm.complete_json("p", Saida).dados == Saida(x=1)
    assert llm.complete_json("p", Saida).dados.x == 2
    with pytest.raises(ValidationError):
        llm.complete_json("p", Saida)
    assert len(llm.chamadas) == 3


def test_fake_sem_respostas_falha_alto():
    with pytest.raises(AssertionError):
        FakeLLM().complete("p")


def test_fake_embed_deterministico():
    a, b = FakeLLM().embed(["oi", "oi"])
    assert a == b and FakeLLM().embed(["tchau"])[0] != a


def test_extrair_json_remove_cercas():
    assert json.loads(_extrair_json('```json\n{"x": 1}\n```')) == {"x": 1}
    assert _extrair_json('{"x": 1}') == '{"x": 1}'


def test_custo_por_etapa():
    inner = FakeLLM(["um dois três", '{"x": 1}'])
    llm = CustoLLM(inner, {"fake": {"entrada_por_mtok": 1_000_000, "saida_por_mtok": 2_000_000}})
    llm.complete("a b", etapa="ata", prompt_versao="ata.v1", reuniao_id="r1")
    llm.complete_json("a b c", Saida, etapa="plano", reuniao_id="r1")
    r = llm.resumo("r1")
    assert r["ata"] == {"chamadas": 1, "tokens_in": 2, "tokens_out": 3, "custo": 2 + 6}
    assert r["plano"]["tokens_in"] == 3
    assert llm.chamadas[0].prompt_versao == "ata.v1" and llm.chamadas[0].latencia_s >= 0
    assert llm.resumo("outra") == {}


def test_custo_sem_preco_fica_none():
    llm = CustoLLM(FakeLLM(["x"]), {})
    llm.complete("p")
    assert llm.chamadas[0].custo is None


def test_build_client_por_provedor():
    assert type(build_client(Settings(llm_provider="anthropic"))).__name__ == "AnthropicClient"
    assert type(build_client(Settings(llm_provider="openai"))).__name__ == "OpenAIClient"
    with pytest.raises(NotImplementedError):
        build_client(Settings(llm_provider="gemini"))


def test_build_embedder_so_para_openai():
    from core.llm.providers import build_embedder

    assert build_embedder(Settings(llm_provider="anthropic", embedding_provider="")) is None
    e = build_embedder(
        Settings(
            llm_provider="anthropic",
            embedding_provider="openai",
            embedding_api_key="k",
            llm_api_key="outra",
        )
    )
    assert type(e).__name__ == "OpenAIClient" and e.s.llm_api_key == "k"
    s = Settings(llm_provider="openai", embedding_provider="", llm_api_key="x")
    s.embedding_api_key = ""
    assert build_embedder(s).s.llm_api_key == "x"
