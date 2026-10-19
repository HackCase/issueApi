from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .rotas import issues, pulls

app = FastAPI(title="GitHub Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(issues.router, prefix="/api/issues", tags=["issues"])
app.include_router(pulls.router, prefix="/api/pulls", tags=["pulls"])


@app.get("/api/health")
def health():
    return {"status": "ok"}