"""Pruebas del drenador de bandeja compartido (ADR 0022).

La logica de drenar una `bandeja_salida` estaba TRIPLICADA (repartidor de
operacion, poller de identidad, poller de inteligencia): reflejar la tabla,
`SELECT ... FOR UPDATE SKIP LOCKED` sobre los no-publicados, iterar, marcar
publicado o subir intentos. `drenar` la unifica; cada llamador solo aporta su
`manejar(conexion, fila) -> Resultado`.

Se fija aqui:

- `HECHO` marca el evento publicado y cuenta.
- `OMITIR` marca publicado pero NO cuenta (tipo que no me toca).
- `REINTENTAR` sube intentos y NO marca publicado (se reintenta la proxima pasada).
- El `correlacion_id` de la carga se re-vincula antes de llamar a `manejar`
  (cierra el hueco de §A.6: un evento drenado recupera el hilo de su peticion).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from sqlalchemy import MetaData, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bandeja import Resultado, bandeja_reflejada, drenar
from tukit_comun.bd import MotorServicio
from tukit_comun.http import id_de_correlacion

# La misma tabla que reflejan los drenadores reales; se materializa para el test.
BANDEJA = bandeja_reflejada(MetaData())


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def _sembrar(motor: MotorServicio, filas: list[dict[str, Any]]) -> None:
    async with motor.engine.begin() as conexion:
        for i, fila in enumerate(filas, start=1):
            await conexion.execute(insert(BANDEJA).values(id=i, intentos=0, **fila))


async def _pendientes(motor: MotorServicio) -> list[Any]:
    async with motor.engine.connect() as conexion:
        filas = await conexion.execute(select(BANDEJA).where(BANDEJA.c.publicado_en.is_(None)))
        return list(filas)


async def test_hecho_publica_y_cuenta(motor):
    await _sembrar(motor, [{"tipo": "kits_publicados", "carga": {}}])

    async def manejar(conexion, fila) -> Resultado:
        return Resultado.HECHO

    n = await drenar(motor.engine, manejar)
    assert n == 1
    assert await _pendientes(motor) == []


async def test_omitir_publica_pero_no_cuenta(motor):
    await _sembrar(motor, [{"tipo": "desconocido", "carga": {}}])

    async def manejar(conexion, fila) -> Resultado:
        return Resultado.OMITIR

    n = await drenar(motor.engine, manejar)
    assert n == 0
    # Publicado igual: un tipo que no me toca no se reprocesa cada pasada.
    assert await _pendientes(motor) == []


async def test_reintentar_sube_intentos_y_deja_pendiente(motor):
    await _sembrar(motor, [{"tipo": "kits_publicados", "carga": {}}])

    async def manejar(conexion, fila) -> Resultado:
        return Resultado.REINTENTAR

    n = await drenar(motor.engine, manejar)
    assert n == 0
    pend = await _pendientes(motor)
    assert len(pend) == 1
    assert pend[0].intentos == 1


async def test_filtra_por_tipo(motor):
    await _sembrar(
        motor,
        [
            {"tipo": "lista_verificada", "carga": {}},
            {"tipo": "otro", "carga": {}},
        ],
    )
    vistos: list[str] = []

    async def manejar(conexion, fila) -> Resultado:
        vistos.append(fila.tipo)
        return Resultado.HECHO

    n = await drenar(motor.engine, manejar, tipo="lista_verificada")
    assert n == 1
    assert vistos == ["lista_verificada"]  # el 'otro' ni se toco


async def test_revincula_la_correlacion_desde_la_carga(motor):
    await _sembrar(motor, [{"tipo": "kits_publicados", "carga": {"correlacion_id": "abc123"}}])
    visto: list[str | None] = []

    async def manejar(conexion, fila) -> Resultado:
        visto.append(id_de_correlacion())
        return Resultado.HECHO

    await drenar(motor.engine, manejar)
    assert visto == ["abc123"]


async def test_con_correlacion_estampa_y_cierra_el_ciclo():
    # El otro extremo del hilo: el productor estampa el id de la peticion en la
    # carga, y el drenador lo re-vincula al consumir (probado arriba). Con id en
    # contexto se anexa; sin id (un poller) no se inventa nada.
    from tukit_comun.bandeja import con_correlacion
    from tukit_comun.http import fijar_correlacion, reset_correlacion

    token = fijar_correlacion("req-42")
    try:
        assert con_correlacion({"x": 1}) == {"x": 1, "correlacion_id": "req-42"}
    finally:
        reset_correlacion(token)
    assert con_correlacion({"x": 1}) == {"x": 1}  # sin peticion, sin id inventado


async def test_sink_recibe_solo_los_hecho(motor):
    # El sink (broker) es ADITIVO al manejar: solo se le pasan los eventos que
    # el manejar dio por HECHO —no los OMITIR ni los REINTENTAR—, y el outbox
    # sigue marcando/publicando igual (la fuente de verdad no cambia, ADR 0022).
    await _sembrar(
        motor,
        [
            {"tipo": "kits_publicados", "carga": {"a": 1}},  # HECHO
            {"tipo": "desconocido", "carga": {}},  # OMITIR
        ],
    )
    publicados: list[str] = []

    class SinkFalso:
        async def publicar(self, fila) -> None:
            publicados.append(fila.tipo)

    async def manejar(conexion, fila) -> Resultado:
        return Resultado.HECHO if fila.tipo == "kits_publicados" else Resultado.OMITIR

    n = await drenar(motor.engine, manejar, sink=SinkFalso())
    assert n == 1
    assert publicados == ["kits_publicados"]  # el OMITIR no fue al broker
