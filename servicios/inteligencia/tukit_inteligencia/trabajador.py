"""Trabajador durable del pipeline: la cola, no una tarea efimera.

Decisiones:
- `crear` escribe el trabajo `encolado` de forma transaccional y este proceso lo toma con
  `SELECT ... FOR UPDATE SKIP LOCKED` (el mecanismo del outbox), lo marca `procesando` en la misma
  transaccion y ejecuta `procesar`. Una caida de proceso no pierde trabajo y varias replicas drenan
  la misma cola sin coordinarse.
- `--retomar-colgados`, y el bucle cada cierto numero de vueltas, amplia el claim a `procesando`
  para retomar un trabajo que quedo a medias; `procesar` es idempotente en el claim (borra ITEM y KIT
  y reejecuta), asi que no duplica.

Uso:  python -m tukit_inteligencia.trabajador [--seguir] [--retomar-colgados]
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from tukit_comun.bandeja import Resultado
from tukit_comun.broker import url_broker
from tukit_comun.consumidor import Consumidor, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.metricas import contar_trabajo_publicado
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente
from tukit_comun.topologia import TRABAJOS

from . import importaciones
from .modelos import EstadoTrabajo
from .remoto import ClienteCatalogo
from .trabajos import TRABAJO, ahora, procesar

_RECLAMABLES_NORMAL = (EstadoTrabajo.ENCOLADO.value,)
_RECLAMABLES_CON_COLGADOS = (EstadoTrabajo.ENCOLADO.value, EstadoTrabajo.PROCESANDO.value)
_COLGADO_DESDE = timedelta(minutes=15)
_TERMINALES_EXITOSOS = frozenset({EstadoTrabajo.PUBLICADO.value, EstadoTrabajo.ESPERA_REVISION.value})
_AVISO_PERDIDO = timedelta(minutes=1)
_VUELTAS_POR_BARRIDO = 12


async def _reclamar(
    motor: Any, *, limite: int, estados: tuple[str, ...], encolado_antes_de: datetime | None = None
) -> list[uuid.UUID]:
    procesando = EstadoTrabajo.PROCESANDO.value
    reclamables = TRABAJO.c.estado.in_([e for e in estados if e != procesando])
    if encolado_antes_de is not None:
        reclamables = and_(reclamables, TRABAJO.c.actualizado_en < encolado_antes_de)
    if procesando in estados:
        colgado = and_(TRABAJO.c.estado == procesando, TRABAJO.c.actualizado_en < ahora() - _COLGADO_DESDE)
        reclamables = or_(reclamables, colgado)
    async with motor.engine.begin() as conexion:
        filas = list(
            await conexion.execute(
                select(TRABAJO.c.id)
                .where(reclamables)
                .order_by(TRABAJO.c.creado_en)
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
        )
        ids = [f.id for f in filas]
        if ids:
            await conexion.execute(
                update(TRABAJO).where(TRABAJO.c.id.in_(ids)).values(estado=EstadoTrabajo.PROCESANDO.value)
            )
        return ids


async def pasada(
    motor: Any,
    *,
    catalogo: ClienteCatalogo | None = None,
    limite: int = 10,
    retomar_colgados: bool = False,
    encolado_antes_de: datetime | None = None,
) -> int:
    estados = _RECLAMABLES_CON_COLGADOS if retomar_colgados else _RECLAMABLES_NORMAL
    ids = await _reclamar(motor, limite=limite, estados=estados, encolado_antes_de=encolado_antes_de)
    for trabajo_id in ids:
        await _procesar_y_contar(motor, trabajo_id, catalogo)
    return len(ids)


async def _procesar_y_contar(motor: Any, trabajo_id: uuid.UUID, catalogo: ClienteCatalogo | None) -> None:
    await procesar(motor, trabajo_id, catalogo=catalogo)
    async with motor.engine.begin() as conexion:
        estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    if estado in _TERMINALES_EXITOSOS:
        contar_trabajo_publicado()


async def _reclamar_uno(motor: Any, trabajo_id: uuid.UUID) -> bool:
    async with motor.engine.begin() as conexion:
        resultado = await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id, TRABAJO.c.estado == EstadoTrabajo.ENCOLADO.value)
            .values(estado=EstadoTrabajo.PROCESANDO.value)
        )
    return bool(resultado.rowcount == 1)


async def atender_aviso(motor: Any, evento: Evento, *, catalogo: ClienteCatalogo | None = None) -> Resultado:
    if evento.tipo != "trabajo_encolado":
        return Resultado.OMITIR
    try:
        trabajo_id = uuid.UUID(str((evento.carga or {}).get("trabajo_id") or evento.agregado_id))
    except (ValueError, TypeError):
        return Resultado.OMITIR
    if not await _reclamar_uno(motor, trabajo_id):
        return Resultado.OMITIR
    await _procesar_y_contar(motor, trabajo_id, catalogo)
    return Resultado.HECHO


async def barrer(motor: Any, *, catalogo: ClienteCatalogo | None = None) -> int:
    return await pasada(
        motor, catalogo=catalogo, retomar_colgados=True, encolado_antes_de=ahora() - _AVISO_PERDIDO
    )


async def correr_una_vez(*, motor: Any = None, catalogo: Any = None) -> int:
    from tukit_comun.bd import crear_motor

    propio = motor is None
    motor = motor or crear_motor("inteligencia")
    catalogo = catalogo or ClienteCatalogo()
    try:
        hechos = await pasada(motor, catalogo=catalogo, retomar_colgados=True)
        importadas = await importaciones.reintentar_pendientes(motor, catalogo=catalogo)
        if importadas:
            print(f"[trabajador] listas importadas: {importadas}")
        return hechos
    finally:
        if propio:
            await motor.cerrar()


async def correr_en_bucle(
    intervalo: float,
    *,
    dormir: Callable[[float], Awaitable[None]] | None = None,
    con_avisos: bool = False,
    motor: Any = None,
    catalogo: Any = None,
) -> None:
    from tukit_comun.bd import crear_motor

    propio = motor is None
    motor = motor or crear_motor("inteligencia")
    catalogo = catalogo or ClienteCatalogo()
    vuelta = 0

    async def _vuelta() -> None:
        nonlocal vuelta
        vuelta += 1
        if con_avisos:
            hechos = await barrer(motor, catalogo=catalogo) if vuelta % _VUELTAS_POR_BARRIDO == 1 else 0
        else:
            hechos = await pasada(
                motor, catalogo=catalogo, retomar_colgados=(vuelta % _VUELTAS_POR_BARRIDO == 0)
            )
        if hechos:
            print(f"[trabajador] trabajos procesados: {hechos}")
        importadas = await importaciones.reintentar_pendientes(motor, catalogo=catalogo)
        if importadas:
            print(f"[trabajador] listas importadas: {importadas}")

    try:
        await bucle_resiliente(
            _vuelta, intervalo=intervalo, proceso="inteligencia-trabajador", dormir=dormir or asyncio.sleep
        )
    finally:
        if propio:
            await motor.cerrar()


async def escuchar_cola(
    url: str,
    *,
    seguir: bool,
    intervalo: float = 5.0,
    dormir: Callable[[float], Awaitable[None]] | None = None,
) -> int:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("inteligencia")
    catalogo = ClienteCatalogo()
    consumidor = Consumidor(cola=TRABAJOS, manejar=functools.partial(atender_aviso, motor, catalogo=catalogo))
    try:
        if not seguir:
            atendidos = await consumir(
                url, consumidor, seguir=False, proceso="inteligencia-trabajador", prefetch=1
            )
            return atendidos + await barrer(motor, catalogo=catalogo)
        async with asyncio.TaskGroup() as grupo:
            grupo.create_task(
                consumir(
                    url,
                    consumidor,
                    seguir=True,
                    proceso="inteligencia-trabajador",
                    intervalo=intervalo,
                    prefetch=1,
                    dormir=dormir or asyncio.sleep,
                )
            )
            grupo.create_task(correr_en_bucle(intervalo, dormir=dormir, con_avisos=True))
        return 0
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena la cola de trabajos de Inteligencia y corre el pipeline (ADR 0024)."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("inteligencia-trabajador")

    url = url_broker()
    if url:
        hechos = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
        if not argumentos.seguir:
            print(f"[trabajador] trabajos procesados: {hechos}")
        return 0
    if argumentos.seguir:
        asyncio.run(correr_en_bucle(argumentos.intervalo))
    else:
        hechos = asyncio.run(correr_una_vez())
        print(f"[trabajador] trabajos procesados: {hechos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "atender_aviso",
    "barrer",
    "correr_en_bucle",
    "correr_una_vez",
    "escuchar_cola",
    "main",
    "pasada",
]
