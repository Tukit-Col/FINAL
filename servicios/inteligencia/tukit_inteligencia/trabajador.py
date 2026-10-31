"""El trabajador durable del pipeline (ADR 0024): la cola, no una `asyncio.Task`.

`inteligencia.lanzar` ya no arranca una corrutina efimera en el proceso del
API. El trabajo se escribe `encolado` (transaccional, lo hace `crear`) y este
trabajador lo drena: toma un `encolado` con `SELECT … FOR UPDATE SKIP LOCKED`
—el mismo mecanismo del outbox (ADR 0022)—, lo marca `procesando` en la misma
transaccion (para que un segundo worker no lo tome) y ejecuta `procesar`.

**Que cierra:** el unico punto donde una caida de proceso perdia trabajo del
usuario. Si el API se reinicia con un trabajo en vuelo, la fila sigue en la base
y otro worker (o el reinicio) la retoma. `SKIP LOCKED` deja que N replicas
drenen la misma cola sin coordinacion.

    python -m tukit_inteligencia.trabajador           # una pasada
    python -m tukit_inteligencia.trabajador --seguir   # bucle

**Reanudar los colgados.** Un trabajo que quedo `procesando` (crash a mitad) no
lo toma la pasada normal —solo mira `encolado`—. `--retomar-colgados` (y el
bucle, cada cierto numero de vueltas) amplia el claim a `procesando` para que un
worker lo retome. `procesar` es idempotente en el claim (borra ITEM/KIT y
reejecuta), asi que retomar no duplica.

**Las listas que esperan al catalogo** (ADR 0040). Una subida que llego con el
catalogo caido deja su lista `pendiente` en `importacion_lista`; cada vuelta, y
cada pasada suelta, reintenta importarlas (`importaciones.reintentar_pendientes`).

**Con RabbitMQ** (`RABBITMQ_URL`, ADR 0046) no sondea los `encolado`: cada
trabajo que queda `encolado` deja un aviso `trabajo_encolado` en la bandeja, el
publicador lo lleva a la cola `inteligencia.trabajos` y el trabajador reclama
esa fila con un `UPDATE ... WHERE estado = 'encolado'`. Si no la reclama (otro
la tomo, se cancelo antes o ya termino), el aviso queda atendido, asi que uno
repetido no procesa dos veces. La tabla sigue siendo la cola: una vez por minuto
un barrido toma los `encolado` que llevan mas de `_AVISO_PERDIDO` sin moverse
(su aviso se perdio) y los colgados. Las listas pendientes se reintentan en cada
vuelta, como sin broker.

**Una caida no lo mata** (ADR 0041). El bucle corre sobre `bucle_resiliente`:
si Postgres no responde, espera y reintenta la vuelta con el mismo motor, que
reconecta solo (`pool_pre_ping`). Un trabajo que quedo `procesando` cuando se
cayo la base lo retoma la vuelta de colgados, pasado `_COLGADO_DESDE`. Un error
de programacion sigue terminando el proceso.
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
# Un `procesando` es colgado si lleva este tiempo sin cambiar. Sin el umbral, la
# vuelta de colgados (cada minuto) tomaba tambien el trabajo que el poller o un
# preview estaban armando en ese momento en su propio proceso: los dos lo
# armaban a la vez y uno terminaba "fallido". Un canonico tarda segundos y una
# lista con PDF unos minutos; quince no los alcanza y un crash real se retoma.
_COLGADO_DESDE = timedelta(minutes=15)
# Un trabajo "publicado" para la metrica es el que termino en un estado exitoso:
# publicado directo o a la espera de revision. `fallido` no cuenta.
_TERMINALES_EXITOSOS = frozenset({EstadoTrabajo.PUBLICADO.value, EstadoTrabajo.ESPERA_REVISION.value})
# Con RabbitMQ, un `encolado` que lleva este tiempo sin moverse perdio su aviso
# y lo toma el barrido. Mas corto, el barrido le ganaria al aviso que viene en
# camino (el publicador sondea su bandeja cada segundo).
_AVISO_PERDIDO = timedelta(minutes=1)
# Las vueltas que hay entre una mirada a los colgados y la siguiente: un minuto
# a 5 s. Con RabbitMQ, el barrido entero va con esa cadencia.
_VUELTAS_POR_BARRIDO = 12


async def _reclamar(
    motor: Any, *, limite: int, estados: tuple[str, ...], encolado_antes_de: datetime | None = None
) -> list[uuid.UUID]:
    """Toma hasta `limite` trabajos reclamables y los marca `procesando`, atomico.

    El `SELECT … FOR UPDATE SKIP LOCKED` bloquea las filas y el `UPDATE` a
    `procesando` en la MISMA transaccion las saca del conjunto reclamable antes
    de soltar el lock: dos workers concurrentes nunca toman el mismo trabajo (uno
    ve la fila ya `procesando` y el `.in_(estados)` no la trae). `procesar` es
    idempotente en el claim (ya venia `procesando`), asi que no re-transiciona.

    Con `encolado_antes_de`, solo toma los `encolado` que no se movieron desde
    entonces: el barrido con RabbitMQ deja los recientes a su aviso.
    """
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
    """Una pasada: procesa hasta `limite` trabajos reclamables. Devuelve cuantos.

    Con `retomar_colgados`, tambien reclama `procesando` (crash a mitad); sin el,
    solo `encolado`. Un fallo de un trabajo no tumba la pasada: `procesar` lo
    deja `fallido` con diagnostico (seccion 8) y devuelve, y el siguiente sigue.
    `encolado_antes_de` va a `_reclamar`.
    """
    estados = _RECLAMABLES_CON_COLGADOS if retomar_colgados else _RECLAMABLES_NORMAL
    ids = await _reclamar(motor, limite=limite, estados=estados, encolado_antes_de=encolado_antes_de)
    for trabajo_id in ids:
        await _procesar_y_contar(motor, trabajo_id, catalogo)
    return len(ids)


async def _procesar_y_contar(motor: Any, trabajo_id: uuid.UUID, catalogo: ClienteCatalogo | None) -> None:
    await procesar(motor, trabajo_id, catalogo=catalogo)
    # Metrica de dominio (ADR 0021): se cuenta el trabajo que termino en un
    # estado exitoso (publicado o en revision), no el que quedo `fallido`.
    # Se lee el estado ya persistido por `procesar`, no se infiere.
    async with motor.engine.begin() as conexion:
        estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    if estado in _TERMINALES_EXITOSOS:
        contar_trabajo_publicado()


async def _reclamar_uno(motor: Any, trabajo_id: uuid.UUID) -> bool:
    """Toma el trabajo de un aviso si sigue `encolado`. `False` si no.

    El `UPDATE` con la condicion de estado es atomico: entre dos trabajadores,
    o entre el aviso y el barrido, solo uno lo pasa a `procesando`."""
    async with motor.engine.begin() as conexion:
        resultado = await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id, TRABAJO.c.estado == EstadoTrabajo.ENCOLADO.value)
            .values(estado=EstadoTrabajo.PROCESANDO.value)
        )
    return bool(resultado.rowcount == 1)


async def atender_aviso(motor: Any, evento: Evento, *, catalogo: ClienteCatalogo | None = None) -> Resultado:
    """Un `trabajo_encolado` de la cola `inteligencia.trabajos` (ADR 0046).

    Reclama la fila del aviso y la procesa. Si no la reclama —otro trabajador o
    el barrido la tomo, se cancelo antes, o ya termino—, el aviso ya esta
    atendido: una entrega repetida no procesa dos veces."""
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
    """El barrido con RabbitMQ: los `encolado` que perdieron su aviso y los colgados."""
    return await pasada(
        motor, catalogo=catalogo, retomar_colgados=True, encolado_antes_de=ahora() - _AVISO_PERDIDO
    )


async def correr_una_vez() -> int:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("inteligencia")
    catalogo = ClienteCatalogo()
    try:
        hechos = await pasada(motor, catalogo=catalogo, retomar_colgados=True)
        importadas = await importaciones.reintentar_pendientes(motor, catalogo=catalogo)
        if importadas:
            print(f"[trabajador] listas importadas: {importadas}")
        return hechos
    finally:
        await motor.cerrar()


async def _bucle(
    intervalo: float,
    *,
    dormir: Callable[[float], Awaitable[None]] | None = None,
    con_avisos: bool = False,
) -> None:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("inteligencia")
    catalogo = ClienteCatalogo()
    vuelta = 0

    async def _vuelta() -> None:
        nonlocal vuelta
        vuelta += 1
        if con_avisos:
            # Con RabbitMQ los `encolado` llegan por su aviso. El barrido corre
            # al arrancar y despues una vez por minuto.
            hechos = await barrer(motor, catalogo=catalogo) if vuelta % _VUELTAS_POR_BARRIDO == 1 else 0
        else:
            # Cada 12 vueltas (un minuto a 5 s) se amplia el claim a los
            # colgados, para retomar un `procesando` que quedo huerfano por un
            # crash sin pisar un trabajo que otro worker acaba de tomar en la
            # vuelta normal.
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
        await motor.cerrar()


async def escuchar_cola(
    url: str,
    *,
    seguir: bool,
    intervalo: float = 5.0,
    dormir: Callable[[float], Awaitable[None]] | None = None,
) -> int:
    """Con RabbitMQ (ADR 0046): atiende los avisos de `inteligencia.trabajos`.

    Sin `seguir`, atiende los avisos que hay en la cola, barre una vez y
    devuelve cuantos trabajos proceso. Con `seguir`, escucha la cola y, al lado,
    corre el bucle del barrido y de las listas pendientes; los dos sobre
    `bucle_resiliente`. Un aviso a la vez (`prefetch=1`): cada trabajo tarda, y
    el siguiente aviso queda para otro trabajador."""
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
            grupo.create_task(_bucle(intervalo, dormir=dormir, con_avisos=True))
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
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        hechos = asyncio.run(correr_una_vez())
        print(f"[trabajador] trabajos procesados: {hechos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["atender_aviso", "barrer", "correr_una_vez", "escuchar_cola", "main", "pasada"]
