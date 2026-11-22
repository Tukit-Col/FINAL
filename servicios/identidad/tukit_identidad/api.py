from __future__ import annotations

import argparse

from fastapi import FastAPI
from tukit_comun.bd import crear_motor
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import crear_app
from tukit_comun.telemetria import instrumentar_motor

from .dominio import sesiones
from .routers import router

PUERTO_POR_OMISION = 8011


async def _arrancar(app: FastAPI) -> None:
    sesiones._llave()  # sin TUKIT_LLAVE_SESION avisa aqui, al arrancar, y no al firmar el primer token
    cifrador_desde_entorno()
    app.state.motor = crear_motor("identidad")
    instrumentar_motor(app.state.motor.engine)


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Identidad",
    descripcion=(
        "Colegios, sedes y grados para que el acudiente escoja, registro del contacto "
        "que convierte un correo en un identificador, sesiones y mi cuenta. Contrato: seccion 12.4."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Identidad.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
