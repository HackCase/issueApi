import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import pool
from .rotas import issues, pulls


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="GitHub Dashboard API", lifespan=lifespan)

# CORS_ORIGINS: lista separada por virgula; o padrao serve para desenvolvimento
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(issues.router, prefix="/api/issues", tags=["issues"])
app.include_router(pulls.router, prefix="/api/pulls", tags=["pulls"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
