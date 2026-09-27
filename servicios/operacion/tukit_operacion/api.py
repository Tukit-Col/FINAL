"""La superficie de Operacion: la bandeja de casos y el alta de una PQRS.

Dos superficies, como en el contrato (`libs/ts/tukit-contrato/src/operacion.ts`):

- **Lectura** (`GET /v1/operacion/casos`, `/{id}`): la bandeja del back-office.
  `BandejaOperacion {resumen, casos[]}`, ordenada por prioridad y luego por
  vencimiento, que es como el operador entra: lo urgente y lo que vence primero.
- **Escritura** (`POST /v1/operacion/casos`): lo que un acudiente manda desde el
  centro de ayuda. La categoria tiene que estar en `CATEGORIAS_CASO_ACUDIENTE`
  (las fallas de la saga las abre el sistema, no una persona) o se rechaza con
  422. El contacto NO se persiste: se resuelve a un `usuario_id` contra
  Identidad. `vence_en` sale de la tabla de SLA por categoria (Ley 1755).

    python -m tukit_operacion.api            # localhost:8015
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app
from tukit_comun.http import iso as _iso

from .modelos import (
    CATEGORIAS_CASO_ACUDIENTE,
    ORDEN_PRIORIDAD,
    PRIORIDAD_POR_CATEGORIA,
    SLA_HORAS,
    Base,
    CategoriaCaso,
    EstadoCaso,
    OrigenCaso,
    Prioridad,
)
from .remoto import ClienteIdentidad

PUERTO_POR_OMISION = 8015

CASO = Base.metadata.tables["caso"]
METRICA = Base.metadata.tables["metrica_diaria"]


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("operacion")
    # El cliente de Identidad se cuelga de la app para poder sustituirlo en las
    # pruebas sin tocar el endpoint.
    app.state.identidad = ClienteIdentidad()


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Operacion",
    descripcion=(
        "Casos, PQRS, notificaciones, auditoria y telemetria. Bandeja del back-office y "
        "alta de PQRS del acudiente. El contacto se resuelve a un id en Identidad, no se guarda."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)


def _serializar_caso(fila: Any) -> dict[str, Any]:
    return {
        "caso_id": str(fila.id),
        "origen": fila.origen,
        "categoria": fila.categoria,
        "estado": fila.estado,
        "prioridad": fila.prioridad,
        "asunto": fila.asunto,
        "abierto_en": _iso(fila.abierto_en),
        "vence_en": _iso(fila.vence_en),
        "trabajo_id": str(fila.trabajo_id) if fila.trabajo_id is not None else None,
        "pedido_id": str(fila.pedido_id) if fila.pedido_id is not None else None,
        "asignado_a": str(fila.asignado_a_id) if fila.asignado_a_id is not None else None,
    }


def _clave_orden(fila: Any) -> tuple[int, float]:
    """Prioridad primero (urgente arriba), luego vencimiento mas cercano.

    Se ordena en Python y no en SQL porque el rango de prioridad es un dato del
    dominio (`ORDEN_PRIORIDAD`) y no una columna: mantenerlo en un solo sitio
    evita que el orden de la bandeja y el de la etiqueta se desincronicen. Un
    caso sin `vence_en` va al final de su grupo de prioridad.
    """
    try:
        rango = ORDEN_PRIORIDAD[Prioridad(fila.prioridad)]
    except ValueError:
        rango = 99
    vence = fila.vence_en.timestamp() if fila.vence_en is not None else float("inf")
    return (rango, vence)


async def _resumen(conexion: Any, ahora: datetime) -> dict[str, Any]:
    inactivos = tuple(e.value for e in EstadoCaso.inactivos())
    fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
    hace_una_semana = ahora - timedelta(days=7)

    abiertos = await conexion.scalar(select(func.count()).where(CASO.c.estado.notin_(inactivos)))
    urgentes = await conexion.scalar(
        select(func.count()).where(
            CASO.c.estado.notin_(inactivos), CASO.c.prioridad == Prioridad.URGENTE.value
        )
    )
    vencen_hoy = await conexion.scalar(
        select(func.count()).where(
            CASO.c.estado.notin_(inactivos),
            CASO.c.vence_en.is_not(None),
            CASO.c.vence_en <= fin_dia,
        )
    )
    resueltos_semana = await conexion.scalar(
        select(func.count()).where(CASO.c.resuelto_en.is_not(None), CASO.c.resuelto_en >= hace_una_semana)
    )
    return {
        "abiertos": int(abiertos or 0),
        "urgentes": int(urgentes or 0),
        "vencen_hoy": int(vencen_hoy or 0),
        "resueltos_semana": int(resueltos_semana or 0),
    }


@app.get("/v1/operacion/casos", tags=["operacion"], summary="Bandeja: resumen + casos ordenados")
async def bandeja() -> dict[str, Any]:
    ahora = datetime.now(UTC)
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        resumen = await _resumen(conexion, ahora)
        filas = list(await conexion.execute(select(CASO)))
    casos = [_serializar_caso(f) for f in sorted(filas, key=_clave_orden)]
    return {"resumen": resumen, "casos": casos}


@app.get("/v1/operacion/casos/{caso_id}", tags=["operacion"], summary="Un caso")
async def ver_caso(caso_id: uuid.UUID) -> dict[str, Any]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        fila = (await conexion.execute(select(CASO).where(CASO.c.id == caso_id))).one_or_none()
        if fila is None:
            raise ErrorDominio("caso_no_existe", "No hay ningun caso con ese identificador.", estado=404)
        return _serializar_caso(fila)


@app.get(
    "/v1/operacion/metricas",
    tags=["operacion"],
    summary="Series de las metricas de calidad congeladas por dia (metrica_diaria)",
)
async def metricas_series(
    dimension: Annotated[
        str | None, Query(description="Filtra por dimension: catalogo, colegio, global")
    ] = None,
    dimension_id: Annotated[
        str | None, Query(description="Acota a un id dentro de la dimension (ej. un colegio)")
    ] = None,
    desde: Annotated[str | None, Query(description="Fecha ISO minima (inclusive)")] = None,
) -> dict[str, Any]:
    """Las metricas punto-en-el-tiempo que `instantanea` congela cada dia.

    El panel del operador las pide para pintar la traza de "como mejora el
    algoritmo por dia". Devuelve las filas crudas (fecha, dimension, id, metrica,
    valor) ordenadas por fecha; el frontend las agrupa por metrica en series. Sin
    snapshots aun, `puntos` viene vacio: es una respuesta valida, no un 404.
    """
    consulta = select(
        METRICA.c.fecha,
        METRICA.c.dimension,
        METRICA.c.dimension_id,
        METRICA.c.metrica,
        METRICA.c.valor,
    ).order_by(METRICA.c.fecha, METRICA.c.dimension, METRICA.c.metrica)
    if dimension:
        consulta = consulta.where(METRICA.c.dimension == dimension)
    if dimension_id:
        consulta = consulta.where(METRICA.c.dimension_id == dimension_id)
    if desde:
        try:
            limite = datetime.fromisoformat(desde).date()
        except ValueError:
            raise ErrorDominio(
                "fecha_invalida", "`desde` va como fecha ISO (YYYY-MM-DD).", estado=422, campo="desde"
            ) from None
        consulta = consulta.where(METRICA.c.fecha >= limite)

    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        filas = list(await conexion.execute(consulta))

    puntos = [
        {
            "fecha": f.fecha.isoformat(),
            "dimension": f.dimension,
            "dimension_id": f.dimension_id,
            "metrica": f.metrica,
            "valor": int(f.valor),
        }
        for f in filas
    ]
    return {"puntos": puntos}


class Contacto(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    celular: str = Field(min_length=1, max_length=32)


class SolicitudCaso(BaseModel):
    """Lo que un acudiente manda para abrir una PQRS. `contacto` se resuelve a un
    id y no se guarda; `descripcion` es el cuerpo del caso."""

    categoria: str = Field(max_length=24)
    asunto: str = Field(min_length=1, max_length=256)
    descripcion: str = Field(min_length=1, max_length=4096)
    contacto: Contacto
    trabajo_id: str | None = None


def _vence_en(categoria: CategoriaCaso, desde: datetime) -> datetime | None:
    horas = SLA_HORAS.get(categoria)
    return desde + timedelta(hours=horas) if horas is not None else None


@app.post(
    "/v1/operacion/casos",
    tags=["operacion"],
    status_code=201,
    summary="Abre una PQRS. El contacto se resuelve a un id; no se guarda.",
)
async def abrir_caso(solicitud: SolicitudCaso) -> dict[str, Any]:
    # La categoria tiene que ser una que un acudiente puede abrir. Las fallas de
    # la saga (mapeo_lista, autenticacion, stock) las abre el sistema.
    try:
        categoria = CategoriaCaso(solicitud.categoria)
    except ValueError:
        raise ErrorDominio(
            "categoria_invalida",
            "Esa categoria no existe.",
            estado=422,
            campo="categoria",
        ) from None
    if categoria not in CATEGORIAS_CASO_ACUDIENTE:
        raise ErrorDominio(
            "categoria_no_permitida",
            "Esa categoria la abre el sistema, no se puede elegir desde el centro de ayuda.",
            estado=422,
            campo="categoria",
        )

    trabajo_id = None
    if solicitud.trabajo_id:
        try:
            trabajo_id = uuid.UUID(solicitud.trabajo_id)
        except ValueError:
            raise ErrorDominio(
                "trabajo_invalido",
                "El identificador de trabajo no tiene forma valida.",
                estado=422,
                campo="trabajo_id",
            ) from None

    # El contacto se resuelve a un usuario_id en Identidad y NO se persiste. Si
    # Identidad esta caida, el caso se abre igual sin titular (usuario_id nulo).
    usuario_id_texto = await app.state.identidad.resolver_contacto(
        solicitud.contacto.correo, solicitud.contacto.celular
    )
    usuario_id = uuid.UUID(usuario_id_texto) if usuario_id_texto else None

    ahora = datetime.now(UTC)
    caso_id = uuid.uuid4()
    prioridad = PRIORIDAD_POR_CATEGORIA.get(categoria, Prioridad.MEDIA)
    vence = _vence_en(categoria, ahora)

    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            insert(CASO).values(
                id=caso_id,
                origen=OrigenCaso.ACUDIENTE.value,
                categoria=categoria.value,
                estado=EstadoCaso.ABIERTO.value,
                prioridad=prioridad.value,
                asunto=solicitud.asunto,
                descripcion=solicitud.descripcion,
                usuario_id=usuario_id,
                trabajo_id=trabajo_id,
                abierto_en=ahora,
                vence_en=vence,
            )
        )

    return {
        "caso_id": str(caso_id),
        "estado": EstadoCaso.ABIERTO.value,
        "categoria": categoria.value,
        "recibido_en": _iso(ahora),
        "vence_en": _iso(vence),
    }


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Operacion.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
