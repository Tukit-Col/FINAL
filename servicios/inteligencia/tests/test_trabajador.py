"""El trabajador durable del pipeline (ADR 0024).

`lanzar` ya no arranca una `asyncio.Task` efimera: solo deja el trabajo
`encolado` (lo hace `crear`). Un trabajador drena la cola con `SELECT … FOR
UPDATE SKIP LOCKED` —el mismo mecanismo del outbox—, mueve la fila a
`procesando` y ejecuta `procesar`. Si el proceso muere a mitad, la fila sigue
`procesando`/`encolado` y otro worker (o el reinicio) la retoma; no queda
trabajo perdido, que es el gap que la ADR cierra.

Se fija aqui:

- Una pasada toma un trabajo `encolado`, lo procesa y lo deja publicado.
- `SKIP LOCKED`: dos pasadas concurrentes no procesan el mismo trabajo dos veces.
- Un trabajo que quedo `procesando` (crash a mitad) se retoma en la pasada.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_inteligencia import trabajador, trabajos
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.trabajos import TRABAJO


async def _encolar(motor) -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
    )
    return uuid.UUID(respuesta["trabajo_id"])


async def test_una_pasada_procesa_un_encolado(motor):
    trabajo_id = await _encolar(motor)
    catalogo = _catalogo_verificado()

    n = await trabajador.pasada(motor, catalogo=catalogo)

    assert n == 1
    async with motor.engine.begin() as conexion:
        estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    # Sin contacto/origen, `crear` da un trabajo `colegio_grado`: la ruta rapida
    # lo deja en revision (kit canonico del grado), no publicado directo.
    assert estado == EstadoTrabajo.ESPERA_REVISION.value


async def test_sin_encolados_no_hace_nada(motor):
    assert await trabajador.pasada(motor, catalogo=_catalogo_verificado()) == 0


async def test_el_claim_saca_el_trabajo_de_la_cola(motor):
    # El claim mueve la fila a `procesando` en la MISMA transaccion del SELECT,
    # asi que una segunda pasada (normal, solo mira `encolado`) ya no lo ve: es
    # lo que en Postgres el SKIP LOCKED convierte en "dos workers no lo toman a la
    # vez". Aqui se verifica el efecto observable (la fila sale de la cola) sin
    # depender del SKIP LOCKED real, que SQLite no implementa.
    await _encolar(motor)
    catalogo = _catalogo_verificado()

    assert await trabajador.pasada(motor, catalogo=catalogo) == 1
    assert await trabajador.pasada(motor, catalogo=catalogo) == 0  # ya no esta encolado


async def test_no_reclama_lo_que_otro_proceso_va_a_procesar(motor):
    # El poller y el preview crean el trabajo y lo procesan en el acto. Si
    # naciera `encolado`, el trabajador podria tomarlo entre el INSERT y ese
    # `procesar`, y los dos armarian los kits a la vez.
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
        en_proceso=True,
    )
    assert await trabajador.pasada(motor, catalogo=_catalogo_verificado()) == 0

    estado = await trabajos.procesar(
        motor, uuid.UUID(respuesta["trabajo_id"]), catalogo=_catalogo_verificado()
    )
    assert estado == EstadoTrabajo.ESPERA_REVISION.value


async def test_retoma_un_procesando_colgado(motor):
    # Simula un crash: el trabajo quedo `procesando` sin nadie ejecutandolo, y
    # hace rato (un `procesando` reciente es de alguien que lo esta armando).
    trabajo_id = await _encolar(motor)
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(
                estado=EstadoTrabajo.PROCESANDO.value, actualizado_en=trabajos.ahora() - timedelta(hours=1)
            )
        )

    n = await trabajador.pasada(motor, catalogo=_catalogo_verificado(), retomar_colgados=True)

    assert n == 1
    async with motor.engine.begin() as conexion:
        estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    # Sin contacto/origen, `crear` da un trabajo `colegio_grado`: la ruta rapida
    # lo deja en revision (kit canonico del grado), no publicado directo.
    assert estado == EstadoTrabajo.ESPERA_REVISION.value


async def test_no_le_roba_el_trabajo_a_quien_lo_esta_armando(motor):
    # El poller crea el canonico ya `procesando` y lo arma en su propio
    # proceso. Retomar colgados cada minuto lo tomaba tambien, los dos lo
    # armaban a la vez y uno terminaba en "no se puede pasar de fallido a
    # publicado": asi se perdio el rearmado de Octavo dos veces.
    await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
        en_proceso=True,
    )
    assert await trabajador.pasada(motor, catalogo=_catalogo_verificado(), retomar_colgados=True) == 0
