from typing import TypeVar

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from .schemas import MeetingInput
from .settings import Settings

T = TypeVar("T", bound=BaseModel)


class ReuniaoRegistro(BaseModel):
    reuniao: MeetingInput
    ata_path: str
    ata_md: str
    sessao_id: str | None = None


class MemoryStore:
    """Sem DATABASE_URL (dev/testes): estado só vive no processo."""

    def __init__(self):
        self.docs: dict[tuple[str, str], dict] = {}

    def get(self, kind: str, id: str) -> dict | None:
        return self.docs.get((kind, id))

    def put(self, kind: str, id: str, data: dict) -> None:
        self.docs[(kind, id)] = data


class PgStore:
    """Documentos JSON em uma tabela só: (kind, id) -> data."""

    def __init__(self, url: str):
        self.url = url
        self._pronto = False

    def _conn(self):
        conn = psycopg.connect(self.url)
        if not self._pronto:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS core_docs (
                     kind TEXT NOT NULL, id TEXT NOT NULL, data JSONB NOT NULL,
                     updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                     PRIMARY KEY (kind, id))"""
            )
            conn.commit()
            self._pronto = True
        return conn

    def get(self, kind: str, id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT data FROM core_docs WHERE kind=%s AND id=%s", (kind, id))
            row = row.fetchone()
            return row[0] if row else None

    def put(self, kind: str, id: str, data: dict) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO core_docs (kind, id, data) VALUES (%s, %s, %s)
                   ON CONFLICT (kind, id) DO UPDATE SET data = EXCLUDED.data, updated_at = now()""",
                (kind, id, Jsonb(data)),
            )


def build_store(s: Settings):
    return PgStore(s.database_url) if s.database_url else MemoryStore()


def obter(store, kind: str, id: str, modelo: type[T]) -> T | None:
    d = store.get(kind, id)
    return modelo.model_validate(d) if d is not None else None


def salvar(store, kind: str, id: str, obj: BaseModel) -> None:
    store.put(kind, id, obj.model_dump(mode="json"))
