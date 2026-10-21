import os

import pytest

from core.settings import Settings
from core.store import MemoryStore, PgStore, build_store

PG = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.parametrize(
    "fabrica",
    [
        MemoryStore,
        pytest.param(
            lambda: PgStore(PG), marks=pytest.mark.skipif(not PG, reason="TEST_DATABASE_URL")
        ),
    ],
)
def test_put_get_sobrescreve(fabrica):
    st = fabrica()
    assert st.get("k", "zz-inexistente") is None
    st.put("k", "id1", {"a": 1, "b": ["é"]})
    st.put("k", "id1", {"a": 2})
    assert st.get("k", "id1") == {"a": 2}


def test_build_store_por_settings():
    assert isinstance(build_store(Settings(database_url="")), MemoryStore)
    assert isinstance(build_store(Settings(database_url="postgresql://x")), PgStore)
