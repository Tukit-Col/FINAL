from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from tukit_comun.cache import usar_cliente
from tukit_gateway.api import app


@pytest.fixture(autouse=True)
def _sin_redis(monkeypatch) -> Iterator[None]:
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)


@pytest.fixture(autouse=True)
async def _sin_cliente_compartido() -> AsyncIterator[None]:
    yield
    cliente = getattr(app.state, "cliente", None)
    if cliente is not None:
        await cliente.aclose()
        del app.state.cliente


@pytest.fixture()
def atras():
    from _ayudas_gateway import Atras

    falso = Atras()
    app.state.cliente = falso.cliente
    return falso


@pytest.fixture()
def redis():
    from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria

    motor = RedisEnMemoria()
    usar_cliente(cliente_en_memoria(motor))
    return motor
