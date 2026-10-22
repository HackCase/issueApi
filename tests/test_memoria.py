import os
from datetime import date

import pytest

from core.guardrails.sanitize import Sanitizador
from core.guardrails.validators import Config
from core.llm.fake import FakeLLM
from core.memory.dedupe import melhor_duplicata, recorrencia
from core.memory.memoria import Memoria
from core.memory.vector import Achado, Item, PgVetores, VetoresMem, cosseno
from core.pipeline.plano import gerar_plano
from core.schemas import MeetingInput
from tests.test_plano import acao

LIM = 0.85


def achado(rid="r1", ref="p1", sim=0.9):
    return Achado(rid, ref, "t", "texto", sim)


def reuniao(titulo="Gestão A", dia=14, problemas=("Falta de onboarding dos novos membros",)):
    return MeetingInput(
        titulo=titulo,
        data=date(2026, 10, dia),
        acompanhamento="Rotina normal da semana",
        problemas=list(problemas),
    )


class Espiao(FakeLLM):
    """Guarda o que foi enviado para embedding."""

    def __init__(self):
        super().__init__()
        self.enviados: list[str] = []

    def embed(self, textos):
        self.enviados += textos
        return super().embed(textos)


def memoria(vetores=None, emb=None):
    return Memoria(vetores or VetoresMem(), emb or Espiao(), LIM)


def test_cosseno():
    assert cosseno([1, 0], [1, 0]) == pytest.approx(1)
    assert cosseno([1, 0], [0, 1]) == 0 and cosseno([0, 0], [1, 1]) == 0


def test_recorrencia_conta_reunioes_distintas_acima_do_limiar():
    achados = [
        achado("r1"),
        achado("r1", "p2", 0.95),
        achado("r2", sim=0.86),
        achado("r3", sim=0.5),
    ]
    n, fortes = recorrencia(achados, LIM)
    assert n == 2 and len(fortes) == 3
    assert recorrencia([], LIM) == (0, [])


def test_melhor_duplicata_respeita_o_limiar():
    assert melhor_duplicata([achado(sim=0.84)], LIM) is None and melhor_duplicata([], LIM) is None
    d = melhor_duplicata([achado("r9", "a3", 0.91), achado(sim=0.9)], LIM)
    assert (d.reuniao_id, d.acao_id, d.similaridade) == ("r9", "a3", 0.91)


def test_recorrencia_entre_reunioes_e_exclui_a_propria():
    m = memoria()
    san = Sanitizador()
    r1, r2 = reuniao("Gestão A", 7), reuniao("Gestão B", 14)
    m.registrar_ata(r1, san)
    assert m.historico_problemas(r1, san) == ({}, "")  # a própria reunião não conta
    contagens, texto = m.historico_problemas(r2, san)
    assert contagens == {"p1": 1} and "(2026-10-07-gestao-a)" in texto and "onboarding" in texto
    novo = reuniao("Gestão C", 21, ("Servidor caiu duas vezes no deploy",))
    assert m.historico_problemas(novo, san) == ({}, "")


def test_registrar_substitui_chunks_da_mesma_reuniao():
    m = memoria()
    m.registrar_ata(reuniao(problemas=("a1 a1", "b2 b2")), Sanitizador())
    m.registrar_ata(reuniao(problemas=("só um",)), Sanitizador())
    assert len(m.vetores.linhas["atas_chunks"]["2026-10-14-gestao-a"]) == 2  # 1 problema + acomp.


def test_embedder_so_recebe_texto_mascarado_e_o_banco_guarda_o_original():
    emb = Espiao()
    m = memoria(emb=emb)
    r = reuniao(problemas=("A Acme pediu prazo, contato joao@acme.com",))
    m.registrar_ata(r, Sanitizador(["Acme"]))
    assert all("Acme" not in t and "joao@" not in t for t in emb.enviados)
    guardado = [i.texto for i in m.vetores.linhas["atas_chunks"][r.reuniao_id]]
    assert "A Acme pediu prazo, contato joao@acme.com" in guardado


CFG = Config(frozenset({"diretoria: pessoas"}), frozenset({"tipo: acao"}), frozenset({"Ana"}))


def plano_com(mem, r, ata="# ata"):
    llm = FakeLLM([{"acoes": [acao()]}])
    p = gerar_plano(r, ata, None, CFG, 12, llm, Sanitizador(), "", mem)
    return p, llm.chamadas[0]["prompt"]


def test_plano_marca_recorrencia_e_duplicata():
    mem = memoria()
    anterior = reuniao("Gestão A", 7)
    mem.registrar_ata(anterior, Sanitizador())
    p1, _ = plano_com(None, anterior)
    mem.registrar_issues(p1.model_copy(update={"reuniao_id": anterior.reuniao_id}), Sanitizador())

    atual = reuniao("Gestão B", 14)
    p, prompt = plano_com(mem, atual)
    assert p.recorrencias == {"p1": 1} and "<historico>" in prompt
    dup = p.possiveis_duplicatas["a1"]
    assert dup.reuniao_id == anterior.reuniao_id and dup.acao_id == "a1" and dup.similaridade > LIM
    assert p.avisos == [] and p.status == "rascunho"


def test_plano_sem_memoria_fica_limpo():
    p, prompt = plano_com(None, reuniao())
    assert (p.recorrencias, p.possiveis_duplicatas, p.avisos) == ({}, {}, [])
    assert "<historico>" not in prompt


class Quebrada:
    def substituir(self, *a):
        raise ConnectionError("banco fora")

    buscar = substituir


def test_memoria_fora_do_ar_nao_derruba_o_plano():
    p, prompt = plano_com(memoria(Quebrada()), reuniao())
    assert p.acoes[0].id == "a1" and p.possiveis_duplicatas == {}
    assert len(p.avisos) == 1 and "banco fora" in p.avisos[0]


PG = os.environ.get("TEST_PGVECTOR_URL")


@pytest.mark.skipif(not PG, reason="defina TEST_PGVECTOR_URL (Postgres com pgvector)")
def test_pgvector_substitui_e_busca_por_similaridade():
    v = PgVetores(PG, 8)
    emb = FakeLLM().embed(["alpha", "beta", "gamma"])
    r1 = [Item("p1", "T1", "alpha", emb[0]), Item("p2", "T2", "beta", emb[1])]
    v.substituir("atas_chunks", "t-r1", r1)
    v.substituir("atas_chunks", "t-r1", r1)  # reindexar não duplica
    v.substituir("atas_chunks", "t-r2", [Item("p1", "T3", "gamma", emb[2])])

    achados = v.buscar("atas_chunks", emb[0], 5, excluir="t-r2")
    assert [a.ref for a in achados] == ["p1", "p2"]
    assert achados[0].similaridade == pytest.approx(1) and achados[0].texto == "alpha"
    assert achados[1].similaridade < achados[0].similaridade

    v.substituir("atas_chunks", "t-r1", [])
    assert [a.reuniao_id for a in v.buscar("atas_chunks", emb[0], 5, excluir="x")] == ["t-r2"]
