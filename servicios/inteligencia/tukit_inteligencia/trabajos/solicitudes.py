"""Cola del operador y panel del acudiente: listar, cancelar y eliminar solicitudes."""

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
    """Los trabajos esperando a una persona, del mas viejo al mas nuevo.

    El orden es por antiguedad y no por tamano ni por confianza: quien lleva
    mas esperando se atiende primero, que es la unica politica que no deja a
    nadie al final para siempre.
    """
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
                # Lo que el trabajo ya sabe de sus hijos. El nombre del colegio
                # no: ese lo pone quien lee, con el directorio que ya tiene.
                "colegios": sorted({h["colegio_id"] for h in f.hijos or () if h.get("colegio_id")}),
                "grados": list(dict.fromkeys(h["grado"] for h in f.hijos or () if h.get("grado"))),
                "lineas_a_revisar": int(f.dudosos),
                # Un borrador de edicion de kits ya publicados: el canonico del
                # que salio. None en todo lo demas.
                "edicion_de": next(iter(f.hijos or ()), {}).get("basado_en"),
            }
            for f in filas
        ]
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "trabajos": datos}


def _a_consciente(momento: Any) -> datetime:
    """Un `datetime` con zona para ordenar sin chocar naive contra aware.

    Las fechas propias vuelven naive en SQLite (pruebas) y aware en Postgres;
    las del catalogo llegan como ISO por HTTP. Mezclarlas en un `sort` levanta
    `TypeError`, asi que todo se normaliza a aware (UTC si no trae zona) antes
    de comparar. `None` cae al final (fecha minima)."""
    if momento is None:
        return datetime.min.replace(tzinfo=UTC)
    if isinstance(momento, str):
        momento = datetime.fromisoformat(momento)
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


async def mis_solicitudes(motor: Any, usuario_id: uuid.UUID, *, catalogo: Any) -> dict[str, Any]:
    """Las solicitudes del acudiente —listas subidas + trabajos—, ya unidas.

    Una lista subida (en el catalogo) y el trabajo que engendra al aprobarse
    (aca) son la MISMA solicitud: se unen por el `version_id` que el poller
    dejo en el trabajo. Una lista aprobada con su trabajo sale como una sola
    fila `aprobada`, no como dos.

    El `usuario_id` es SIEMPRE el del portador de la sesion, nunca uno del
    navegador; `listas_por_contacto` se llama con ese mismo id.

    Si el catalogo no responde, no se cae la vista: se devuelven los trabajos y
    `listas_disponibles=False` para que el panel muestre un aviso y aun asi
    liste los trabajos (las filas `recibida` que viven en el catalogo no
    aparecen mientras dure la caida).

    Una lista que se subio con el catalogo caido todavia no esta en el catalogo:
    espera en `importacion_lista` (ADR 0040). Tambien sale como `recibida`, con
    `tarea_id: null` porque aun no hay tarea que cancelar, y deja de salir de
    aqui en cuanto se importa: desde ahi la trae el catalogo.
    """
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

    # Las listas subidas del contacto. Una caida del catalogo degrada la vista,
    # no la tumba (se marca y se sigue con los trabajos).
    try:
        listas = await catalogo.listas_por_contacto(str(usuario_id))
        listas_disponibles = True
    except RemotoCaido:
        listas = []
        listas_disponibles = False

    # `version_id` -> trabajo, para unir una lista aprobada con el trabajo que
    # engendro. Solo los de `lista_verificada` guardan ese id en `hijos[0]`.
    trabajo_por_version: dict[str, Any] = {}
    for fila in filas:
        if fila.origen == "lista_verificada":
            hijos = list(fila.hijos or ())
            vid = hijos[0].get("version_id") if hijos else None
            if vid:
                trabajo_por_version[str(vid)] = fila

    solicitudes: list[dict[str, Any]] = []
    versiones_unidas: set[str] = set()

    # Una solicitud por lista subida: aprobada (con su trabajo) o recibida.
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
            # Sin aprobar todavia, o aprobada pero el poller aun no crea el
            # trabajo (se autocorrige en la siguiente carga): es "recibida".
            solicitudes.append(
                {
                    "tipo": "recibida",
                    # Con esto el acudiente la cancela (`cancelar_lista_subida`).
                    "tarea_id": lista_subida.get("tarea_id"),
                    "colegio_id": colegio_id,
                    "colegio_nombre": colegio_nombre,
                    "grado": grado,
                    "creado_en": lista_subida.get("creada_en"),
                    "_orden": _a_consciente(lista_subida.get("creada_en")),
                }
            )

    # Las listas que esperan aca a que el catalogo vuelva.
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

    # Los trabajos que no salieron ya como una lista aprobada.
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


