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
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from typing import Any

from sqlalchemy import select, update
from tukit_comun.metricas import contar_trabajo_publicado

from .modelos import EstadoTrabajo
from .remoto import ClienteCatalogo
from .trabajos import TRABAJO, procesar

_RECLAMABLES_NORMAL = (EstadoTrabajo.ENCOLADO.value,)
_RECLAMABLES_CON_COLGADOS = (EstadoTrabajo.ENCOLADO.value, EstadoTrabajo.PROCESANDO.value)
# Un trabajo "publicado" para la metrica es el que termino en un estado exitoso:
# publicado directo o a la espera de revision. `fallido` no cuenta.
_TERMINALES_EXITOSOS = frozenset(
    {EstadoTrabajo.PUBLICADO.value, EstadoTrabajo.ESPERA_REVISION.value}
)


async def _reclamar(motor: Any, *, limite: int, estados: tuple[str, ...]) -> list[uuid.UUID]:
    """Toma hasta `limite` trabajos reclamables y los marca `procesando`, atomico.

    El `SELECT … FOR UPDATE SKIP LOCKED` bloquea las filas y el `UPDATE` a
    `procesando` en la MISMA transaccion las saca del conjunto reclamable antes
    de soltar el lock: dos workers concurrentes nunca toman el mismo trabajo (uno
    ve la fila ya `procesando` y el `.in_(estados)` no la trae). `procesar` es
    idempotente en el claim (ya venia `procesando`), asi que no re-transiciona.
    """
    async with motor.engine.begin() as conexion:
        filas = list(
            await conexion.execute(
                select(TRABAJO.c.id)
                .where(TRABAJO.c.estado.in_(estados))
                .order_by(TRABAJO.c.creado_en)
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
        )
        ids = [f.id for f in filas]
        if ids:
            await conexion.execute(
                update(TRABAJO)
                .where(TRABAJO.c.id.in_(ids))
                .values(estado=EstadoTrabajo.PROCESANDO.value)
            )
        return ids


async def pasada(
    motor: Any,
    *,
    catalogo: ClienteCatalogo | None = None,
    limite: int = 10,
    retomar_colgados: bool = False,
) -> int:
    """Una pasada: procesa hasta `limite` trabajos reclamables. Devuelve cuantos.

    Con `retomar_colgados`, tambien reclama `procesando` (crash a mitad); sin el,
    solo `encolado`. Un fallo de un trabajo no tumba la pasada: `procesar` lo
    deja `fallido` con diagnostico (seccion 8) y devuelve, y el siguiente sigue.
    """
    estados = _RECLAMABLES_CON_COLGADOS if retomar_colgados else _RECLAMABLES_NORMAL
    ids = await _reclamar(motor, limite=limite, estados=estados)
    for trabajo_id in ids:
        await procesar(motor, trabajo_id, catalogo=catalogo)
        # Metrica de dominio (ADR 0021): se cuenta el trabajo que termino en un
        # estado exitoso (publicado o en revision), no el que quedo `fallido`.
        # Se lee el estado ya persistido por `procesar`, no se infiere.
        async with motor.engine.begin() as conexion:
            estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
        if estado in _TERMINALES_EXITOSOS:
            contar_trabajo_publicado()
    return len(ids)


async def correr_una_vez() -> int:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("inteligencia")
    catalogo = ClienteCatalogo()
    try:
        return await pasada(motor, catalogo=catalogo, retomar_colgados=True)
    finally:
        await motor.cerrar()


async def _bucle(intervalo: float) -> None:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("inteligencia")
    catalogo = ClienteCatalogo()
    vuelta = 0
    try:
        while True:
            # Cada 12 vueltas (un minuto a 5 s) se amplia el claim a los colgados,
            # para retomar un `procesando` que quedo huerfano por un crash sin
            # pisar un trabajo que otro worker acaba de tomar en la vuelta normal.
            vuelta += 1
            hechos = await pasada(motor, catalogo=catalogo, retomar_colgados=(vuelta % 12 == 0))
            if hechos:
                print(f"[trabajador] trabajos procesados: {hechos}")
            await asyncio.sleep(intervalo)
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena la cola de trabajos de Inteligencia y corre el pipeline (ADR 0024)."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        hechos = asyncio.run(correr_una_vez())
        print(f"[trabajador] trabajos procesados: {hechos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["correr_una_vez", "main", "pasada"]
