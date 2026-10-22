from datetime import date

from core.guardrails.sanitize import Sanitizador, carregar_clientes
from core.schemas import MeetingInput


def test_mascara_dados_sensiveis():
    san = Sanitizador()
    t = (
        "Fale com ana.silva@exemplo.com.br ou (11) 98765-4321. "
        "CPF 123.456.789-09, CNPJ 12.345.678/0001-95."
    )
    out = san.mascarar(t)
    for bruto in ["ana.silva", "98765", "123.456", "12.345.678"]:
        assert bruto not in out
    assert all(f"[{t}_1]" in out for t in ["EMAIL", "TELEFONE", "CPF", "CNPJ"])


def test_reverte_o_que_mascarou():
    san = Sanitizador(["Acme Ltda"])
    t = "A Acme Ltda (acme ltda) escreveu para joao@acme.com, tel +55 11 91234-5678."
    out = san.mascarar(t)
    assert "Acme" not in out and "joao@" not in out
    assert san.reverter(out) == t.replace("acme ltda", "Acme Ltda")  # 1ª grafia vence


def test_mesmo_valor_mesmo_placeholder():
    san = Sanitizador()
    out = san.mascarar("a@x.com b@x.com a@x.com")
    assert out == "[EMAIL_1] [EMAIL_2] [EMAIL_1]"


def test_cliente_so_palavra_inteira_e_sem_regex_injetada():
    san = Sanitizador(["A.B", "Sol"])
    assert san.mascarar("Solar A.B AxB Sol") == "Solar [CLIENTE_1] AxB [CLIENTE_2]"


def test_texto_sem_dados_fica_igual():
    assert Sanitizador().mascarar("Reunião em 14/10/2026, 3 pendências, R$ 1500,00") == (
        "Reunião em 14/10/2026, 3 pendências, R$ 1500,00"
    )


def test_mascarar_reuniao_preserva_participantes():
    r = MeetingInput(
        titulo="t",
        data=date(2026, 10, 14),
        participantes=["Ana"],
        acompanhamento="a@b.com",
        problemas=["ligar 11 91234-5678"],
    )
    m = Sanitizador().mascarar_reuniao(r)
    assert (
        m.participantes == ["Ana"] and "@" not in m.acompanhamento and "9123" not in m.problemas[0]
    )
    assert r.acompanhamento == "a@b.com"  # original intacto


def test_carregar_clientes(tmp_path):
    assert carregar_clientes(tmp_path) == []
    (tmp_path / "clientes.yaml").write_text("clientes: [Acme]")
    assert carregar_clientes(tmp_path) == ["Acme"]


def test_cliente_dentro_de_email_nao_vaza_a_parte_local():
    out = Sanitizador(["Acme"]).mascarar("fale com joao@acme.com sobre a Acme")
    assert "joao" not in out and "@" not in out and "Acme" not in out
