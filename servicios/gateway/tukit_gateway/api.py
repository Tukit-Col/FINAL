"""Ruteo por prefijo. Una URL para el frontend, tres servicios detras.

El manifiesto declara este componente "sin dominio y sin base", y esta
version lo cumple al pie de la letra: no hay una sola consulta, ni un modelo,
ni una decision de negocio. Solo mira el prefijo de la ruta y reenvia.

Por que existe teniendo los tres servicios con CORS puesto. Porque el
frontend tendria que conocer tres origenes, y esa es una forma de acoplarse
al despliegue que se paga cada vez que algo se mueve: cambiar un puerto
obligaria a tocar el otro repositorio. Con la puerta, el contrato dice
`http://localhost:8010` y donde vive cada servicio es un detalle del backend.

Sobre la autenticacion. Identidad ya publica `/v1/sesiones*` (correo+clave ->
token con roles, ADR 0013/0016) y la puerta la rutea como cualquier otra. El
`Authorization: Bearer` viaja intacto hacia atras -no esta en
`CABECERAS_SALTADAS`-, y la validacion AUTORITATIVA del token vive en
`GET /v1/sesiones/actual` de Identidad, que es quien tiene la `version_permisos`
vigente para poder revocar. El frontend la consulta en cada render protegido, y
esa consulta pasa por aqui: la puerta ya es parte del camino de validacion.

Lo que esta version **no** hace todavia, y a proposito: repetir esa validacion
localmente para las rutas del pipeline, que hoy no exigen sesion. Forzar el
token en ellas seria construir la mitad del mecanismo -autenticacion sin el
resto de los servicios preparados- y creer que esta completo, que es justo lo
que el Anexo M le reprocha al rediseno. El sitio donde iria ese chequeo local
esta marcado en `_reenviar`. Tampoco limita la tasa aun.

El mapa de prefijos es explicito y no un comodin. Una ruta que no este aqui
devuelve 404 con la lista de las que si existen, en vez de reenviarla a un
servicio al azar y dejar que el error salga seis capas mas abajo.

    python -m tukit_gateway.api            # localhost:8010
"""

from __future__ import annotations

import argparse
import os

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from tukit_comun.http import crear_app

PUERTO_POR_OMISION = 8010

# Generoso porque detras hay un pipeline que tarda minutos. El proxy del
# frontend actual ya convive con eso con una espera de 300 s.
ESPERA_SEGUNDOS = 300.0

# Cabeceras que NO se copian. `host` porque apunta a la puerta y confundiria
# al de atras; las de longitud y codificacion porque httpx las recalcula y
# copiarlas produce respuestas truncadas que parecen un fallo de red.
CABECERAS_SALTADAS = frozenset({"host", "content-length", "transfer-encoding", "connection", "keep-alive"})


def _servicios() -> dict[str, str]:
    return {
        "catalogo": os.environ.get("TUKIT_CATALOGO_URL", "http://127.0.0.1:8012").rstrip("/"),
        "identidad": os.environ.get("TUKIT_IDENTIDAD_URL", "http://127.0.0.1:8011").rstrip("/"),
        "inteligencia": os.environ.get("TUKIT_INTELIGENCIA_URL", "http://127.0.0.1:8013").rstrip("/"),
        "comercio": os.environ.get("TUKIT_COMERCIO_URL", "http://127.0.0.1:8014").rstrip("/"),
        "operacion": os.environ.get("TUKIT_OPERACION_URL", "http://127.0.0.1:8015").rstrip("/"),
    }


