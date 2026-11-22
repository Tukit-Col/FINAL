"""Puerta de enlace: ruteo por prefijo hacia los servicios del backend.

Decisiones:
- Sin dominio y sin base: solo mira el prefijo de la ruta y reenvia. Las apps conocen una sola URL
  (`:8010`) y donde vive cada servicio es un detalle del backend.
- `Authorization: Bearer` viaja intacto hacia atras. La validacion autoritativa del token vive en
  `GET /v1/sesiones/actual` de Identidad, que conoce la `version_permisos` vigente y por eso puede
  revocar.
- Las rutas servicio a servicio que no se exponen (por ejemplo `/v1/comercio/pedidos-pagados`)
  responden como si no existieran.
- Las rutas del contrato que aun no tiene nadie detras responden 501 con la seccion del contrato.
- Un solo cliente httpx para todo el proceso: construir un `AsyncClient` por peticion arma un
  `SSLContext` de forma sincrona (~480 ms en Windows) con el bucle congelado.
"""

from __future__ import annotations

import argparse
import os
import re

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from tukit_comun.http import CABECERA_CORRELACION, crear_app, crear_pool, id_de_correlacion

from . import limite

PUERTO_POR_OMISION = 8010

ESPERA_SEGUNDOS = 300.0

CONEXIONES = 100

CABECERAS_SALTADAS = frozenset({"host", "content-length", "transfer-encoding", "connection", "keep-alive"})


def _servicios() -> dict[str, str]:
    return {
        "catalogo": os.environ.get("TUKIT_CATALOGO_URL", "http://127.0.0.1:8012").rstrip("/"),
        "identidad": os.environ.get("TUKIT_IDENTIDAD_URL", "http://127.0.0.1:8011").rstrip("/"),
        "inteligencia": os.environ.get("TUKIT_INTELIGENCIA_URL", "http://127.0.0.1:8013").rstrip("/"),
        "comercio": os.environ.get("TUKIT_COMERCIO_URL", "http://127.0.0.1:8014").rstrip("/"),
        "operacion": os.environ.get("TUKIT_OPERACION_URL", "http://127.0.0.1:8015").rstrip("/"),
    }


RUTAS: dict[str, str] = {
    "/v1/catalogo": "catalogo",
    "/v1/listas": "catalogo",
    "/v1/listas/subir": "inteligencia",
    "/v1/admin/listas": "catalogo",
    "/v1/admin/propuestas": "catalogo",
    "/v1/admin/catalogo": "catalogo",
    "/v1/admin/sugerencias": "catalogo",
    "/v1/admin/correcciones": "catalogo",
    "/v1/admin/acudientes": "identidad",
    "/v1/colegios": "identidad",
    "/v1/directorio": "identidad",
    "/v1/grados": "identidad",
    "/v1/contactos": "identidad",
    "/v1/usuarios": "identidad",
    "/v1/registro": "identidad",
    "/v1/sesiones": "identidad",
    "/v1/cuenta": "identidad",
    "/v1/trabajos": "inteligencia",
    "/v1/mis-solicitudes": "inteligencia",
    "/v1/nl2c": "inteligencia",
    "/v1/kits": "inteligencia",
    "/v1/grados-canonicos": "inteligencia",
    "/v1/admin": "inteligencia",
    "/v1/metricas": "inteligencia",
    "/v1/comercio": "comercio",
    "/v1/operacion": "operacion",
    "/v1/ordenes": "comercio",
    "/v1/pagos": "comercio",
    "/v1/webhooks/wompi": "comercio",
}


PENDIENTES: dict[str, str] = {}


RUTAS_BLOQUEADAS: frozenset[str] = frozenset({"/v1/comercio/pedidos-pagados"})

_PREFIJO_ORDENES = "/v1/ordenes"
_ORDENES_EXPUESTAS = re.compile(r"/v1/ordenes/[^/]+/avanzar")


_PREFIJO_CONSOLA = "/v1/admin"
_ROLES_EQUIPO = frozenset({"admin", "operador"})

_CONSOLA_ABIERTA: frozenset[tuple[str, str]] = frozenset({("POST", "/v1/admin/sugerencias")})

_CONSOLA_FUERA_DE_ADMIN: tuple[tuple[frozenset[str], re.Pattern[str]], ...] = (
    (frozenset({"PATCH", "DELETE"}), re.compile(r"/v1/catalogo/productos/[^/]+")),
    (frozenset({"POST"}), re.compile(r"/v1/catalogo/productos/[^/]+/reclasificar")),
    (frozenset({"PATCH"}), re.compile(r"/v1/colegios/[^/]+")),
)

_PREFIJO_CONTACTOS = "/v1/contactos"

ESPERA_SESION_SEGUNDOS = 10.0


def destino(ruta: str) -> str | None:
    for prefijo in sorted(RUTAS, key=len, reverse=True):
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            return RUTAS[prefijo]
    return None


def pendiente(ruta: str) -> str | None:
    for prefijo, seccion in PENDIENTES.items():
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            return seccion
    return None


def ambigua(ruta: str) -> bool:
    return "\\" in ruta or any(segmento in (".", "..") for segmento in ruta.split("/"))


def bloqueada(ruta: str) -> bool:
    if ambigua(ruta):
        return True
    if any(ruta == p or ruta.startswith(p + "/") for p in RUTAS_BLOQUEADAS):
        return True
    if ruta == _PREFIJO_ORDENES or ruta.startswith(_PREFIJO_ORDENES + "/"):
        return _ORDENES_EXPUESTAS.fullmatch(ruta) is None
    return ruta.startswith(_PREFIJO_CONTACTOS + "/")


