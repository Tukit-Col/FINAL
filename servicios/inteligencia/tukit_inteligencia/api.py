"""Superficie de Inteligencia: monta el router y ata el motor y los clientes.

Decisiones:
- `POST /v1/trabajos` devuelve 202 y no el kit: el pipeline tarda minutos y el flujo exige una
  pausa humana antes de que el acudiente vea nada, asi que el recurso central es el trabajo, que se
  crea, se consulta y avisa al terminar.
- Los puertos de percepcion (render y lectura de pagina) tienen su valor por omision aqui y se
  cambian por `app.state.renderizar` y `app.state.leer`, para probar el onboarding sin pypdfium2 ni
  llave de Gemini. Los clientes remotos tambien leen de `app.state`.
- `TUKIT_AUTOPUBLICAR` salta la revision humana y se anuncia al arrancar.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from fastapi import FastAPI, Request
from tukit_comun.bd import crear_motor
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import crear_app, crear_pool
from tukit_comun.telemetria import instrumentar_motor

from . import cache_lecturas, gemini, paginas, trabajos
from .percepcion import LeerPagina, Percepcion, Renderizar, percibir
from .remoto import (
    ESPERA_SEGUNDOS,
    ClienteCatalogo,
    ClienteComercio,
    ClienteIdentidad,
    url_catalogo,
    url_identidad,
)

if __name__ == "__main__":
    sys.modules.setdefault("tukit_inteligencia.api", sys.modules[__name__])

from .routers import router  # noqa: E402
from .routers.nl2c import router as router_nl2c  # noqa: E402

PUERTO_POR_OMISION = 8013

_RENDERIZAR: Renderizar = paginas.renderizar
_LEER: LeerPagina = gemini.pedir_pagina


async def _percibir_onboarding(contenido: bytes) -> Percepcion:
    renderizar = getattr(app.state, "renderizar", None) or _RENDERIZAR
    leer = getattr(app.state, "leer", None) or _LEER
    return await cache_lecturas.percibir_guardada(
        contenido, lambda archivo: percibir(archivo, renderizar=renderizar, leer=leer)
    )


def _catalogo() -> Any:
    cliente = getattr(app.state, "catalogo", None)
    if cliente is None:
        cliente = ClienteCatalogo()
    return cliente


def _identidad() -> Any:
    cliente = getattr(app.state, "identidad", None)
    if cliente is None:
        cliente = ClienteIdentidad()
    return cliente


def _comercio() -> Any:
    cliente = getattr(app.state, "comercio", None)
    if cliente is None:
        cliente = ClienteComercio()
    return cliente


async def _usuario_de_la_peticion(peticion: Request) -> str | None:
    autorizacion = peticion.headers.get("Authorization", "")
    token = autorizacion[7:] if autorizacion.startswith("Bearer ") else None
    return await _identidad().usuario_del_token(token) if token else None


async def _arrancar(app: FastAPI) -> None:
    cifrador_desde_entorno()  # sin TUKIT_LLAVE_CIFRADO avisa al arrancar; en produccion no arranca
    app.state.motor = crear_motor("inteligencia")
    instrumentar_motor(app.state.motor.engine)
    if trabajos.autopublicar():
        print(
            "[inteligencia] TUKIT_AUTOPUBLICAR esta activo: los trabajos se publican SIN "
            "revision humana. Es un atajo de desarrollo y no debe estar puesto fuera de el."
        )
    app.state.pool_catalogo = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.pool_identidad = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.pool_comercio = crear_pool(espera=ESPERA_SEGUNDOS)
    app.state.catalogo = ClienteCatalogo(cliente=app.state.pool_catalogo)
    app.state.identidad = ClienteIdentidad(cliente=app.state.pool_identidad)
    app.state.comercio = ClienteComercio(cliente=app.state.pool_comercio)
    print(f"[inteligencia] catalogo en {url_catalogo()}, identidad en {url_identidad()}")


async def _apagar(app: FastAPI) -> None:
    for atributo in ("pool_catalogo", "pool_identidad", "pool_comercio"):
        pool = getattr(app.state, atributo, None)
        if pool is not None:
            await pool.aclose()
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Inteligencia",
    descripcion=(
        "El recurso `trabajo`: percepcion, normalizacion, resolucion y optimizacion de una "
        "lista escolar en tres kits. Contrato: CONTRATO_API.md secciones 2 a 8."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router)
app.include_router(router_nl2c)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API del pipeline de kits.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
