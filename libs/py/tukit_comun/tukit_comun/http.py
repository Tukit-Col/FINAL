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

# Los dos puertos en los que arranca un Next.js recien creado. Se ponen por
# omision porque el caso de desarrollo es el 100 % de los usos de hoy y
# pedirle a alguien que exporte una variable para ver la primera pantalla es
# friccion sin contrapartida. En produccion se sobreescribe con
# `TUKIT_CORS_ORIGENES`, separando con comas.
ORIGENES_POR_OMISION = ("http://localhost:3000", "http://127.0.0.1:3000")

# El id de correlacion: una sola cadena que sigue una peticion a traves de todos
# los servicios que toca. Sin esto, un fallo en la saga de pago deja cinco logs
# en cinco servicios sin forma de saber que son la misma peticion. Se guarda en
# un `contextvar` (no un global de modulo) porque el servidor atiende varias
# peticiones async a la vez y un global las mezclaria. La cabecera es la
# convencion de facto (`x-correlation-id`), en minusculas porque HTTP no
# distingue mayusculas y asi se compara sin normalizar.
CABECERA_CORRELACION = "x-correlation-id"
_correlacion: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlacion_id", default=None)


def id_de_correlacion() -> str | None:
    """El id de correlacion de la peticion en curso, o `None` fuera de una.

    `None` fuera de un ciclo de peticion (un poller, un CLI): no se inventa un
    id para trabajo que nadie pidio por HTTP, y quien propaga trata `None` como
    "no anexar cabecera".
    """
    return _correlacion.get()


def fijar_correlacion(cid: str | None) -> contextvars.Token[str | None]:
    """Fija el id de correlacion en el contexto actual y devuelve el token.

    Lo usa el drenador de la bandeja (`tukit_comun.bandeja`) para RE-VINCULAR el
    id que viajo en la carga del evento antes de manejarlo: asi un evento drenado
    del outbox recupera el hilo de la peticion que lo origino (cierra el hueco de
    §A.6). Quien lo llama debe hacer `_correlacion.reset(token)` al terminar, o
    usar el mismo patron del middleware. `reset_correlacion` lo encapsula."""
    return _correlacion.set(cid)


def reset_correlacion(token: contextvars.Token[str | None]) -> None:
    """Deshace un `fijar_correlacion`, para no filtrar el id al siguiente uso."""
    _correlacion.reset(token)


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

    # El id de correlacion viaja como cabecera por omision del cliente, asi que
    # se propaga a TODA llamada saliente sin tocar cada `remoto.py`. Es aditivo:
    # si no hay id (un poller, un CLI) no se anexa nada, y una cabecera que el
    # metodo llamante pase explicitamente en `headers=` gana, porque va por
    # peticion y las de omision no la pisan.
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
    """Estampa el id de correlacion VIVO en cada peticion saliente del pool.

    Un cliente de pool vive entre peticiones, asi que el id NO puede ir como
    cabecera por omision (quedaria congelado el de la primera peticion). Este
    hook lo lee del contextvar en cada salida, que es donde `cliente_efimero`
    ponia la cabecera para el cliente efimero. Aditivo: sin id, no anexa nada;
    una cabecera explicita del llamante ya viene puesta y no se pisa."""
    cid = _correlacion.get()
    if cid and CABECERA_CORRELACION not in peticion.headers:
        peticion.headers[CABECERA_CORRELACION] = cid


def crear_pool(*, espera: float, conexiones: int = 20) -> httpx.AsyncClient:
    """Un cliente httpx de vida larga (bulkhead por destino, ADR 0020).

    Reusa conexiones en vez de abrir una por llamada (lo que hacia el efimero),
    y su `Limits` acota cuantas hay en vuelo hacia UN destino: si ese destino se
    degrada, la saturacion no se derrama a los demas. El id de correlacion se
    estampa por peticion via `event_hook` (no cabecera por omision, ver arriba).
    Lo crea el `_arrancar` de cada servicio y lo cierra el `_apagar`."""
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
    """Una app de FastAPI con el CORS, los errores y la sonda ya puestos.

    `al_arrancar` y `al_apagar` reciben la app para colgarle el motor de base
    de datos en `app.state`. Se pasan como funciones y no se resuelven aqui
    porque la libreria no conoce los modelos de nadie, que es la misma regla
    que hace que `crear_motor` reciba el nombre del servicio por argumento.
    """
    from contextlib import asynccontextmanager

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
        # Toma el id que llega (el gateway lo acuña en el borde, ver
        # `tukit_gateway.api`), o acuña uno si esta peticion entra directo al
        # servicio. Se guarda en el contextvar de ESTA peticion para que las
        # llamadas salientes (via `cliente_efimero`) y el sobre de error lo
        # lleven sin pasarlo a mano, y se resetea al salir para no filtrarlo a
        # la siguiente peticion que reuse el hilo/tarea.
        cid = peticion.headers.get(CABECERA_CORRELACION) or uuid.uuid4().hex
        token = _correlacion.set(cid)
        try:
            respuesta = await siguiente(peticion)
        finally:
            _correlacion.reset(token)
        respuesta.headers[CABECERA_CORRELACION] = cid
        return respuesta

    # Los dos manejadores devuelven el sobre EXACTO del contrato (nada mas: el
    # test fija `set(cuerpo) == {error, mensaje, campo}`). El id de correlacion
    # no va en el cuerpo sino en la cabecera, y no hace falta ponerlo aqui: la
    # respuesta de estos manejadores vuelve a salir por `_correlacion_mw` (que
    # envuelve al ExceptionMiddleware), y alli se le pega la cabecera.
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

    configurar_registro(titulo)

    from .metricas import configurar_metricas
    from .telemetria import configurar_telemetria

    configurar_telemetria(app, titulo)
    configurar_metricas()

    @app.get("/salud", tags=["salud"], summary="Sonda de vida del servicio")
    async def salud() -> dict[str, str]:
        return {"estado": "ok", "servicio": titulo, "version": version}

    # Liveness vs readiness (ADR 0021): `/health/live` dice "el loop respira" (no
    # toca base: si respondiera 200 solo con base arriba, un orquestador reiniciaria
    # el proceso por una caida de base que el reinicio no arregla). `/health/ready`
    # dice "puedo atender": prueba la base con un `SELECT 1` sobre el pool (que ya
    # hace `pool_pre_ping`). `/salud` se conserva como alias de liveness.
    @app.get("/health/live", tags=["salud"], summary="Liveness: el proceso responde")
    async def live() -> dict[str, str]:
        return {"estado": "vivo", "servicio": titulo}

    @app.get("/health/ready", tags=["salud"], summary="Readiness: listo para atender")
    async def ready() -> JSONResponse:
        from sqlalchemy import text

        motor = getattr(app.state, "motor", None)
        if motor is None:  # un servicio sin base (el gateway) esta listo si responde
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
