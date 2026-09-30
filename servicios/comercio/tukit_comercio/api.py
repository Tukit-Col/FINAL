"""El ensamblador de Comercio: crea la app, cuelga singletons, monta el router.

La superficie (lectura de logística + escritura de checkout, §9 del contrato)
vive en `routers/comercio.py`; el qué-decide-el-negocio en `dominio/`; el SQL en
`repositorios/`. Aquí sólo se construye la `FastAPI` con `crear_app`, se cuelgan
de `app.state` los singletons que el router lee en cada petición (el motor de
base, la pasarela y el cliente de Catálogo) y se incluye el router. Esta
separación es la ADR 0019: capas internas de puertos-y-adaptadores ligero.

    python -m tukit_comercio.api            # localhost:8014
"""

from __future__ import annotations

import argparse

from fastapi import FastAPI
from tukit_comun.bd import crear_motor
from tukit_comun.http import crear_app, crear_pool
from tukit_comun.telemetria import instrumentar_motor

from .pasarela import pasarela_desde_entorno
from .remoto import ESPERA_SEGUNDOS, ClienteCatalogo
from .routers import router

PUERTO_POR_OMISION = 8014


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("comercio")
    instrumentar_motor(app.state.motor.engine)
    # La pasarela y el cliente de Catalogo se cuelgan de la app para poder
    # sustituirlos por dobles en las pruebas sin tocar los endpoints. La
    # pasarela sale de WOMPI_MODO (falso por omision, sandbox con llaves).
    app.state.pasarela = pasarela_desde_entorno()
    # Pool httpx de vida larga hacia Catalogo (bulkhead, ADR 0020): reusa
    # conexiones y acota las que van a ese destino. El cliente inyectado en las
    # pruebas (`app.state.catalogo` con su doble) no pasa por aqui.
    app.state.pool_catalogo = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.catalogo = ClienteCatalogo(cliente=app.state.pool_catalogo)


async def _apagar(app: FastAPI) -> None:
    await app.state.pool_catalogo.aclose()
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
