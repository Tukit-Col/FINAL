"""La superficie de Inteligencia: monta el router y ata el motor y los clientes.

`POST /v1/trabajos` devuelve 202 y no el kit, y esa es la decision de diseno
que ordena todo lo demas. El pipeline tarda minutos (OP-03 pide precision por
encima de velocidad) y ademas el flujo exige una pausa humana antes de que el
acudiente vea nada (AD-03 a AD-06). Una API sincronica no puede modelar una
espera que incluye a una persona, asi que el recurso central es el trabajo:
se crea, se consulta, y cuando termina se avisa. Las rutas viven en
`routers/inteligencia.py`; el SQL por-transaccion en `repositorios/trabajos.py`;
los helpers puros del pipeline en `dominio/` (ADR 0019). Este modulo solo
ensambla y conserva el wiring que las rutas y las pruebas necesitan:

- Los puertos de percepcion (`_RENDERIZAR`/`_LEER`/`_percibir_onboarding`) viven
  aqui como indireccion de modulo para que el onboarding se pueda probar sin
  pypdfium2 ni una llave de Gemini: las pruebas los sustituyen por dobles.
- Los clientes remotos (`_catalogo`/`_identidad`/`_comercio`) leen de
  `app.state`, inyectable en pruebas.
- La ejecucion de fondo es una tarea del mismo proceso (`trabajos.lanzar`); es
  lo que permite levantar todo con un comando y lo primero a cambiar (ADR 0024).
- `TUKIT_AUTOPUBLICAR` salta la revision humana; se anuncia a gritos al arrancar
  porque una valvula silenciosa acaba puesta en produccion.

    python -m tukit_inteligencia.api        # localhost:8013
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from fastapi import FastAPI, Request
from tukit_comun.bd import crear_motor
from tukit_comun.http import crear_app, crear_pool
from tukit_comun.telemetria import instrumentar_motor

from . import gemini, paginas, trabajos
from .percepcion import LeerPagina, Percepcion, Renderizar, percibir
from .remoto import (
    ESPERA_SEGUNDOS,
    ClienteCatalogo,
    ClienteComercio,
    ClienteIdentidad,
    url_catalogo,
    url_identidad,
)

# Bajo `python -m tukit_inteligencia.api` este modulo corre como __main__ y NO
# queda en sys.modules como 'tukit_inteligencia.api'. routers/inteligencia.py
# hace `from .. import api` (el patron de wiring de ADR 0019); sin esto Python
# no lo encuentra y lo CARGA UNA SEGUNDA VEZ, cayendo en un ImportError circular
# ("cannot import name 'router'"). Registrar este mismo objeto bajo su nombre de
# paquete hace que el back-import resuelva a el (un solo app, un solo motor).
if __name__ == "__main__":
    sys.modules.setdefault("tukit_inteligencia.api", sys.modules[__name__])

from .routers import router  # noqa: E402

PUERTO_POR_OMISION = 8013

# Los dos puertos de percepcion viven como indireccion de modulo para que el
# onboarding se pueda probar sin pypdfium2 y sin una llave de Gemini: las
# pruebas sustituyen `_RENDERIZAR` y `_LEER` (o el envoltorio completo
# `_percibir_onboarding`) por dobles. En produccion apuntan al render real y
# al adaptador de Gemini, que es el unico sitio que toca la red y la llave.
_RENDERIZAR: Renderizar = paginas.renderizar
_LEER: LeerPagina = gemini.pedir_pagina


def _percibir_onboarding(contenido: bytes) -> Percepcion:
    """Envoltorio con los puertos por omision, monkeypatcheable en pruebas."""
    return percibir(contenido, renderizar=_RENDERIZAR, leer=_LEER)


def _catalogo() -> Any:
    """El cliente del catalogo, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "catalogo", None)
    if cliente is None:
        cliente = ClienteCatalogo()
    return cliente


def _identidad() -> Any:
    """El cliente de Identidad, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "identidad", None)
    if cliente is None:
        cliente = ClienteIdentidad()
    return cliente


def _comercio() -> Any:
    """El cliente de Comercio, inyectable por `app.state` para las pruebas."""
    cliente = getattr(app.state, "comercio", None)
    if cliente is None:
        cliente = ClienteComercio()
    return cliente


async def _usuario_de_la_peticion(peticion: Request) -> str | None:
    """El `usuario_id` del acudiente autenticado, o None si viene anonimo.

    El token de sesion llega como `Authorization: Bearer ...` (lo reenvia el
    Route Handler desde la cookie httpOnly). Este servicio no tiene la clave
    HMAC: se lo pregunta a Identidad. Es la traza de propiedad que baja al
    pipeline; el flujo anonimo heredado cae de vuelta al contacto.
    """
    autorizacion = peticion.headers.get("Authorization", "")
    token = autorizacion[7:] if autorizacion.startswith("Bearer ") else None
    return await _identidad().usuario_del_token(token) if token else None


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("inteligencia")
    instrumentar_motor(app.state.motor.engine)
    if trabajos.autopublicar():
        print(
            "[inteligencia] TUKIT_AUTOPUBLICAR esta activo: los trabajos se publican SIN "
            "revision humana. Es un atajo de desarrollo y no debe estar puesto fuera de el."
        )
    # Un pool httpx de vida larga por destino (bulkhead, ADR 0020). Los helpers
    # `_catalogo/_identidad/_comercio` los leen de `app.state`; en pruebas se
    # sustituyen por dobles antes de tocar la red.
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
        "lista escolar en tres kits. Contrato: arquitectura/CONTRATO_API.md secciones 2 a 8."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router)


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
