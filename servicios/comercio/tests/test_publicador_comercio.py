from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comercio import publicador
from tukit_comercio.modelos import Base
from tukit_comercio.repositorios.pedidos import BANDEJA, RepoPedidos
from tukit_comun.http import fijar_correlacion, reset_correlacion
from tukit_comun.publicador import vaciar


class _Destino:
    def __init__(self) -> None:
        self.publicados: list = []

    async def publicar(self, evento) -> None:
        self.publicados.append(evento)


async def test_publica_el_pedido_pagado_con_su_origen_y_lo_marca():
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with motor.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)
        pedido = SimpleNamespace(id=uuid.uuid4(), usuario_id=uuid.uuid4(), total=45_000)
        token = fijar_correlacion("corr-pago")
        try:
            async with motor.begin() as conexion:
                await RepoPedidos(conexion).encolar_pedido_pagado(pedido)
        finally:
            reset_correlacion(token)
        destino = _Destino()

        assert await vaciar(motor, destino, origen="comercio") == 1

        [evento] = destino.publicados
        assert (evento.origen, evento.tipo, evento.agregado_id) == ("comercio", "pedido_pagado", pedido.id)
        assert evento.carga["usuario_id"] == str(pedido.usuario_id)
        assert evento.correlacion_id == "corr-pago"
        async with motor.connect() as conexion:
            assert await conexion.scalar(select(BANDEJA.c.publicado_en)) is not None
    finally:
        await motor.dispose()


def test_sin_rabbitmq_url_no_arranca(monkeypatch, capsys):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)

    assert publicador.main([]) == 2
    assert "falta RABBITMQ_URL" in capsys.readouterr().out
