import json
from pathlib import Path

import jsonschema
import pytest
import yaml

SCHEMA = json.loads((Path(__file__).parent / "issue.schema.json").read_text())

EXEMPLO = yaml.safe_load("""
schema_version: 1
reuniao_id: "2026-10-14-gestao-semanal"
acao_id: "a1"
title: "Padronizar template de onboarding de membros"
body: |
  ## Contexto
  x
labels: ["diretoria: pessoas", "tipo: acao"]
assignees: []
project_fields: {prioridade: alta, severidade: media, estimativa: 3, prazo: "2026-10-30"}
source: {ata_path: "docs/atas/2026-10-14-gestao-semanal.md", problema_id: p1}
""")


def test_exemplo_valido():
    jsonschema.validate(EXEMPLO, SCHEMA)
    jsonschema.validate(
        {**EXEMPLO, "project_fields": {**EXEMPLO["project_fields"], "prazo": None}}, SCHEMA
    )


@pytest.mark.parametrize(
    "mut",
    [
        {"extra": 1},
        {"schema_version": 2},
        {
            "project_fields": {
                "prioridade": "alta",
                "severidade": "media",
                "estimativa": 4,
                "prazo": None,
            }
        },
    ],
)
def test_exemplo_invalido(mut):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**EXEMPLO, **mut}, SCHEMA)
