from fastapi import FastAPI

app = FastAPI(title="Núcleo de IA — Atas → Issues")


@app.get("/health")
def health():
    return {"status": "ok"}
