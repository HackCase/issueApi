FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY collector ./collector
# editável: o núcleo localiza config/ e prompts/ relativo à raiz do repo
RUN pip install --no-cache-dir -e . -r collector/requirements.txt

COPY config ./config
COPY prompts ./prompts

# padrão: API. O coletor roda com `docker compose run --rm collector`
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
