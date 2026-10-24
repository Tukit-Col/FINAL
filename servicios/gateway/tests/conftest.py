from __future__ import annotations

from collections.abc import Iterator

import pytest
from tukit_comun.cache import usar_cliente


@pytest.fixture(autouse=True)
def _sin_redis(monkeypatch) -> Iterator[None]:
    """Cada prueba con un cliente nuevo y sin Redis: el limite cuenta en una
    memoria que no arrastra lo que conto la prueba anterior, y una `REDIS_URL`
    exportada en la terminal no mete Redis en las pruebas unitarias."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)
