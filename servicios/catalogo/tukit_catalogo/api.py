from __future__ import annotations

import argparse

from fastapi import FastAPI
from tukit_comun.bd import crear_motor
from tukit_comun.http import crear_app
from tukit_comun.telemetria import instrumentar_motor

from .routers import router_catalogo

PUERTO_POR_OMISION = 8012


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("catalogo")
    instrumentar_motor(app.state.motor.engine)


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Catalogo",
    descripcion=(
        "Lectura del catalogo curado: conceptos, productos canonicos con sus niveles y "
        "personaje, ofertas por tienda con precio, y las listas oficiales de los colegios. "
        "Contrato: CONTRATO_API.md seccion 12."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router_catalogo)

from .admin_http import router as _router_admin  # noqa: E402

app.include_router(_router_admin)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de lectura del catalogo.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run("tukit_catalogo.api:app", host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
