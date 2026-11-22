"""Arranque HTTP compartido: la misma app, el mismo error, el mismo CORS.

Decisiones:
- Sobre de error comun `{error, mensaje, campo}`. El manejador de validacion nunca devuelve lo que
  el cliente envio: reescribe la respuesta por omision de FastAPI (que incluye `input`) y deja solo
  la ubicacion del campo.
- Los origenes CORS salen del entorno para que produccion no herede los de desarrollo.
- El id de correlacion vive en un `contextvar`; lo acuna el gateway en el borde y viaja a las
  llamadas salientes y al sobre de error.
"""

from __future__ import annotations

import contextvars
import os
import uuid
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

ORIGENES_POR_OMISION = ("http://localhost:3000", "http://127.0.0.1:3000")

CABECERA_CORRELACION = "x-correlation-id"
_correlacion: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlacion_id", default=None)


def id_de_correlacion() -> str | None:
    return _correlacion.get()


def fijar_correlacion(cid: str | None) -> contextvars.Token[str | None]:
    return _correlacion.set(cid)


def reset_correlacion(token: contextvars.Token[str | None]) -> None:
    _correlacion.reset(token)


class ErrorDominio(Exception):
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
    return valor.isoformat() if valor is not None else None


@asynccontextmanager
async def cliente_efimero(
    cliente: httpx.AsyncClient | None, espera: float
) -> AsyncIterator[httpx.AsyncClient]:
    import httpx

    cid = _correlacion.get()
    cabeceras = {CABECERA_CORRELACION: cid} if cid else None

    if cliente is not None:
        yield cliente
        return
    propio = httpx.AsyncClient(timeout=espera, headers=cabeceras)
    try:
        yield propio
    finally:
        await propio.aclose()


async def _sellar_correlacion(peticion: Any) -> None:
    cid = _correlacion.get()
    if cid and CABECERA_CORRELACION not in peticion.headers:
        peticion.headers[CABECERA_CORRELACION] = cid


def crear_pool(*, espera: float, conexiones: int = 20) -> httpx.AsyncClient:
    import httpx

    return httpx.AsyncClient(
        timeout=espera,
        limits=httpx.Limits(max_connections=conexiones, max_keepalive_connections=conexiones),
        event_hooks={"request": [_sellar_correlacion]},
    )


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
    from contextlib import asynccontextmanager

    from .cache import cerrar_cliente
    from .registro import configurar_registro

    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        if al_arrancar is not None:
            await al_arrancar(app)
        try:
            yield
        finally:
            if al_apagar is not None:
                await al_apagar(app)
            await cerrar_cliente()

    app = FastAPI(title=titulo, description=descripcion, version=version, lifespan=ciclo)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_permitidos(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _correlacion_mw(peticion: Request, siguiente: Callable[[Request], Any]) -> Any:
        cid = peticion.headers.get(CABECERA_CORRELACION) or uuid.uuid4().hex
        token = _correlacion.set(cid)
        try:
            respuesta = await siguiente(peticion)
        finally:
            _correlacion.reset(token)
        respuesta.headers[CABECERA_CORRELACION] = cid
        return respuesta

    @app.exception_handler(ErrorDominio)
    async def _dominio(_peticion: Request, error: ErrorDominio) -> JSONResponse:
        return JSONResponse(status_code=error.estado, content=error.cuerpo())

    @app.exception_handler(RequestValidationError)
    async def _validacion(_peticion: Request, error: RequestValidationError) -> JSONResponse:
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

    configurar_registro(titulo)

    from .metricas import configurar_metricas
    from .telemetria import configurar_telemetria

    configurar_telemetria(app, titulo)
    configurar_metricas()

    @app.get("/salud", tags=["salud"], summary="Sonda de vida del servicio")
    async def salud() -> dict[str, str]:
        return {"estado": "ok", "servicio": titulo, "version": version}

    @app.get("/health/live", tags=["salud"], summary="Liveness: el proceso responde")
    async def live() -> dict[str, str]:
        return {"estado": "vivo", "servicio": titulo}

    @app.get("/health/ready", tags=["salud"], summary="Readiness: listo para atender")
    async def ready() -> JSONResponse:
        from sqlalchemy import text

        motor = getattr(app.state, "motor", None)
        if motor is None:
            return JSONResponse({"estado": "listo", "servicio": titulo})
        try:
            async with motor.engine.connect() as conexion:
                await conexion.execute(text("SELECT 1"))
        except Exception as error:  # noqa: BLE001 — el detalle va al cuerpo, no se traga
            return JSONResponse(
                status_code=503,
                content={"estado": "no_listo", "servicio": titulo, "detalle": str(error)},
            )
        return JSONResponse({"estado": "listo", "servicio": titulo})

    return app
