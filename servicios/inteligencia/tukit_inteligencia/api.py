"""El recurso `trabajo` y la cola de revision, tal como los fija el contrato.

`POST /v1/trabajos` devuelve 202 y no el kit, y esa es la decision de diseno
que ordena todo lo demas. El pipeline tarda minutos (OP-03 pide precision por
encima de velocidad) y ademas el flujo exige una pausa humana antes de que el
acudiente vea nada (AD-03 a AD-06). Una API sincronica no puede modelar una
espera que incluye a una persona, asi que el recurso central es el trabajo:
se crea, se consulta, y cuando termina se avisa.

Dos cosas de esta version que conviene tener a mano al leer el codigo:

- La ejecucion de fondo es una tarea del mismo proceso. Es lo que permite
  levantar todo con un comando y es tambien lo primero que hay que cambiar:
  ver la nota de `trabajos.lanzar`.
- `TUKIT_AUTOPUBLICAR` salta la revision humana. Existe para que el frontend
  pueda ver kits mientras se construye la pantalla de Admin, y se anuncia a
  gritos al arrancar porque una valvula silenciosa acaba puesta en
  produccion.

    python -m tukit_inteligencia.api        # localhost:8013
"""

from __future__ import annotations

import argparse
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app

from . import trabajos
from .modelos import EstadoResolucion, EstadoTrabajo
from .remoto import url_catalogo, url_identidad

PUERTO_POR_OMISION = 8013


class Hijo(BaseModel):
    """Un hijo del hogar. `referencia` la pone el acudiente, no el sistema.

    No lleva nombre de menor a proposito: para armar un kit basta con saber
    de que colegio y grado es la lista, y pedir el nombre seria recoger un
    dato de menor que el flujo no necesita. La referencia ("hijo-1") es lo
    que permite devolver las lineas agrupadas.
    """

    referencia: str = Field(min_length=1, max_length=64)
    colegio_id: str = Field(min_length=1, max_length=64)
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int | None = Field(default=None, ge=2020, le=2100)


