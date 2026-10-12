"""La superficie de lectura de Catalogo: monta los routers y ata el motor.

Las rutas — conceptos, productos con sus ofertas, la escritura de un producto,
las listas oficiales y el emparejamiento — viven en `routers/catalogo.py`; el
SQL en `repositorios/catalogo.py`; los shapers y la validacion, puros, en
`dominio/catalogo.py`. La revision de listas por `/v1/admin` sigue en
`admin_http` y se monta sobre la misma app y el mismo motor. Este modulo solo
ensambla (ADR 0019).

    python -m tukit_catalogo.api            # localhost:8012
"""

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
        "Contrato: docs/arquitectura/CONTRATO_API.md seccion 12."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router_catalogo)

# La superficie de ESCRITURA de la revision de listas vive aparte, en
# `admin_http`, para que la lectura pueda seguir diciendo con verdad que es de
# solo lectura. Es la mano de la persona que revisa: editar renglones, decidir
# propuestas, cerrar una lista y clonarla para corregir. Se monta sobre la
# misma app —y el mismo `app.state.motor`— y se rutea por su prefijo `/v1/admin`.
from .admin_http import router as _router_admin  # noqa: E402

app.include_router(_router_admin)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de lectura del catalogo.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    # Se arranca por CADENA DE IMPORTACION, no pasando `app`, a proposito. Con
    # `python -m tukit_catalogo.api` este archivo es `__main__`, y uvicorn
    # correria el lifespan sobre `__main__.app`. Pero `admin_http._motor()` hace
    # `from .api import app`, que importa `tukit_catalogo.api` como OTRO modulo:
    # una segunda `app` cuyo lifespan nunca corrio y cuyo `state.motor` no
    # existe (de ahi el 500 en `/v1/admin/*`). Nombrar el modulo canonico hace
    # que uvicorn importe esa misma `tukit_catalogo.api`, corra su lifespan y
    # sea la que `admin_http` ve: una sola `app`, un solo motor.
    uvicorn.run("tukit_catalogo.api:app", host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
