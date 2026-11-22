from __future__ import annotations

import argparse

from fastapi import FastAPI
from tukit_comun.bd import crear_motor
from tukit_comun.http import crear_app, crear_pool
from tukit_comun.telemetria import instrumentar_motor

from .pasarela import pasarela_desde_entorno
from .remoto import ESPERA_SEGUNDOS, ClienteCatalogo, ClienteIdentidad
from .routers import router

PUERTO_POR_OMISION = 8014


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("comercio")
    instrumentar_motor(app.state.motor.engine)
    app.state.pasarela = pasarela_desde_entorno()
    app.state.pool_catalogo = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.catalogo = ClienteCatalogo(cliente=app.state.pool_catalogo)
    app.state.pool_identidad = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.identidad = ClienteIdentidad(cliente=app.state.pool_identidad)


async def _apagar(app: FastAPI) -> None:
    await app.state.pool_catalogo.aclose()
    await app.state.pool_identidad.aclose()
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Comercio",
    descripcion=(
        "Pedidos, inventario, pagos (Wompi PSE) y entrega. Superficie de lectura del "
        "back-office de logistica y superficie de checkout del acudiente."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Comercio.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
