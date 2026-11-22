from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select

from ..modelos import (
    EstadoResolucion,
    EstadoTrabajo,
)
from ..remoto import ClienteCatalogo, ClienteComercio, RemotoCaido
from ..repositorios.trabajos import TrabajoNoExiste
from .base import (
    IMPORTACION,
    ITEM,
    KIT_CANONICO,
    RESOLUCION,
    TRABAJO,
    SolicitudNoCancelable,
    TrabajoProtegido,
    _estado,
    _pasar_a,
)


async def cola(motor: Any, *, pagina: int = 1, por_pagina: int = 50) -> dict[str, Any]:
    a_revision = (
        select(ITEM.c.trabajo_id.label("tid"), func.count().label("dudosos"))
        .select_from(ITEM.join(RESOLUCION, RESOLUCION.c.item_crudo_id == ITEM.c.id))
        .where(RESOLUCION.c.estado != EstadoResolucion.RESUELTO_AUTO.value)
        .group_by(ITEM.c.trabajo_id)
        .subquery()
    )
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.origen,
            TRABAJO.c.creado_en,
            TRABAJO.c.hijos,
            func.coalesce(a_revision.c.dudosos, 0).label("dudosos"),
        )
        .select_from(TRABAJO.outerjoin(a_revision, a_revision.c.tid == TRABAJO.c.id))
        .where(TRABAJO.c.estado == EstadoTrabajo.ESPERA_REVISION.value)
        .order_by(TRABAJO.c.creado_en)
    )

    async with motor.engine.begin() as conexion:
        total = int(await conexion.scalar(select(func.count()).select_from(consulta.subquery())) or 0)
        filas = await conexion.execute(consulta.limit(por_pagina).offset((pagina - 1) * por_pagina))
        datos = [
            {
                "trabajo_id": str(f.id),
                "estado": f.estado,
                "creado_en": f.creado_en.isoformat() if f.creado_en else None,
                "origen": f.origen,
                "hijos": len(list(f.hijos or ())),
                "colegios": sorted({h["colegio_id"] for h in f.hijos or () if h.get("colegio_id")}),
                "grados": list(dict.fromkeys(h["grado"] for h in f.hijos or () if h.get("grado"))),
                "lineas_a_revisar": int(f.dudosos),
                "edicion_de": next(iter(f.hijos or ()), {}).get("basado_en"),
            }
            for f in filas
        ]
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "trabajos": datos}


def _a_consciente(momento: Any) -> datetime:
    if momento is None:
        return datetime.min.replace(tzinfo=UTC)
    if isinstance(momento, str):
        momento = datetime.fromisoformat(momento)
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


async def mis_solicitudes(motor: Any, usuario_id: uuid.UUID, *, catalogo: Any) -> dict[str, Any]:
    consulta = (
        select(
            TRABAJO.c.id,
            TRABAJO.c.estado,
            TRABAJO.c.origen,
            TRABAJO.c.hijos,
            TRABAJO.c.creado_en,
        )
        .where(TRABAJO.c.usuario_id == usuario_id, TRABAJO.c.estado != EstadoTrabajo.CANCELADO.value)
        .order_by(TRABAJO.c.creado_en.desc())
    )
    pendientes_consulta = (
        select(IMPORTACION.c.colegio_id, IMPORTACION.c.grado, IMPORTACION.c.carga, IMPORTACION.c.creado_en)
        .where(IMPORTACION.c.contacto_referencia == str(usuario_id), IMPORTACION.c.estado == "pendiente")
        .order_by(IMPORTACION.c.creado_en.desc())
    )
    async with motor.engine.begin() as conexion:
        filas = list(await conexion.execute(consulta))
        pendientes = list(await conexion.execute(pendientes_consulta))

    try:
        listas = await catalogo.listas_por_contacto(str(usuario_id))
        listas_disponibles = True
    except RemotoCaido:
        listas = []
        listas_disponibles = False

    trabajo_por_version: dict[str, Any] = {}
    for fila in filas:
        if fila.origen == "lista_verificada":
            hijos = list(fila.hijos or ())
            vid = hijos[0].get("version_id") if hijos else None
            if vid:
                trabajo_por_version[str(vid)] = fila

    solicitudes: list[dict[str, Any]] = []
    versiones_unidas: set[str] = set()

    for lista_subida in listas:
        vid = lista_subida.get("version_id")
        colegio_id = str(lista_subida.get("colegio_id") or "")
        grado = lista_subida.get("grado") or ""
        colegio_nombre = lista_subida.get("colegio_nombre")
        trabajo_ligado = trabajo_por_version.get(str(vid)) if vid else None
        if lista_subida.get("revisada_en") and trabajo_ligado is not None:
            versiones_unidas.add(str(vid))
            solicitudes.append(
                {
                    "tipo": "aprobada",
                    "colegio_id": colegio_id,
                    "colegio_nombre": colegio_nombre,
                    "grado": grado,
                    "trabajo_id": str(trabajo_ligado.id),
                    "creado_en": trabajo_ligado.creado_en.isoformat() if trabajo_ligado.creado_en else None,
                    "_orden": _a_consciente(trabajo_ligado.creado_en),
                }
            )
        else:
            solicitudes.append(
                {
                    "tipo": "recibida",
                    "tarea_id": lista_subida.get("tarea_id"),
                    "colegio_id": colegio_id,
                    "colegio_nombre": colegio_nombre,
                    "grado": grado,
                    "creado_en": lista_subida.get("creada_en"),
                    "_orden": _a_consciente(lista_subida.get("creada_en")),
                }
            )

    for pendiente in pendientes:
        colegio_datos = (pendiente.carga or {}).get("colegio_datos") or {}
        solicitudes.append(
            {
                "tipo": "recibida",
                "tarea_id": None,
                "colegio_id": pendiente.colegio_id,
                "colegio_nombre": colegio_datos.get("nombre"),
                "grado": pendiente.grado,
                "creado_en": _a_consciente(pendiente.creado_en).isoformat(),
                "_orden": _a_consciente(pendiente.creado_en),
            }
        )

    for fila in filas:
        vid = None
        if fila.origen == "lista_verificada":
            hijos = list(fila.hijos or ())
            vid = hijos[0].get("version_id") if hijos else None
        if vid and str(vid) in versiones_unidas:
            continue
        primer = (list(fila.hijos or ()) or [{}])[0]
        solicitudes.append(
            {
                "tipo": "trabajo",
                "colegio_id": str(primer.get("colegio_id") or ""),
                "colegio_nombre": None,
                "grado": primer.get("grado") or "",
                "trabajo_id": str(fila.id),
                "estado": fila.estado,
                "creado_en": fila.creado_en.isoformat() if fila.creado_en else None,
                "_orden": _a_consciente(fila.creado_en),
            }
        )

    solicitudes.sort(key=lambda s: s["_orden"], reverse=True)
    for solicitud in solicitudes:
        del solicitud["_orden"]
    return {"solicitudes": solicitudes, "listas_disponibles": listas_disponibles}


