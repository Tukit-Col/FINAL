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
    estado_tras_respuesta,
    prioridad_inicial,
    validar_cambio_estado,
    validar_respuesta,
    vence_en,
)
from ..modelos import EstadoCaso
from ..remoto import IdentidadCaida
from ..repositorios import RepoCasos
from ..repositorios.casos import serializar_caso, serializar_detalle_caso

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
# Sesion: quien llama al back-office. Misma puerta y mismos sobres que comercio
# (`_exigir_staff`), para que el front trate igual un 401/403/503 de cualquier
# servicio. Operacion no lee la base de Identidad: pregunta por HTTP.
# ---------------------------------------------------------------------------

# Los roles del equipo interno; el admin es superconjunto del operador.
_ROLES_STAFF = frozenset({"admin", "operador"})


def _token_bearer(authorization: str | None) -> str | None:
    """El token del encabezado `Authorization`: `Bearer <token>` o el token pelado."""
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


async def _exigir_staff(request: Request, authorization: str | None) -> uuid.UUID:
    """Puerta operador/admin: 401 sin token o con uno invalido, 503 si Identidad
    no responde (FALLA CERRADA: no se autoriza por no poder preguntar), 403 si el
    rol no es staff. Devuelve el `usuario_id` de la sesion, que queda como actor."""
    token = _token_bearer(authorization)
    if not token:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    try:
        sesion = await request.app.state.identidad.sesion(token)
    except IdentidadCaida as error:
        raise ErrorDominio("identidad_no_disponible", "No se pudo validar la sesion.", estado=503) from error
    if sesion is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    roles = {r.get("rol") for r in sesion.get("roles", [])}
    if not roles & _ROLES_STAFF:
        raise ErrorDominio(
            "acceso_denegado", "Esta vista es solo para el equipo interno de Tukit.", estado=403
        )
    return uuid.UUID(str(sesion["usuario_id"]))


_MENSAJE_CAMBIO = {
    "estado_invalido": "Ese estado no existe.",
    "transicion_invalida": "No se puede pasar el ticket a ese estado desde el actual.",
    "caso_cerrado": "El ticket esta cerrado: no admite respuestas.",
    "respuesta_vacia": "Escribe la respuesta.",
    "respuesta_larga": "La respuesta es demasiado larga.",
}


def _rechazar(rechazo: Any) -> ErrorDominio:
    return ErrorDominio(
        rechazo.razon,
        _MENSAJE_CAMBIO.get(rechazo.razon, "El cambio no procede."),
        estado=rechazo.estado,
        campo=rechazo.campo,
    )


async def _caso_o_404(repo: RepoCasos, caso_id: uuid.UUID) -> Any:
    fila = await repo.obtener(caso_id)
    if fila is None:
        raise ErrorDominio("caso_no_existe", "No hay ningun caso con ese identificador.", estado=404)
    return fila


async def _detalle_staff(repo: RepoCasos, fila: Any) -> dict[str, Any]:
    return serializar_detalle_caso(fila) | {"eventos": await repo.eventos_de(fila.id)}


# ---------------------------------------------------------------------------
# Lectura: bandeja del back-office y series de metricas
# ---------------------------------------------------------------------------


