"""Las rutas de Operacion: parsear, llamar al dominio, delegar al repo.

Dos superficies, como en el contrato (`libs/ts/tukit-contrato/src/operacion.ts`):

- **Lectura** (`GET /v1/operacion/casos`, `/{id}`, `/metricas`): la bandeja del
  back-office, ordenada por prioridad y luego por vencimiento, y las series de
  metricas de calidad congeladas por dia.
- **Escritura** (`POST /v1/operacion/casos`): lo que un acudiente manda desde el
  centro de ayuda. La categoria tiene que estar en `CATEGORIAS_CASO_ACUDIENTE` o
  se rechaza con 422; el contacto NO se persiste: se resuelve a un `usuario_id`
  contra Identidad, y `vence_en` sale del SLA por categoria (Ley 1755).

El router no calcula ni arma SQL: `admitir_categoria_acudiente`/`vence_en`/
`prioridad_inicial`/`clave_orden` viven en `dominio/`, y todo el SQL en
`repositorios/`. Aqui solo se parsea la entrada (incluidos los 422 de forma), se
orquesta la resolucion de contacto y se traducen los resultados a sobres de
error.

Los singletons (`motor`, `identidad`) se leen de `request.app.state` en cada
peticion, no se capturan al importar: asi las pruebas pueden sustituir los
dobles despues de construir la app.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, Field
from tukit_comun.http import ErrorDominio
from tukit_comun.http import iso as _iso

from ..dominio.casos import (
    CategoriaRechazada,
    admitir_categoria_acudiente,
    clave_orden,
    prioridad_inicial,
    vence_en,
)
from ..modelos import EstadoCaso
from ..remoto import IdentidadCaida
from ..repositorios import RepoCasos
from ..repositorios.casos import serializar_caso

router = APIRouter(tags=["operacion"])

# El mensaje humano de cada rechazo de categoria; la razon estable la pone el
# dominio, el sobre HTTP lo arma el router (ADR 0019).
_MENSAJE_CATEGORIA = {
    "categoria_invalida": "Esa categoria no existe.",
    "categoria_no_permitida": (
        "Esa categoria la abre el sistema, no se puede elegir desde el centro de ayuda."
    ),
}


# ---------------------------------------------------------------------------
# Lectura: bandeja del back-office y series de metricas
# ---------------------------------------------------------------------------


@router.get("/v1/operacion/casos", summary="Bandeja: resumen + casos ordenados")
async def bandeja(request: Request) -> dict[str, Any]:
    ahora = datetime.now(UTC)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        resumen = await repo.resumen(ahora)
        filas = await repo.listar_casos()
    ordenadas = sorted(filas, key=lambda f: clave_orden(f.prioridad, f.vence_en))
    casos = [serializar_caso(f) for f in ordenadas]
    return {"resumen": resumen, "casos": casos}


@router.get("/v1/operacion/casos/{caso_id}", summary="Un caso")
async def ver_caso(request: Request, caso_id: uuid.UUID) -> dict[str, Any]:
    async with request.app.state.motor.sesion() as db:
        fila = await RepoCasos(await db.connection()).obtener(caso_id)
        if fila is None:
            raise ErrorDominio("caso_no_existe", "No hay ningun caso con ese identificador.", estado=404)
        return serializar_caso(fila)


@router.get(
    "/v1/operacion/metricas",
    summary="Series de las metricas de calidad congeladas por dia (metrica_diaria)",
)
async def metricas_series(
    request: Request,
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
    limite = None
    if desde:
        try:
            limite = datetime.fromisoformat(desde).date()
        except ValueError:
            raise ErrorDominio(
                "fecha_invalida", "`desde` va como fecha ISO (YYYY-MM-DD).", estado=422, campo="desde"
            ) from None

    async with request.app.state.motor.sesion() as db:
        filas = await RepoCasos(await db.connection()).serie_metricas(
            dimension=dimension, dimension_id=dimension_id, desde=limite
        )

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


# ---------------------------------------------------------------------------
# Escritura: alta de una PQRS del acudiente
# ---------------------------------------------------------------------------


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


@router.post(
    "/v1/operacion/casos",
    status_code=201,
    summary="Abre una PQRS. El contacto se resuelve a un id; no se guarda.",
)
async def abrir_caso(request: Request, solicitud: SolicitudCaso) -> dict[str, Any]:
    # La categoria tiene que ser una que un acudiente puede abrir. Las fallas de
    # la saga (mapeo_lista, autenticacion, stock) las abre el sistema. El dominio
    # decide; aqui solo se traduce el rechazo al sobre HTTP.
    categoria = admitir_categoria_acudiente(solicitud.categoria)
    if isinstance(categoria, CategoriaRechazada):
        raise ErrorDominio(
            categoria.razon,
            _MENSAJE_CATEGORIA[categoria.razon],
            estado=categoria.estado,
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
    # El await de red va ANTES de abrir la sesion de base: no se sostiene una
    # conexion a traves de una llamada HTTP externa.
    usuario_id_texto = await request.app.state.identidad.resolver_contacto(
        solicitud.contacto.correo, solicitud.contacto.celular
    )
    usuario_id = uuid.UUID(usuario_id_texto) if usuario_id_texto else None

    ahora = datetime.now(UTC)
    caso_id = uuid.uuid4()
    prioridad = prioridad_inicial(categoria)
    vence = vence_en(categoria, ahora)

    async with request.app.state.motor.sesion() as db:
        await RepoCasos(await db.connection()).insertar_caso(
            caso_id=caso_id,
            categoria=categoria.value,
            prioridad=prioridad.value,
            asunto=solicitud.asunto,
            descripcion=solicitud.descripcion,
            usuario_id=usuario_id,
            trabajo_id=trabajo_id,
            abierto_en=ahora,
            vence_en=vence,
        )

    return {
        "caso_id": str(caso_id),
        "estado": EstadoCaso.ABIERTO.value,
        "categoria": categoria.value,
        "recibido_en": _iso(ahora),
        "vence_en": _iso(vence),
    }


# ---------------------------------------------------------------------------
# El acudiente sobre SUS casos: abrir, ver y seguir (dueno = la sesion)
# ---------------------------------------------------------------------------
#
# El dueno sale del token validado contra Identidad, nunca de un campo del
# formulario: con `POST /v1/operacion/casos` cualquiera podia poner el correo de
# otra familia y colgarle el caso. Un caso ajeno responde 403.


def _token_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


async def _usuario_de_sesion(request: Request, authorization: str | None) -> uuid.UUID:
    """El `usuario_id` de la sesion. 401 sin token valido; 503 si Identidad no
    responde (falla cerrada)."""
    token = _token_bearer(authorization)
    if not token:
        raise ErrorDominio("sesion_invalida", "Inicia sesión para ver y abrir tus casos.", estado=401)
    try:
        sesion = await request.app.state.identidad.sesion(token)
    except IdentidadCaida as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesión.", estado=503) from error
    if sesion is None:
        raise ErrorDominio("sesion_invalida", "Tu sesión expiró. Vuelve a ingresar.", estado=401)
    return uuid.UUID(str(sesion["usuario_id"]))


class SolicitudMiCaso(BaseModel):
    """Lo que el acudiente con sesion manda para abrir un caso: sin contacto,
    porque ya se sabe quien es."""

    categoria: str = Field(max_length=24)
    asunto: str = Field(min_length=1, max_length=256)
    descripcion: str = Field(min_length=1, max_length=4096)
    trabajo_id: str | None = None
    pedido_id: str | None = None


class ComentarioCaso(BaseModel):
    texto: str = Field(min_length=1, max_length=1024)


async def _caso_del_portador(repo: RepoCasos, caso_id: uuid.UUID, usuario_id: uuid.UUID) -> Any:
    fila = await repo.obtener(caso_id)
    if fila is None:
        raise ErrorDominio("caso_no_existe", "No hay ningun caso con ese identificador.", estado=404)
    if fila.usuario_id != usuario_id:
        raise ErrorDominio("caso_ajeno", "Este caso no es de tu cuenta.", estado=403)
    return fila


def _uuid_opcional(valor: str | None, campo: str) -> uuid.UUID | None:
    if not valor:
        return None
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorDominio(
            "identificador_invalido", f"El campo {campo} no tiene forma de identificador.", estado=422, campo=campo
        ) from None


@router.get("/v1/operacion/mis-casos", summary="Mis casos: los del portador del token")
async def mis_casos(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    usuario_id = await _usuario_de_sesion(request, authorization)
    async with request.app.state.motor.sesion() as db:
        filas = await RepoCasos(await db.connection()).listar_de_usuario(usuario_id)
    casos = [serializar_caso(f) for f in filas]
    return {"total": len(casos), "casos": casos}


@router.post(
    "/v1/operacion/mis-casos",
    status_code=201,
    summary="Abre una PQRS a nombre de la sesion",
)
async def abrir_mi_caso(
    request: Request, solicitud: SolicitudMiCaso, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    usuario_id = await _usuario_de_sesion(request, authorization)
    categoria = admitir_categoria_acudiente(solicitud.categoria)
    if isinstance(categoria, CategoriaRechazada):
        raise ErrorDominio(
            categoria.razon, _MENSAJE_CATEGORIA[categoria.razon], estado=categoria.estado, campo="categoria"
        )
    trabajo_id = _uuid_opcional(solicitud.trabajo_id, "trabajo_id")
    pedido_id = _uuid_opcional(solicitud.pedido_id, "pedido_id")

    ahora = datetime.now(UTC)
    caso_id = uuid.uuid4()
    vence = vence_en(categoria, ahora)
    async with request.app.state.motor.sesion() as db:
        await RepoCasos(await db.connection()).insertar_caso(
            caso_id=caso_id,
            categoria=categoria.value,
            prioridad=prioridad_inicial(categoria).value,
            asunto=solicitud.asunto,
            descripcion=solicitud.descripcion,
            usuario_id=usuario_id,
            trabajo_id=trabajo_id,
            pedido_id=pedido_id,
            abierto_en=ahora,
            vence_en=vence,
        )
    return {
        "caso_id": str(caso_id),
        "estado": EstadoCaso.ABIERTO.value,
        "categoria": categoria.value,
        "recibido_en": _iso(ahora),
        "vence_en": _iso(vence),
    }


@router.get("/v1/operacion/mis-casos/{caso_id}", summary="Uno de mis casos, con mis mensajes")
async def ver_mi_caso(
    request: Request, caso_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    usuario_id = await _usuario_de_sesion(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        fila = await _caso_del_portador(repo, caso_id, usuario_id)
        return {
            **serializar_caso(fila),
            "descripcion": fila.descripcion,
            "comentarios": await repo.comentarios_de(caso_id),
        }


@router.post(
    "/v1/operacion/mis-casos/{caso_id}/comentarios",
    status_code=201,
    summary="El acudiente agrega un mensaje a uno de sus casos abiertos",
)
async def comentar_mi_caso(
    request: Request,
    caso_id: uuid.UUID,
    comentario: ComentarioCaso,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    usuario_id = await _usuario_de_sesion(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        fila = await _caso_del_portador(repo, caso_id, usuario_id)
        if fila.estado in {e.value for e in EstadoCaso.inactivos()}:
            raise ErrorDominio(
                "caso_cerrado", "Este caso ya está cerrado. Abre uno nuevo si sigue el problema.", estado=409
            )
        await repo.agregar_comentario(caso_id, usuario_id, comentario.texto.strip())
    return {"caso_id": str(caso_id), "recibido_en": _iso(datetime.now(UTC))}
