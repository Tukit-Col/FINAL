from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from tukit_comun.cache import usar_cliente
from tukit_gateway.api import app


@pytest.fixture(autouse=True)
def _sin_redis(monkeypatch) -> Iterator[None]:
    """Cada prueba con un cliente nuevo y sin Redis: el limite cuenta en una
    memoria que no arrastra lo que conto la prueba anterior, y una `REDIS_URL`
    exportada en la terminal no mete Redis en las pruebas unitarias."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)


@pytest.fixture(autouse=True)
async def _sin_cliente_compartido() -> AsyncIterator[None]:
    """El cliente httpx compartido de la puerta nace en el primer uso y se ata
    al bucle de esa prueba; se cierra y se retira al terminar, para que la
    siguiente no herede conexiones de un bucle que ya no existe."""
    yield
    cliente = getattr(app.state, "cliente", None)
    if cliente is not None:
        await cliente.aclose()
        del app.state.cliente
