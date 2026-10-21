import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .pipeline.ata import AtaInvalida, EntradaInsuficiente
from .rotas import reunioes

app = FastAPI(title="Núcleo de IA — Atas → Issues")
app.include_router(reunioes.router)


def _erro(status: int, erro: str, detalhe) -> JSONResponse:
    return JSONResponse({"erro": erro, "detalhe": str(detalhe)}, status_code=status)


@app.exception_handler(RequestValidationError)
async def _validacao(_: Request, e: RequestValidationError):
    return _erro(422, "entrada_invalida", e.errors())


@app.exception_handler(HTTPException)
async def _http(_: Request, e: HTTPException):
    return _erro(e.status_code, "erro_http", e.detail)


@app.exception_handler(EntradaInsuficiente)
async def _insuficiente(_: Request, e: EntradaInsuficiente):
    return _erro(422, "entrada_insuficiente", e)


@app.exception_handler(AtaInvalida)
async def _ata_invalida(_: Request, e: AtaInvalida):
    return _erro(502, "ata_invalida", e)


@app.exception_handler(httpx.HTTPError)
async def _upstream(_: Request, e: httpx.HTTPError):
    return _erro(502, "falha_externa", e)


@app.get("/health")
def health():
    return {"status": "ok"}