# Un pedido cancelado ya no frena la cancelacion de su solicitud. Uno vencido
# sigue en `pendiente_pago` (§9.4): se cancela primero, como cualquier pendiente.
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
    """El acudiente cancela una solicitud suya (ADR 0031).

    `token` es la sesion del acudiente: con ella Comercio le dice sus pedidos.

    El trabajo pasa a `cancelado`, terminal, y deja de salir en "Mis
    solicitudes" y en la cola de revision. No se cancela:

    - la solicitud de otro (`solicitud_ajena`, 403);
    - un trabajo que el pipeline esta armando (`en_proceso`): se escribe en
      medio y el resultado quedaria a medias;
    - el trabajo que hoy es el kit canonico de su grado (`kit_canonico`):
      aprobarlo lo fijo como la cache de la que copian los demas acudientes;
    - un kit con un pago pendiente (`pedido_pendiente`): primero se cancela el
      pedido, que es lo que consulta a la pasarela antes de soltarlo (§9.3);
    - un kit ya comprado (`kit_comprado`).

    Si el trabajo salio de una lista que el acudiente subio, la lista tambien se
    le desvincula en el Catalogo; si no, volveria a salir como "recibida". Sin
    Comercio no se cancela a ciegas: `RemotoCaido`.
    """
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
    # Aprobar el trabajo de un acudiente lo fija como cache de su grado
    # (`revisar`): la ruta rapida de los demas padres copia de ahi. Cancelarlo
    # dejaria el puntero en un trabajo cancelado, asi que mientras sea el
    # canonico no se toca; se cancela cuando otra publicacion lo reemplace.
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
    """El acudiente cancela una lista que subio y que todavia no tiene kit.

    La lista no se borra: es una lista oficial del colegio y alguien la puede
    curar igual. Solo deja de ser suya (no sale en "Mis solicitudes" ni le arma
    un kit al aprobarse). El Catalogo solo desvincula tareas de este contacto.
    """
    retiradas = await catalogo.retirar_de_contacto(str(usuario_id), tarea_id=tarea_id)
    return {"tarea_id": tarea_id, "retiradas": retiradas}


async def eliminar(motor: Any, trabajo_id: uuid.UUID) -> None:
    """Borra un trabajo y todo lo que cuelga de el (cascada de FKs).

    Un trabajo `publicado` esta protegido: es el kit canonico de su colegio y
    grado (o lo alimentara), y borrarlo perderia una revision humana ya
    aprobada. Los demas estados —previews desechables, encolados, fallidos— se
    pueden borrar sin remordimiento. La cascada `ondelete=CASCADE` de etapas,
    items, candidatos, resoluciones, kits y lineas hace el resto; lo unico que
    no cuelga por FK es la `bandeja_salida`, que es el log de eventos y se deja.
    """
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if actual == EstadoTrabajo.PUBLICADO.value:
            raise TrabajoProtegido(actual)
        await conexion.execute(delete(TRABAJO).where(TRABAJO.c.id == trabajo_id))


async def previews_de(motor: Any, colegio_id: str, grado: str, anio_lectivo: int) -> list[uuid.UUID]:
    """Los previews desechables vivos de un (colegio, grado, anio).

    El colegio/grado no son columnas: viven en el JSON `hijos`, tal como los
    mando el admin al previsualizar. Se filtra en memoria (son pocos) los
    trabajos con `origen='preview_onboarding'` que NO estan publicados y cuyo
    primer hijo cuadra. Lo usa `preview_onboarding` para no acumular copias.
    """
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
