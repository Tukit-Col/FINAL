"""La superficie de Operacion: monta el router y ata los singletons.

Dos superficies, como en el contrato (`libs/ts/tukit-contrato/src/operacion.ts`):

- **Lectura** (`GET /v1/operacion/casos`, `/{id}`, `/metricas`): la bandeja del
  back-office, ordenada por prioridad y luego por vencimiento, y las series de
  metricas de calidad congeladas por dia.
- **Escritura** (`POST /v1/operacion/casos`): lo que un acudiente manda desde el
  centro de ayuda. El contacto NO se persiste: se resuelve a un `usuario_id`
  contra Identidad. `vence_en` sale de la tabla de SLA por categoria (Ley 1755).

Este modulo solo ensambla: crea el motor y el cliente de Identidad al arrancar,
los cuelga de `app.state`, y monta `routers/operacion.py`. El parseo, las reglas
y el SQL viven en `routers/`, `dominio/` y `repositorios/` (ADR 0019).

    python -m tukit_operacion.api            # localhost:8015
"""

from __future__ import annotations

import argparse

from fastapi import FastAPI
from tukit_comun.bd import crear_motor
from tukit_comun.http import crear_app, crear_pool
from tukit_comun.telemetria import instrumentar_motor

from .remoto import ESPERA_SEGUNDOS, ClienteIdentidad
from .routers import router

PUERTO_POR_OMISION = 8015


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("operacion")
    instrumentar_motor(app.state.motor.engine)
    # El cliente de Identidad se cuelga de la app para poder sustituirlo en las
    # pruebas sin tocar el endpoint.
    app.state.pool_identidad = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.identidad = ClienteIdentidad(cliente=app.state.pool_identidad)


async def _apagar(app: FastAPI) -> None:
    await app.state.pool_identidad.aclose()
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Operacion",
    descripcion=(
        "Casos, PQRS, notificaciones, auditoria y telemetria. Bandeja del back-office y "
        "alta de PQRS del acudiente. El contacto se resuelve a un id en Identidad, no se guarda."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Operacion.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