@router.get("/v1/operacion/casos", summary="Bandeja: resumen + casos ordenados. Solo staff.")
async def bandeja(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    await _exigir_staff(request, authorization)
    ahora = datetime.now(UTC)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        resumen = await repo.resumen(ahora)
        filas = await repo.listar_casos()
    ordenadas = sorted(filas, key=lambda f: clave_orden(f.prioridad, f.vence_en))
    casos = [serializar_caso(f) for f in ordenadas]
    return {"resumen": resumen, "casos": casos}


@router.get("/v1/operacion/casos/{caso_id}", summary="Un caso con su conversacion. Solo staff.")
async def ver_caso(
    request: Request, caso_id: uuid.UUID, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    await _exigir_staff(request, authorization)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        return await _detalle_staff(repo, await _caso_o_404(repo, caso_id))


class SolicitudRespuesta(BaseModel):
    """La respuesta del equipo al acudiente. Texto plano; el limite lo valida el dominio."""

    texto: str = Field(max_length=4096)


class SolicitudEstado(BaseModel):
    destino: str = Field(min_length=1, max_length=24)


class SolicitudVinculo(BaseModel):
    pedido_id: str


@router.post("/v1/operacion/casos/{caso_id}/responder", summary="Responde al acudiente. Solo staff.")
async def responder_caso(
    request: Request,
    caso_id: uuid.UUID,
    solicitud: SolicitudRespuesta,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Guarda la respuesta en la historia del caso y encola el aviso al acudiente,
    todo en UNA unidad de trabajo (o se guardan las dos cosas o ninguna). Un caso
    recien abierto pasa a `en_gestion`. Sin titular resuelto (Identidad estaba
    caida al abrirlo) la respuesta se guarda pero no hay a quien avisar."""
    actor = await _exigir_staff(request, authorization)
    ahora = datetime.now(UTC)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        fila = await _caso_o_404(repo, caso_id)
        texto, rechazo = validar_respuesta(fila.estado, solicitud.texto)
        if rechazo is not None or texto is None:
            raise _rechazar(rechazo)
        await repo.registrar_evento(
            caso_id=caso_id, tipo="respuesta", datos={"texto": texto}, actor_id=actor, ahora=ahora
        )
        nuevo = estado_tras_respuesta(fila.estado)
        if nuevo != fila.estado:
            await repo.cambiar_estado(caso_id=caso_id, desde=fila.estado, hacia=nuevo, resuelto_en=None)
            await repo.registrar_evento(
                caso_id=caso_id,
                tipo="estado",
                datos={"desde": fila.estado, "hacia": nuevo},
                actor_id=actor,
                ahora=ahora,
            )
        avisado = fila.usuario_id is not None
        if avisado:
            await repo.encolar_respuesta(caso_id=caso_id, usuario_id=fila.usuario_id)
        await repo.auditar(
            actor_id=actor, accion="caso_respondido", caso_id=caso_id, datos={"avisado": avisado}, ahora=ahora
        )
        return await _detalle_staff(repo, await _caso_o_404(repo, caso_id))


@router.post("/v1/operacion/casos/{caso_id}/estado", summary="Cambia el estado del ticket. Solo staff.")
async def cambiar_estado_caso(
    request: Request,
    caso_id: uuid.UUID,
    solicitud: SolicitudEstado,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    actor = await _exigir_staff(request, authorization)
    ahora = datetime.now(UTC)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        fila = await _caso_o_404(repo, caso_id)
        rechazo = validar_cambio_estado(fila.estado, solicitud.destino)
        if rechazo is not None:
            raise _rechazar(rechazo)
        inactivo = solicitud.destino in {e.value for e in EstadoCaso.inactivos()}
        # `resuelto_en` marca la primera vez que se resolvio; cerrar un ya resuelto lo conserva.
        resuelto_en = (fila.resuelto_en or ahora) if inactivo else None
        movido = await repo.cambiar_estado(
            caso_id=caso_id, desde=fila.estado, hacia=solicitud.destino, resuelto_en=resuelto_en
        )
        if not movido:
            # Otro operador lo movio mientras tanto; lanzar revierte la unidad de trabajo.
            raise ErrorDominio(
                "cambio_concurrente",
                "Alguien mas movio este ticket mientras tanto; recarga y vuelve a intentar.",
                estado=409,
            )
        datos = {"desde": fila.estado, "hacia": solicitud.destino}
        await repo.registrar_evento(caso_id=caso_id, tipo="estado", datos=datos, actor_id=actor, ahora=ahora)
        await repo.auditar(actor_id=actor, accion="caso_estado", caso_id=caso_id, datos=datos, ahora=ahora)
        return await _detalle_staff(repo, await _caso_o_404(repo, caso_id))


@router.post("/v1/operacion/casos/{caso_id}/pedido", summary="Vincula el ticket a un pedido. Solo staff.")
async def vincular_pedido(
    request: Request,
    caso_id: uuid.UUID,
    solicitud: SolicitudVinculo,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Deja el `pedido_id` en el caso (referencia logica; Comercio es el dueno del pedido)."""
    actor = await _exigir_staff(request, authorization)
    try:
        pedido_id = uuid.UUID(solicitud.pedido_id)
    except ValueError:
        raise ErrorDominio(
            "identificador_invalido", "El pedido no tiene forma de identificador.", estado=422, campo="pedido_id"
        ) from None
    ahora = datetime.now(UTC)
    async with request.app.state.motor.sesion() as db:
        repo = RepoCasos(await db.connection())
        await _caso_o_404(repo, caso_id)
        await repo.vincular_pedido(caso_id=caso_id, pedido_id=pedido_id)
        await repo.registrar_evento(
            caso_id=caso_id, tipo="pedido", datos={"pedido_id": str(pedido_id)}, actor_id=actor, ahora=ahora
        )
        return await _detalle_staff(repo, await _caso_o_404(repo, caso_id))


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