_PEDIDO_SIN_EFECTO = frozenset({"cancelado"})


async def cancelar_solicitud(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    usuario_id: uuid.UUID,
    token: str,
    comercio: ClienteComercio,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    async with motor.engine.begin() as conexion:
        cabeza = (
            await conexion.execute(
                select(TRABAJO.c.estado, TRABAJO.c.usuario_id, TRABAJO.c.origen, TRABAJO.c.hijos).where(
                    TRABAJO.c.id == trabajo_id
                )
            )
        ).one_or_none()
    if cabeza is None:
        raise TrabajoNoExiste(str(trabajo_id))
    if cabeza.usuario_id != usuario_id:
        raise SolicitudNoCancelable("solicitud_ajena", "Esta solicitud no es de tu cuenta.", 403)
    if cabeza.estado == EstadoTrabajo.CANCELADO.value:
        return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.CANCELADO.value}
    if cabeza.estado == EstadoTrabajo.PROCESANDO.value:
        raise SolicitudNoCancelable(
            "en_proceso", "Estamos armando tu kit justo ahora. Intenta cancelarla en un minuto."
        )
    async with motor.engine.begin() as conexion:
        es_canonico = await conexion.scalar(
            select(KIT_CANONICO.c.id).where(KIT_CANONICO.c.trabajo_id == trabajo_id).limit(1)
        )
    if es_canonico is not None:
        raise SolicitudNoCancelable(
            "kit_canonico",
            "Este kit quedó como el kit de referencia de tu colegio y grado, así que no se "
            "cancela. Si no lo necesitas, no tienes que comprarlo.",
        )

    for pedido in await comercio.pedidos_de(token):
        if str(pedido.get("trabajo_id")) != str(trabajo_id) or pedido.get("estado") in _PEDIDO_SIN_EFECTO:
            continue
        if pedido.get("estado") == "pendiente_pago":
            raise SolicitudNoCancelable(
                "pedido_pendiente",
                "Tienes un pedido de este kit esperando pago. Cancélalo primero en Mis pedidos.",
            )
        raise SolicitudNoCancelable(
            "kit_comprado", "Ya compraste este kit, así que la solicitud no se cancela."
        )

    async with motor.engine.begin() as conexion:
        await _pasar_a(conexion, trabajo_id, EstadoTrabajo.CANCELADO.value)

    hijo = (list(cabeza.hijos or ()) or [{}])[0]
    if cabeza.origen == "lista_verificada" and hijo.get("version_id"):
        await catalogo.retirar_de_contacto(str(usuario_id), version_id=str(hijo["version_id"]))
    return {"trabajo_id": str(trabajo_id), "estado": EstadoTrabajo.CANCELADO.value}


async def cancelar_lista_subida(
    usuario_id: uuid.UUID, tarea_id: str, *, catalogo: ClienteCatalogo
) -> dict[str, Any]:
    retiradas = await catalogo.retirar_de_contacto(str(usuario_id), tarea_id=tarea_id)
    return {"tarea_id": tarea_id, "retiradas": retiradas}


async def eliminar(motor: Any, trabajo_id: uuid.UUID) -> None:
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if actual == EstadoTrabajo.PUBLICADO.value:
            raise TrabajoProtegido(actual)
        await conexion.execute(delete(TRABAJO).where(TRABAJO.c.id == trabajo_id))


async def previews_de(motor: Any, colegio_id: str, grado: str, anio_lectivo: int) -> list[uuid.UUID]:
    async with motor.engine.begin() as conexion:
        filas = await conexion.execute(
            select(TRABAJO.c.id, TRABAJO.c.hijos).where(
                TRABAJO.c.origen == "preview_onboarding",
                TRABAJO.c.estado != EstadoTrabajo.PUBLICADO.value,
            )
        )
    coincidencias: list[uuid.UUID] = []
    for fila in filas:
        hijo = next(iter(fila.hijos or ()), None)
        if not hijo:
            continue
        if (
            str(hijo.get("colegio_id") or "") == colegio_id
            and str(hijo.get("grado") or "") == grado
            and int(hijo.get("anio_lectivo") or 0) == anio_lectivo
        ):
            coincidencias.append(fila.id)
    return coincidencias