class Contacto(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    celular: str | None = Field(default=None, max_length=32)


class Preferencias(BaseModel):
    """Lo que el acudiente declara. NO se pide el estrato.

    En las 60 respuestas de la encuesta, 41 son estrato 4: no tiene varianza
    suficiente para segmentar y si es dato sensible del hogar de un menor.
    Como ademas la correlacion intuitiva no existe (el segmento que mas gasta
    es el MENOS dispuesto a pagar sobreprecio), quitarlo no cuesta precision.
    """

    pesos: dict[str, float] | None = None
    # Cota DURA, no una pista. Es el uso mas valioso de la encuesta: convierte
    # una opinion en una restriccion que el optimizador puede imponer.
    presupuesto_por_hijo: int | None = Field(default=None, gt=0)
    disposicion_sobreprecio: float | None = Field(default=None, ge=0, le=1)
    personaje_por_hijo: dict[str, list[str]] | None = None
    dolor_declarado: str | None = Field(default=None, max_length=64)


class PeticionTrabajo(BaseModel):
    hijos: list[Hijo] = Field(min_length=1)
    contacto: Contacto | None = None
    preferencias: Preferencias | None = None


class DecisionLinea(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    motivo: str | None = Field(default=None, max_length=512)
    actor: uuid.UUID | None = None


class DecisionRevision(BaseModel):
    decision: str = Field(pattern="^(aprobar|devolver)$")
    nota: str | None = Field(default=None, max_length=1024)
    actor: uuid.UUID | None = None


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("inteligencia")
    if trabajos.autopublicar():
        print(
            "[inteligencia] TUKIT_AUTOPUBLICAR esta activo: los trabajos se publican SIN "
            "revision humana. Es un atajo de desarrollo y no debe estar puesto fuera de el."
        )
    print(f"[inteligencia] catalogo en {url_catalogo()}, identidad en {url_identidad()}")


async def _apagar(app: FastAPI) -> None:
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


@app.post("/v1/trabajos", tags=["trabajos"], status_code=202, summary="Crea un trabajo y lo encola")
async def crear_trabajo(peticion: PeticionTrabajo) -> dict[str, Any]:
    """La peticion es por HOGAR y no por hijo.

    Es lo que hace posible la consolidacion entre hermanos y el reparto de
    empaques: si cada hijo se pidiera aparte, el optimizador no podria ver
    que dos ninos necesitan un borrador cada uno y que una caja de diez sale
    mejor.
    """
    referencias = [hijo.referencia for hijo in peticion.hijos]
    if len(set(referencias)) != len(referencias):
        raise ErrorDominio(
            "referencias_repetidas",
            "Cada hijo necesita una referencia distinta: es con lo que se agrupan sus lineas.",
            campo="hijos",
        )

    pesos = (peticion.preferencias.pesos if peticion.preferencias else None) or {}
    if pesos and abs(sum(pesos.values()) - 1.0) > 0.01:
        raise ErrorDominio(
            "pesos_no_suman_uno",
            "Los pesos de las preferencias tienen que sumar 1.0.",
            estado=422,
            campo="preferencias.pesos",
        )

    respuesta = await trabajos.crear(
        app.state.motor,
        hijos=[hijo.model_dump() for hijo in peticion.hijos],
        contacto=peticion.contacto.model_dump() if peticion.contacto else None,
        preferencias=(peticion.preferencias.model_dump(exclude_none=True) if peticion.preferencias else {}),
    )
    trabajos.lanzar(app.state.motor, uuid.UUID(respuesta["trabajo_id"]))
    return respuesta


@app.get("/v1/trabajos/{trabajo_id}", tags=["trabajos"], summary="Estado, etapas y kits del trabajo")
async def ver_trabajo(trabajo_id: uuid.UUID) -> dict[str, Any]:
    try:
        return await trabajos.ver(app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error


@app.post(
    "/v1/trabajos/{trabajo_id}/reintentar",
    tags=["trabajos"],
    summary="Vuelve a correr un trabajo fallido, sin repetir lo que ya estaba bien",
)
async def reintentar(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Existe porque un trabajo fallido con diagnostico es reintentable.

    Es la contraparte de la seccion 8: si Gemini o el catalogo no
    respondieron, el trabajo quedo guardado con su error y el acudiente no
    tiene que volver a subir nada.
    """
    try:
        actual = await trabajos.ver(app.state.motor, trabajo_id)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error

    if actual["estado"] not in {EstadoTrabajo.FALLIDO.value, EstadoTrabajo.ENCOLADO.value}:
        raise ErrorDominio(
            "estado_incompatible",
            f"Solo se reintenta un trabajo fallido o encolado, y este esta en {actual['estado']}.",
            estado=409,
        )

    trabajos.lanzar(app.state.motor, trabajo_id)
    return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.ENCOLADO.value}


# ---------------------------------------------------------------------------
# Revision humana (apps/admin)
# ---------------------------------------------------------------------------


@app.get("/v1/admin/cola", tags=["admin"], summary="AD-02, AD-03: trabajos esperando a una persona")
async def cola(
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await trabajos.cola(app.state.motor, pagina=pagina, por_pagina=por_pagina)


@app.get(
    "/v1/admin/trabajos/{trabajo_id}",
    tags=["admin"],
    summary="AD-03: el trabajo CON sus kits, aunque todavia no este publicado",
)
async def ver_admin(trabajo_id: uuid.UUID) -> dict[str, Any]:
    """Mismo lector que el del acudiente, con los kits forzados.

    El acudiente no ve un kit sin revisar; Admin tiene que verlo, porque su
    trabajo es justamente revisarlo. Es la misma consulta con una bandera, y
    no dos lectores distintos que se puedan desincronizar.
    """
    try:
        return await trabajos.ver(app.state.motor, trabajo_id, incluir_kits=True)
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error


@app.post(
    "/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/validar",
    tags=["admin"],
    summary="AD-04: una persona da por bueno el emparejamiento",
)
async def validar_linea(trabajo_id: uuid.UUID, item_id: uuid.UUID, decision: DecisionLinea) -> dict[str, Any]:
    try:
        return await trabajos.decidir_linea(
            app.state.motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.RESUELTO_AUTO.value,
            sku=decision.sku,
            actor=decision.actor,
            motivo=decision.motivo,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese trabajo no tiene esa linea.", estado=404) from error


@app.post(
    "/v1/admin/trabajos/{trabajo_id}/lineas/{item_id}/sin-coincidencia",
    tags=["admin"],
    summary="AD-04: una persona declara que el catalogo no lo tiene",
)
async def sin_coincidencia(
    trabajo_id: uuid.UUID, item_id: uuid.UUID, decision: DecisionLinea
) -> dict[str, Any]:
    """Marca `HUECO_CATALOGO` y no `SIN_MATCH`, y la diferencia importa.

    Si una persona miro la linea, entendio que pedia y concluyo que no lo
    tenemos, eso es un hueco de catalogo: "te entendi y no lo tengo".
    `SIN_MATCH` significa "no te entendi", y despues de una revision humana
    esa ya no es la verdad. Solo el primero se puede responder con una
    alternativa o con una disculpa util, y solo el primero alimenta la
    metrica de que le falta al catalogo.
    """
    try:
        return await trabajos.decidir_linea(
            app.state.motor,
            trabajo_id,
            item_id,
            estado=EstadoResolucion.HUECO_CATALOGO.value,
            actor=decision.actor,
            motivo=decision.motivo,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio("linea_no_existe", "Ese trabajo no tiene esa linea.", estado=404) from error


@app.post(
    "/v1/admin/trabajos/{trabajo_id}/revision",
    tags=["admin"],
    summary="AD-06: aprobar publica al acudiente, devolver reabre sin avisar",
)
async def revisar(trabajo_id: uuid.UUID, decision: DecisionRevision) -> dict[str, Any]:
    try:
        resultado = await trabajos.revisar(
            app.state.motor,
            trabajo_id,
            decision=decision.decision,
            nota=decision.nota,
            actor=decision.actor,
        )
    except trabajos.TrabajoNoExiste as error:
        raise ErrorDominio(
            "trabajo_no_existe", "No hay ningun trabajo con ese identificador.", estado=404
        ) from error
    except trabajos.TransicionIlegal as error:
        raise ErrorDominio(
            "estado_incompatible",
            f"Un trabajo en {error.actual} no se puede pasar a {error.pedida}.",
            estado=409,
        ) from error

    if decision.decision == "devolver":
        trabajos.lanzar(app.state.motor, trabajo_id)
    return resultado


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
