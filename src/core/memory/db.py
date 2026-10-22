import psycopg

TABELAS = ("atas_chunks", "issues_hist")


def conectar(url: str, dim: int) -> psycopg.Connection:
    """Conexão com o schema da memória garantido (idempotente)."""
    conn = psycopg.connect(url)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for t in TABELAS:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {t} (
                  reuniao_id TEXT NOT NULL,
                  ref        TEXT NOT NULL,
                  titulo     TEXT NOT NULL,
                  texto      TEXT NOT NULL,
                  embedding  vector({int(dim)}) NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  PRIMARY KEY (reuniao_id, ref))"""
        )
    # ponytail: sem índice HNSW/IVFFlat (busca exata); criar quando passar de ~10k linhas
    conn.commit()
    return conn
