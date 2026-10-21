import yaml

from ..erros import ErroApi
from ..guardrails.validators import Config, exigir_plano_valido
from ..schemas import Acao, MeetingInput, PlanoAcao

SCHEMA_VERSION = 1
SECAO_DECISOES = "## Decisões e próximos passos"


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, v: str):
    # texto multilinha em bloco literal (`|`), como no exemplo da seção 5.5
    return dumper.represent_scalar("tag:yaml.org,2002:str", v, style="|" if "\n" in v else None)


_Dumper.add_representer(str, _str)


def caminho_yaml(reuniao_id: str, acao_id: str) -> str:
    return f"out/issues/{reuniao_id}/{acao_id}.yml"


def _body(a: Acao, ata_path: str) -> str:
    criterios = "\n".join(f"- [ ] {c}" for c in a.criterios_aceite)
    return (
        f"## Contexto\n{a.descricao.strip()}\n\n"
        f"## Critérios de aceite\n{criterios}\n\n"
        f"## Origem\nProblema {a.problema_origem} · Ata: {ata_path}\n"
    )


def render(plano: PlanoAcao, ata_path: str, logins: dict[str, str] | None = None) -> dict[str, str]:
    """Função pura e determinística: `acao_id -> texto YAML` (contrato da seção 5.5).

    `logins` mapeia o nome do responsável para o login do GitHub (membros.yaml).
    """
    logins = logins or {}
    saida = {}
    for a in plano.acoes:
        doc = {
            "schema_version": SCHEMA_VERSION,
            "reuniao_id": plano.reuniao_id,
            "acao_id": a.id,
            "title": a.titulo,
            "body": _body(a, ata_path),
            "labels": list(a.labels),
            "assignees": [logins[a.responsavel]] if a.responsavel in logins else [],
            "project_fields": {
                "prioridade": a.prioridade,
                "severidade": a.severidade,
                "estimativa": a.estimativa,
                "prazo": a.prazo.isoformat() if a.prazo else None,
            },
            "source": {"ata_path": ata_path, "problema_id": a.problema_origem},
        }
        saida[a.id] = yaml.dump(
            doc, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=1000
        )
    return saida


def gerar_issues(
    plano: PlanoAcao, reuniao: MeetingInput, ata_path: str, cfg: Config, max_acoes: int
) -> dict[str, str]:
    """Só com plano aprovado; revalida tudo (5.4) antes de renderizar. Nunca devolve parcial."""
    if plano.status != "aprovado":
        raise ErroApi(409, "plano_nao_aprovado", "aprove o plano antes de gerar as issues")
    exigir_plano_valido(plano, reuniao, cfg, max_acoes)
    return render(plano, ata_path, cfg.logins)


def secao_decisoes(plano: PlanoAcao) -> str:
    linhas = [
        f"- **{a.id}** — {a.titulo} (prioridade {a.prioridade})"
        f" → `{caminho_yaml(plano.reuniao_id, a.id)}`"
        for a in plano.acoes
    ]
    linhas += [f"- Sem ação para {p}: {j}" for p, j in sorted(plano.justificativas.items())]
    return f"{SECAO_DECISOES}\n\n" + "\n".join(linhas) + "\n"


def atualizar_ata(ata_md: str, plano: PlanoAcao) -> str:
    """Troca a seção final "Decisões e próximos passos" (idempotente)."""
    i = ata_md.find(SECAO_DECISOES)
    base = ata_md[:i].rstrip() if i >= 0 else ata_md.rstrip()
    return f"{base}\n\n{secao_decisoes(plano)}"
