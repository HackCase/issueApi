from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .erros import ErroApi
from .guardrails.validators import PlanoInvalido
from .metricas import db, pulls
from .metricas import issues as metricas_issues
from .pipeline.ata import AtaInvalida, EntradaInsuficiente
from .pipeline.comum import SaidaInvalida
from .rotas import grill, issues, plano, reunioes
from .settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    db.fechar()


app = FastAPI(title="Mega Jr. — Atas → Issues + métricas", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)
app.include_router(reunioes.router)
app.include_router(grill.router)
app.include_router(plano.router)
app.include_router(issues.router)
app.include_router(metricas_issues.router, prefix="/issues", tags=["métricas"])
app.include_router(pulls.router, prefix="/pulls", tags=["métricas"])


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


@app.exception_handler(ErroApi)
async def _erro_api(_: Request, e: ErroApi):
    return _erro(e.status, e.erro, e.detalhe)


@app.exception_handler(PlanoInvalido)
async def _plano_invalido(_: Request, e: PlanoInvalido):
    return _erro(422, "plano_invalido", e)


@app.exception_handler(SaidaInvalida)
async def _saida_invalida(_: Request, e: SaidaInvalida):
    return _erro(502, "saida_invalida", e)


@app.exception_handler(httpx.HTTPError)
async def _upstream(_: Request, e: httpx.HTTPError):
    return _erro(502, "falha_externa", e)


@app.get("/health")
def health():
    return {"status": "ok"}
