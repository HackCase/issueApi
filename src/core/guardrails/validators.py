from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..schemas import MeetingInput, PlanoAcao


@dataclass(frozen=True)
class Config:
    diretorias: frozenset[str]
    tipos: frozenset[str]
    membros: frozenset[str]
    logins: dict[str, str] = field(default_factory=dict)  # nome -> login do GitHub

    @property
    def labels_permitidas(self) -> frozenset[str]:
        return self.diretorias | self.tipos


class PlanoInvalido(ValueError):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def carregar_config(config_dir: Path) -> Config:
    labels = yaml.safe_load((config_dir / "labels.yaml").read_text(encoding="utf-8")) or {}
    membros = yaml.safe_load((config_dir / "membros.yaml").read_text(encoding="utf-8")) or {}
    return Config(
        diretorias=frozenset(labels.get("diretorias") or []),
        tipos=frozenset(labels.get("tipos") or []),
        membros=frozenset(m["nome"] for m in membros.get("membros") or []),
        logins={m["nome"]: m["github"] for m in membros.get("membros") or [] if m.get("github")},
    )


def validar_plano(
    plano: PlanoAcao, reuniao: MeetingInput, cfg: Config, max_acoes: int = 12
) -> list[str]:
    """Devolve a lista de erros (vazia = válido). Regras da seção 5.4 do SPEC."""
    erros: list[str] = []
    problemas = set(reuniao.problema_ids)

    if not 1 <= len(plano.acoes) <= max_acoes:
        erros.append(f"número de ações deve estar entre 1 e {max_acoes}: {len(plano.acoes)}")

    vistos: set[str] = set()
    ids = [a.id for a in plano.acoes]
    if len(ids) != len(set(ids)):
        erros.append("ids de ação duplicados")
    for a in plano.acoes:
        fora = [lb for lb in a.labels if lb not in cfg.labels_permitidas]
        if fora:
            erros.append(f"{a.id}: labels fora da allowlist: {fora}")
        n_dir = sum(lb in cfg.diretorias for lb in a.labels)
        if n_dir != 1:
            erros.append(f"{a.id}: precisa de exatamente 1 label de diretoria, tem {n_dir}")
        if a.problema_origem not in problemas:
            erros.append(f"{a.id}: problema_origem inexistente: {a.problema_origem}")
        if a.responsavel is not None and a.responsavel not in cfg.membros:
            erros.append(f"{a.id}: responsável fora de membros.yaml: {a.responsavel}")
        if a.prazo is not None and a.prazo < reuniao.data:
            erros.append(f"{a.id}: prazo {a.prazo} anterior à data da reunião {reuniao.data}")
        chave = a.titulo.strip().casefold()
        if chave in vistos:
            erros.append(f"{a.id}: título duplicado: {a.titulo}")
        vistos.add(chave)

    for pid in plano.justificativas:
        if pid not in problemas:
            erros.append(f"justificativa para problema inexistente: {pid}")
    cobertos = {a.problema_origem for a in plano.acoes} | set(plano.justificativas)
    for pid in sorted(problemas - cobertos):
        erros.append(f"problema {pid} sem ação nem justificativa")

    return erros


def exigir_plano_valido(
    plano: PlanoAcao, reuniao: MeetingInput, cfg: Config, max_acoes: int = 12
) -> None:
    if erros := validar_plano(plano, reuniao, cfg, max_acoes):
        raise PlanoInvalido(erros)
