# issueApi

Coleta issues/PRs de uma org do GitHub para o Postgres e expõe métricas via API (FastAPI).
Faz parte do projeto Atas → Plano de Ação → Issues (ver `sdd/spec.md`).

## Rodar

```bash
cp .env.example .env            # preencher GITHUB_TOKEN e GITHUB_ORG
docker compose up -d            # db + API única em http://localhost:8000/docs
docker compose run --rm collector   # coleta (incremental)
```

## Criar issues a partir de YAML

```bash
pip install -r requirements.txt
python create_issues.py issues.yaml
```

## Núcleo de IA (`src/core`)

```bash
pip install -e ".[dev]"
ruff check src tests && pytest
uvicorn core.main:app --reload     # API única: atas (/reunioes...) e métricas (/issues/*, /pulls/*)
```