async def _arrancar(app: FastAPI) -> None:
    app.state.cliente = crear_pool(espera=ESPERA_SEGUNDOS, conexiones=CONEXIONES)


async def _apagar(app: FastAPI) -> None:
    cliente = getattr(app.state, "cliente", None)
    if cliente is not None:
        await cliente.aclose()


def _cliente() -> httpx.AsyncClient:
    cliente = getattr(app.state, "cliente", None)
    if cliente is None:
        cliente = crear_pool(espera=ESPERA_SEGUNDOS, conexiones=CONEXIONES)
        app.state.cliente = cliente
    return cliente


def es_consola(metodo: str, ruta: str) -> bool:
    metodo = metodo.upper()
    camino = ruta.rstrip("/")
    if any(metodo in metodos and patron.fullmatch(camino) for metodos, patron in _CONSOLA_FUERA_DE_ADMIN):
        return True
    if not (ruta == _PREFIJO_CONSOLA or ruta.startswith(_PREFIJO_CONSOLA + "/")):
        return False
    return (metodo, camino) not in _CONSOLA_ABIERTA


def _token_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip() or None
    return authorization.strip() or None


def _rechazo(estado: int, error: str, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"error": error, "mensaje": mensaje})


async def _exigir_equipo(peticion: Request) -> JSONResponse | None:
    token = _token_bearer(peticion.headers.get("authorization"))
    if token is None:
        return _rechazo(401, "sesion_invalida", "El token no es valido o expiro.")
    base = _servicios()["identidad"]
    try:
        respuesta = await _cliente().get(
            f"{base}/v1/sesiones/actual",
            headers={"Authorization": f"Bearer {token}"},
            timeout=ESPERA_SESION_SEGUNDOS,
        )
    except httpx.HTTPError:
        respuesta = None
    if respuesta is not None and respuesta.status_code == 401:
        return _rechazo(401, "sesion_invalida", "El token no es valido o expiro.")
    if respuesta is None or respuesta.status_code != 200:
        return _rechazo(503, "identidad_no_disponible", "No se pudo validar la sesion.")
    roles = {r.get("rol") for r in respuesta.json().get("roles", [])}
    if not roles & _ROLES_EQUIPO:
        return _rechazo(403, "acceso_denegado", "Esta vista es solo para el equipo interno de Tukit.")
    return None


app = crear_app(
    titulo="Tukit Gateway",
    descripcion=(
        "Unica URL base del backend. Rutea por prefijo hacia catalogo, identidad e "
        "inteligencia. Contrato: CONTRATO_API.md seccion 12.1."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)


@app.get("/v1/servicios", tags=["salud"], summary="Que hay detras y si responde")
async def servicios() -> dict[str, object]:
    """Una sonda que dice la verdad sobre los tres, no solo sobre la puerta.

    Sin esto, `GET /salud` en la puerta responde `ok` con los tres servicios
    caidos, que es la clase de sonda que hace perder una tarde.
    """
    estado = {}
    cliente = _cliente()
    for nombre, base in _servicios().items():
        try:
            respuesta = await cliente.get(f"{base}/health/ready", timeout=5.0)
            estado[nombre] = {"url": base, "arriba": respuesta.status_code == 200}
        except httpx.HTTPError as error:
            estado[nombre] = {"url": base, "arriba": False, "detalle": str(error)}
    return {"servicios": estado, "todos_arriba": all(s["arriba"] for s in estado.values())}


@app.api_route(
    "/{ruta:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def reenviar(ruta: str, peticion: Request) -> Response:
    camino = "/" + ruta
    rechazo = await limite.revisar(peticion, camino)
    if rechazo is not None:
        return rechazo

    seccion = None if ambigua(camino) else pendiente(camino)
    if seccion is not None:
        return JSONResponse(
            status_code=501,
            content={
                "error": "no_implementado",
                "mensaje": (
                    f"{camino} esta en el contrato (seccion {seccion}) y todavia no hay "
                    "servicio detras. No cambies el cliente: la URL es la correcta."
                ),
                "seccion_contrato": seccion,
            },
        )

    if bloqueada(camino) or destino(camino) is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "ruta_desconocida",
                "mensaje": f"La puerta no atiende {camino}.",
                "rutas": sorted(RUTAS),
            },
        )

    nombre = destino(camino)

    if es_consola(peticion.method, camino):
        rechazo = await _exigir_equipo(peticion)
        if rechazo is not None:
            return rechazo

    base = _servicios()[nombre]
    cabeceras = {k: v for k, v in peticion.headers.items() if k.lower() not in CABECERAS_SALTADAS}
    cuerpo = await peticion.body()

    cid = id_de_correlacion()
    if cid:
        cabeceras[CABECERA_CORRELACION] = cid

    try:
        respuesta = await _cliente().request(
            peticion.method,
            f"{base}{camino}",
            params=dict(peticion.query_params),
            headers=cabeceras,
            content=cuerpo,
        )
    except httpx.HTTPError as error:
        return JSONResponse(
            status_code=503,
            content={
                "error": "servicio_no_disponible",
                "mensaje": f"El servicio de {nombre} no respondio en {base}.",
                "detalle": str(error),
            },
        )

    devueltas = {k: v for k, v in respuesta.headers.items() if k.lower() not in CABECERAS_SALTADAS}
    return Response(
        content=respuesta.content,
        status_code=respuesta.status_code,
        headers=devueltas,
        media_type=respuesta.headers.get("content-type"),
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la puerta de enlace de Tukit.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info", proxy_headers=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
