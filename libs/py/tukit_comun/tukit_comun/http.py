"""Arranque HTTP compartido: la misma app, el mismo error, el mismo CORS.

Es el gemelo de `migraciones.py` para la capa de conversacion. Cada servicio
expone su propia superficie y ninguno importa la de otro, pero tres cosas
tienen que ser identicas en los tres o el frontend las sufre:

**El sobre de error.** El contrato (seccion 11) fija `{error, mensaje, campo}`
y fija tambien lo que NUNCA se devuelve: lo que el cliente acaba de enviar. El
manejador de validacion del sistema anterior le devolvia al cliente la
contrasena que habia recibido, y ese defecto esta documentado. Aqui el
manejador de `RequestValidationError` reescribe la respuesta por omision de
FastAPI, que incluye el valor recibido en `input`, y deja solo la ubicacion
del campo.

**El CORS.** Un Next.js en `localhost:3000` no puede leer ninguna respuesta
sin esto, y el sintoma es un error de red en el navegador que no se parece en
nada a la causa. Los origenes salen del entorno para que produccion no herede
la lista de desarrollo.

**La sonda de salud.** `GET /salud` en los tres, con el mismo cuerpo, para
que el ejecutor de tareas pueda esperar a que el servicio este arriba sin
saber cual es.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    import httpx

# Los dos puertos en los que arranca un Next.js recien creado. Se ponen por
# omision porque el caso de desarrollo es el 100 % de los usos de hoy y
# pedirle a alguien que exporte una variable para ver la primera pantalla es
# friccion sin contrapartida. En produccion se sobreescribe con
# `TUKIT_CORS_ORIGENES`, separando con comas.
ORIGENES_POR_OMISION = ("http://localhost:3000", "http://127.0.0.1:3000")


class ErrorDominio(Exception):
    """Un rechazo del dominio, con el codigo que el contrato promete.

    No es lo mismo que un fallo: `presupuesto_invalido` y `lista_ya_publicada`
    son respuestas legitimas del sistema, y el frontend las distingue por el
    campo `error`, no leyendo el texto. Por eso el codigo es un dato y no una
    cadena formateada dentro del mensaje.
    """

    def __init__(self, error: str, mensaje: str, *, estado: int = 400, campo: str | None = None) -> None:
        super().__init__(mensaje)
        self.error = error
        self.mensaje = mensaje
        self.estado = estado
        self.campo = campo

    def cuerpo(self) -> dict[str, Any]:
        sobre: dict[str, Any] = {"error": self.error, "mensaje": self.mensaje}
        if self.campo is not None:
            sobre["campo"] = self.campo
        return sobre


def iso(valor: datetime | None) -> str | None:
    """Fecha a texto ISO-8601, o `None` si no hay fecha.

    Vive aqui porque comercio y operacion serializaban lo mismo con dos copias
    identicas de este ayudante. `None` es "no hay fecha", no una cadena vacia:
    el contrato distingue "sin entregar" de "entregado en fecha desconocida".
    """
    return valor.isoformat() if valor is not None else None


@asynccontextmanager
async def cliente_efimero(
    cliente: httpx.AsyncClient | None, espera: float
) -> AsyncIterator[httpx.AsyncClient]:
    """El cliente httpx inyectado, o uno propio que se cierra al salir.

    Los tres `remoto.py` (catalogo, identidad, operacion) repetian el mismo
    baile: `propio = self.cliente is None; cliente = self.cliente or AsyncClient();
    try: ... finally: if propio: await cliente.aclose()`. El patron compartido es
    SOLO el ciclo de vida del cliente —tomar el inyectado (para las pruebas) o
    abrir uno efimero y cerrarlo—; el manejo de errores de cada metodo (levantar
    vs devolver None, tratar el 404) es distinto a proposito y se queda en cada
    cliente. Por eso esto es un context manager y no una clase base con logica.
    """
    import httpx

    if cliente is not None:
        yield cliente
        return
    propio = httpx.AsyncClient(timeout=espera)
    try:
        yield propio
    finally:
        await propio.aclose()


def origenes_permitidos() -> list[str]:
    crudo = os.environ.get("TUKIT_CORS_ORIGENES", "").strip()
    if not crudo:
        return list(ORIGENES_POR_OMISION)
    return [o.strip() for o in crudo.split(",") if o.strip()]


def crear_app(
    *,
    titulo: str,
    descripcion: str,
    version: str = "1.1",
    al_arrancar: Callable[[FastAPI], Any] | None = None,
    al_apagar: Callable[[FastAPI], Any] | None = None,
) -> FastAPI:
    """Una app de FastAPI con el CORS, los errores y la sonda ya puestos.

    `al_arrancar` y `al_apagar` reciben la app para colgarle el motor de base
    de datos en `app.state`. Se pasan como funciones y no se resuelven aqui
    porque la libreria no conoce los modelos de nadie, que es la misma regla
    que hace que `crear_motor` reciba el nombre del servicio por argumento.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        if al_arrancar is not None:
            await al_arrancar(app)
        try:
            yield
        finally:
            if al_apagar is not None:
                await al_apagar(app)

    app = FastAPI(title=titulo, description=descripcion, version=version, lifespan=ciclo)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_permitidos(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ErrorDominio)
    async def _dominio(_peticion: Request, error: ErrorDominio) -> JSONResponse:
        return JSONResponse(status_code=error.estado, content=error.cuerpo())

    @app.exception_handler(RequestValidationError)
    async def _validacion(_peticion: Request, error: RequestValidationError) -> JSONResponse:
        # Se conserva DONDE fallo y se descarta QUE se envio. La respuesta por
        # omision de FastAPI trae `input` con el valor recibido, y es
        # exactamente el defecto que el contrato prohibe repetir.
        campos = [".".join(str(p) for p in d.get("loc", ())[1:]) for d in error.errors()]
        primero = next((c for c in campos if c), None)
        return JSONResponse(
            status_code=400,
            content={
                "error": "entrada_invalida",
                "mensaje": "La peticion no tiene la forma que el contrato espera.",
                **({"campo": primero} if primero else {}),
            },
        )

    @app.get("/salud", tags=["salud"], summary="Sonda de vida del servicio")
    async def salud() -> dict[str, str]:
        return {"estado": "ok", "servicio": titulo, "version": version}

    return app
