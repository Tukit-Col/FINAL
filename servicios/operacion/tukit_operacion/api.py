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
