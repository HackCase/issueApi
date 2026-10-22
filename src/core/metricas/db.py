from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..erros import ErroApi
from ..settings import get_settings


@lru_cache
def _pool() -> ConnectionPool:
    url = get_settings().database_url
    if not url:
        raise ErroApi(503, "sem_banco", "DATABASE_URL não configurada: métricas indisponíveis")
    return ConnectionPool(url, kwargs={"row_factory": dict_row}, open=True)


def todos(sql: str, params=None) -> list[dict]:
    with _pool().connection() as conn:
        return conn.execute(sql, params).fetchall()


def um(sql: str) -> dict:
    with _pool().connection() as conn:
        return conn.execute(sql).fetchone()


def fechar() -> None:
    if _pool.cache_info().currsize:
        _pool().close()
        _pool.cache_clear()