# Prefijo de ruta -> servicio que lo atiende. El orden importa: se busca el
# prefijo mas largo primero, para que `/v1/admin/` gane sobre `/v1/`.
RUTAS: dict[str, str] = {
    "/v1/catalogo": "catalogo",
    "/v1/listas": "catalogo",
    # La revision de listas por HTTP la sirve CATALOGO (es su curaduria); la
    # ingesta de PDF y la percepcion las sirve INTELIGENCIA. Ambas cuelgan de
    # `/v1/admin`, asi que las de catalogo se nombran con su prefijo mas largo
    # —`destino` busca el mas largo primero— y `/v1/admin` a secas queda para
    # inteligencia.
    "/v1/admin/listas": "catalogo",
    "/v1/admin/propuestas": "catalogo",
    # La curaduria proactiva del catalogo (cola de propuestas, alta de util y
    # libro, buscar en tienda, aprobar) la sirve CATALOGO bajo este prefijo mas
    # largo. Gana a `/v1/admin` -> inteligencia; `rechazar` sigue yendo a
    # catalogo por `/v1/admin/propuestas`, que ya esta ruteado arriba.
    "/v1/admin/catalogo": "catalogo",
    # El backlog de sugerencias de padres lo escribe CATALOGO (crea la
    # tarea_importacion). Sin este prefijo mas largo caeria en `/v1/admin` e
    # iria a inteligencia, que no la sirve.
    "/v1/admin/sugerencias": "catalogo",
    "/v1/colegios": "identidad",
    "/v1/grados": "identidad",
    "/v1/contactos": "identidad",
    "/v1/sesiones": "identidad",
    # "Mi cuenta" del acudiente: identidad y libreta de direcciones, sobre el
    # token que emite `/v1/sesiones`.
    "/v1/cuenta": "identidad",
    "/v1/trabajos": "inteligencia",
    "/v1/admin": "inteligencia",
    # El panel del colegio: kits armados, cobertura y ahorro, calculados en vivo
    # sobre los kits. Cuelga de `/v1/metricas` y no de `/v1/colegios` (que es de
    # identidad) para que este ruteo por prefijo lo mande a inteligencia.
    "/v1/metricas": "inteligencia",
    # El back-office de logistica (tablero de pedidos) y la bandeja de casos/PQRS.
    "/v1/comercio": "comercio",
    "/v1/operacion": "operacion",
    # El checkout del acudiente y el webhook de la pasarela: ya tienen detras la
    # superficie de escritura de Comercio (§9), asi que salen de PENDIENTES.
    "/v1/ordenes": "comercio",
    "/v1/webhooks/wompi": "comercio",
}


# Rutas que el contrato define y que todavia no tiene nadie detras. Se
# responden con 501 y con la seccion del contrato donde estan especificadas,
# en vez de con el 404 de "esa ruta no existe".
#
# La diferencia le importa a quien integra: un 404 dice "te equivocaste de
# URL" y manda a revisar el cliente; un 501 dice "la URL es la correcta y el
# backend todavia no la sirve" y manda a esperar. Confundirlas cuesta una
# tarde de buscar un error que no esta.
PENDIENTES: dict[str, str] = {}


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


app = crear_app(
    titulo="Tukit Gateway",
    descripcion=(
        "Unica URL base del backend. Rutea por prefijo hacia catalogo, identidad e "
        "inteligencia. Contrato: arquitectura/CONTRATO_API.md seccion 12.1."
    ),
)


@app.get("/v1/servicios", tags=["salud"], summary="Que hay detras y si responde")
async def servicios() -> dict[str, object]:
    """Una sonda que dice la verdad sobre los tres, no solo sobre la puerta.

    Sin esto, `GET /salud` en la puerta responde `ok` con los tres servicios
    caidos, que es la clase de sonda que hace perder una tarde.
    """
    estado = {}
    async with httpx.AsyncClient(timeout=5.0) as cliente:
        for nombre, base in _servicios().items():
            try:
                respuesta = await cliente.get(f"{base}/salud")
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
    seccion = pendiente(camino)
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

    nombre = destino(camino)
    if nombre is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "ruta_desconocida",
                "mensaje": f"La puerta no atiende {camino}.",
                "rutas": sorted(RUTAS),
            },
        )

    base = _servicios()[nombre]
    cabeceras = {k: v for k, v in peticion.headers.items() if k.lower() not in CABECERAS_SALTADAS}
    cuerpo = await peticion.body()

    # Aqui va la validacion del token y la comparacion de `version_permisos`
    # cuando exista autenticacion. Es el unico punto por el que pasa todo el
    # trafico, que es lo que hace que ponerla aqui sirva de algo.
    try:
        async with httpx.AsyncClient(timeout=ESPERA_SEGUNDOS) as cliente:
            respuesta = await cliente.request(
                peticion.method,
                f"{base}{camino}",
                params=dict(peticion.query_params),
                headers=cabeceras,
                content=cuerpo,
            )
    except httpx.HTTPError as error:
        # 503 y no 502: el de atras no fallo, no esta. La distincion le dice
        # a quien opera si hay que mirar un log o levantar un proceso.
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

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
