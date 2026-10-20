FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /tmp/backend-req.txt
COPY collector/requirements.txt /tmp/collector-req.txt
RUN pip install --no-cache-dir -r /tmp/backend-req.txt -r /tmp/collector-req.txt

COPY backend ./backend
COPY collector ./collector

# padrao: API. O coletor roda com `docker compose run --rm collector`
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
