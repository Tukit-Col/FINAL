from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, delete, func, insert, select, update

from ..modelos import (
    EstadoResolucion,
    EstadoTrabajo,
    puede_pasar,
)
from ..optimizador import (
    unidades_a_comprar,
)
from ..remoto import ClienteCatalogo, RemotoCaido
from ..repositorios.trabajos import RepoTrabajos, TrabajoNoExiste, TransicionIlegal
from .base import (
    CANDIDATO,
    KIT,
    KIT_CANONICO,
    LINEA,
    ORIGENES_SIN_ACUDIENTE,
    RESOLUCION,
    TRABAJO,
    TRANSICION,
    BorradorDesactualizado,
    CheckoutRechazado,
    KitsPublicadosNoEditables,
    NoCanonizable,
    PreviewNoPublicable,
    SinProductoQueValidar,
    _estado,
    _pasar_a,
    _publicar_evento,
    ahora,
)
from .formas import _identidad_de_grado
from .versiones import _basado_en, _canonico_vigente_de, _recalcular_objetivos


async def _resolucion_de(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID) -> Any:
    return await RepoTrabajos(conexion).resolucion_de(trabajo_id, item_id)


async def _sku_a_validar(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID, actual: Any) -> str | None:
    sku = await conexion.scalar(
        select(LINEA.c.sku)
        .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
        .where(KIT.c.trabajo_id == trabajo_id, LINEA.c.item_crudo_id == item_id, LINEA.c.sku.is_not(None))
        .order_by(KIT.c.recomendado.desc())
        .limit(1)
    )
    if sku:
        return str(sku)
    if actual.candidato_item_id is not None:
        previo = await conexion.scalar(
            select(CANDIDATO.c.sku).where(CANDIDATO.c.id == actual.candidato_item_id)
        )
        if previo:
            return str(previo)
    return None


async def _candidato_de(conexion: Any, item_id: uuid.UUID, sku: str) -> uuid.UUID | None:
    return await conexion.scalar(
        select(CANDIDATO.c.id).where(and_(CANDIDATO.c.item_crudo_id == item_id, CANDIDATO.c.sku == sku))
    )


async def _linea_con_sku(conexion: Any, trabajo_id: uuid.UUID, item_id: uuid.UUID, sku: str) -> Any:
    return (
        await conexion.execute(
            select(LINEA)
            .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
            .where(KIT.c.trabajo_id == trabajo_id, LINEA.c.item_crudo_id == item_id, LINEA.c.sku == sku)
            .order_by(KIT.c.recomendado.desc())
            .limit(1)
        )
    ).first()


async def _registrar_candidato(
    conexion: Any,
    trabajo_id: uuid.UUID,
    item_id: uuid.UUID,
    sku: str,
    producto_catalogo: dict[str, Any] | None,
) -> uuid.UUID | None:
    existente = await _candidato_de(conexion, item_id, sku)
    if existente is not None:
        return existente

    linea = await _linea_con_sku(conexion, trabajo_id, item_id, sku)
    if linea is not None:
        datos = {
            "producto_canonico_id": linea.producto_canonico_id,
            "nombre": linea.nombre_producto or sku,
            "marca": linea.marca,
            "nivel": linea.nivel or "confiable",
            "personaje": linea.personaje,
            "imagen_url": linea.imagen_url,
            "unidad_base": linea.unidad_base or "unidad",
            "unidades_por_empaque": int(linea.unidades_por_empaque or 1),
            "precio_cop": linea.precio_unitario_cop,
        }
    elif producto_catalogo is not None:
        datos = {
            "producto_canonico_id": None,
            "nombre": producto_catalogo.get("nombre") or sku,
            "marca": producto_catalogo.get("marca"),
            "nivel": producto_catalogo.get("nivel") or "confiable",
            "personaje": producto_catalogo.get("personaje"),
            "imagen_url": producto_catalogo.get("imagen_url"),
            "unidad_base": producto_catalogo.get("unidad_base") or "unidad",
            "unidades_por_empaque": int(producto_catalogo.get("unidades_por_empaque") or 1),
            "precio_cop": producto_catalogo.get("precio_desde"),
        }
    else:
        return None

    siguiente = await conexion.scalar(
        select(func.coalesce(func.max(CANDIDATO.c.orden), -1) + 1).where(CANDIDATO.c.item_crudo_id == item_id)
    )
    candidato_id = uuid.uuid4()
    await conexion.execute(
        insert(CANDIDATO).values(
            id=candidato_id,
            item_crudo_id=item_id,
            sku=sku,
            atributos={},
            confianza=1.0,
            cumple_atributos=True,
            orden=int(siguiente or 0),
            **datos,
        )
    )
    return candidato_id


async def decidir_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    estado: str,
    sku: str | None = None,
    actor: uuid.UUID | None = None,
    motivo: str | None = None,
    catalogo: ClienteCatalogo | None = None,
) -> dict[str, Any]:
    resuelto = estado == EstadoResolucion.RESUELTO_AUTO.value

    producto_catalogo: dict[str, Any] | None = None
    if resuelto and sku and catalogo is not None:
        async with motor.engine.begin() as conexion:
            conocido = await _candidato_de(conexion, item_id, sku) is not None or (
                await _linea_con_sku(conexion, trabajo_id, item_id, sku) is not None
            )
        if not conocido:
            try:
                producto_catalogo = await catalogo.producto(sku)
            except (RemotoCaido, KeyError):
                producto_catalogo = None

    async with motor.engine.begin() as conexion:
        await _proteger_kits_publicados(conexion, trabajo_id)
        actual = await _resolucion_de(conexion, trabajo_id, item_id)
        if actual is None:
            raise TrabajoNoExiste(f"{trabajo_id}/{item_id}")

        candidato_id: uuid.UUID | None = None
        sku_usado = sku
        if resuelto:
            sku_usado = sku or await _sku_a_validar(conexion, trabajo_id, item_id, actual)
            if sku_usado:
                candidato_id = await _registrar_candidato(
                    conexion, trabajo_id, item_id, sku_usado, producto_catalogo
                )
            if candidato_id is None:
                raise SinProductoQueValidar(sku)

        await conexion.execute(
            insert(TRANSICION).values(
                id=uuid.uuid4(),
                resolucion_item_id=actual.id,
                estado_anterior=actual.estado,
                estado_nuevo=estado,
                motivo=motivo or "decision de Admin Tukit",
                decidida_por=actor,
            )
        )
        await conexion.execute(
            update(RESOLUCION)
            .where(RESOLUCION.c.id == actual.id)
            .values(
                estado=estado,
                candidato_item_id=candidato_id,
                decidido_por=actor,
                decidido_en=ahora(),
            )
        )
        await conexion.execute(
            update(LINEA).where(LINEA.c.item_crudo_id == item_id).values(estado_resolucion=estado)
        )
        if not resuelto:
            await _vaciar_producto_de_item(conexion, item_id)
    return {"item_id": str(item_id), "estado": estado, "sku": sku_usado}


async def _vaciar_producto_de_item(conexion: Any, item_id: uuid.UUID) -> None:
    kits = [
        fila.kit_id
        for fila in await conexion.execute(
            select(LINEA.c.kit_id).where(LINEA.c.item_crudo_id == item_id).distinct()
        )
    ]
    await conexion.execute(
        update(LINEA)
        .where(LINEA.c.item_crudo_id == item_id)
        .values(
            producto_canonico_id=None,
            sku=None,
            nombre_producto=None,
            marca=None,
            nivel=None,
            personaje=None,
            imagen_url=None,
            confianza=None,
            unidades_por_empaque=1,
            unidades_a_comprar=0,
            precio_unitario_cop=None,
            subtotal_cop=None,
        )
    )
    for kit_id in kits:
        await _recalcular_total_kit(conexion, kit_id)


async def fijar_producto_en_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    sku: str,
    *,
    catalogo: ClienteCatalogo,
    volver_comprable: bool = False,
) -> dict[str, Any]:
    async with motor.engine.begin() as conexion:
        await _proteger_kits_publicados(conexion, trabajo_id)
    producto = await catalogo.producto(sku)
    precio = producto.get("precio_desde")
    async with motor.engine.begin() as conexion:
        await _proteger_kits_publicados(conexion, trabajo_id)
        fila = (
            await conexion.execute(
                select(
                    LINEA.c.id,
                    LINEA.c.kit_id,
                    LINEA.c.cantidad_pedida,
                    LINEA.c.informativa,
                    LINEA.c.estado_resolucion,
                    LINEA.c.unidades_a_comprar,
                    LINEA.c.sku,
                    LINEA.c.nombre_producto,
                    LINEA.c.nivel,
                    LINEA.c.precio_unitario_cop,
                    LINEA.c.imagen_url,
                    LINEA.c.alternativas,
                )
                .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
                .where(
                    KIT.c.trabajo_id == trabajo_id,
                    KIT.c.perfil == perfil,
                    LINEA.c.item_crudo_id == item_id,
                )
            )
        ).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(f"{trabajo_id}/{perfil}/{item_id}")

        alternativas = [a for a in (fila.alternativas or []) if a.get("sku") not in {sku, fila.sku}]
        if fila.sku and fila.sku != sku:
            anterior = {
                "sku": fila.sku,
                "nombre": fila.nombre_producto,
                "nivel": fila.nivel,
                "precio_cop": fila.precio_unitario_cop,
                "imagen_url": fila.imagen_url,
            }
            alternativas = [anterior, *alternativas]
        alternativas = alternativas[:2]

        empaque = int(producto.get("unidades_por_empaque") or 1)
        unidades = unidades_a_comprar(int(fila.cantidad_pedida or 0), empaque)
        if fila.sku and fila.unidades_a_comprar == 0 and int(fila.cantidad_pedida or 0) > 0:
            unidades = 0
        informativa = bool(fila.informativa) and not volver_comprable
        subtotal = None if (informativa or precio is None) else precio * unidades
        extra: dict[str, Any] = {}
        if volver_comprable:
            extra = {"informativa": False, "mensaje": None}
            if fila.estado_resolucion in (
                EstadoResolucion.HUECO_CATALOGO.value,
                EstadoResolucion.SIN_MATCH.value,
            ):
                extra["estado_resolucion"] = EstadoResolucion.RESUELTO_AUTO.value
        await conexion.execute(
            update(LINEA)
            .where(LINEA.c.id == fila.id)
            .values(
                **extra,
                sku=sku,
                nombre_producto=producto.get("nombre"),
                marca=producto.get("marca"),
                nivel=producto.get("nivel"),
                personaje=producto.get("personaje"),
                imagen_url=producto.get("imagen_url"),
                unidad_base=producto.get("unidad_base"),
                unidades_por_empaque=empaque,
                unidades_a_comprar=unidades,
                precio_unitario_cop=None if informativa else precio,
                subtotal_cop=subtotal,
                alternativas=alternativas,
            )
        )
        await _recalcular_total_kit(conexion, fila.kit_id)
    return {"trabajo_id": str(trabajo_id), "perfil": perfil, "item_id": str(item_id), "sku": sku}


async def fijar_producto_en_todos_los_kits(
    motor: Any,
    trabajo_id: uuid.UUID,
    item_id: uuid.UUID,
    sku: str,
    *,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    async with motor.engine.begin() as conexion:
        perfiles = [
            f.perfil
            for f in await conexion.execute(
                select(KIT.c.perfil)
                .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
                .where(KIT.c.trabajo_id == trabajo_id, LINEA.c.item_crudo_id == item_id)
                .distinct()
            )
        ]
    if not perfiles:
        raise TrabajoNoExiste(f"{trabajo_id}/{item_id}")
    for perfil in perfiles:
        await fijar_producto_en_linea(
            motor, trabajo_id, perfil, item_id, sku, catalogo=catalogo, volver_comprable=True
        )
    return {"trabajo_id": str(trabajo_id), "perfiles": perfiles, "item_id": str(item_id), "sku": sku}


async def _proteger_kits_publicados(conexion: Any, trabajo_id: uuid.UUID) -> None:
    fila = (
        await conexion.execute(select(TRABAJO.c.estado, TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id))
    ).one_or_none()
    if fila is None or fila.estado != EstadoTrabajo.PUBLICADO.value:
        return
    apuntado = await conexion.scalar(
        select(KIT_CANONICO.c.id).where(KIT_CANONICO.c.trabajo_id == trabajo_id).limit(1)
    )
    if fila.origen in ORIGENES_SIN_ACUDIENTE or apuntado is not None:
        raise KitsPublicadosNoEditables()


async def _recalcular_total_kit(conexion: Any, kit_id: uuid.UUID) -> None:
    await RepoTrabajos(conexion).recalcular_total_kit(kit_id)


async def revisar(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    decision: str,
    nota: str | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    nuevo = EstadoTrabajo.PUBLICADO.value if decision == "aprobar" else EstadoTrabajo.ENCOLADO.value
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if not puede_pasar(actual, nuevo):
            raise TransicionIlegal(actual, nuevo)
        if decision == "aprobar":
            origen = await conexion.scalar(select(TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id))
            if origen in ORIGENES_SIN_ACUDIENTE:
                raise PreviewNoPublicable()
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(
                estado=nuevo,
                revisado_por=actor,
                revisado_en=ahora(),
                nota_revision=nota,
                terminado_en=ahora() if decision == "aprobar" else None,
            )
        )
        if decision == "aprobar":
            if not await _tiene_lineas_comprables(conexion, trabajo_id):
                raise CheckoutRechazado(
                    409,
                    {
                        "error": "kit_sin_lineas",
                        "mensaje": (
                            "Este trabajo no tiene ninguna linea con producto y precio "
                            "que Tukit pueda vender. Fija el producto en las lineas antes "
                            "de aprobarlo."
                        ),
                    },
                )
            await _publicar_evento(conexion, trabajo_id)

    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}


async def _tiene_lineas_comprables(conexion: Any, trabajo_id: uuid.UUID) -> bool:
    existe = await conexion.scalar(
        select(LINEA.c.id)
        .select_from(LINEA.join(KIT, KIT.c.id == LINEA.c.kit_id))
        .where(
            KIT.c.trabajo_id == trabajo_id,
            LINEA.c.informativa.is_(False),
            LINEA.c.sku.is_not(None),
            LINEA.c.precio_unitario_cop.is_not(None),
        )
        .limit(1)
    )
    return existe is not None


async def _fijar_canonico(conexion: Any, trabajo_id: uuid.UUID) -> None:
    await RepoTrabajos(conexion).fijar_canonico(trabajo_id)


async def version_canonica(conexion: Any, colegio_id: str, grado: str, anio: int) -> str | None:
    fila = (
        await conexion.execute(
            select(TRABAJO.c.hijos)
            .select_from(KIT_CANONICO.join(TRABAJO, TRABAJO.c.id == KIT_CANONICO.c.trabajo_id))
            .where(
                KIT_CANONICO.c.colegio_id == colegio_id,
                KIT_CANONICO.c.grado == grado,
                KIT_CANONICO.c.anio_lectivo == anio,
            )
        )
    ).one_or_none()
    if fila is None:
        return None
    identidad = _identidad_de_grado(fila.hijos)
    return identidad[3] if identidad else None


async def _cerrar_canonico_de_lista(conexion: Any, trabajo_id: uuid.UUID) -> str:
    fila = (await conexion.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))).one_or_none()
    identidad = _identidad_de_grado(fila.hijos if fila else None)
    regenera = bool(next(iter(fila.hijos or ()), {}).get("regenera")) if fila else False
    if identidad and identidad[3] and not regenera:
        colegio_id, grado, anio, version = identidad
        if await version_canonica(conexion, colegio_id, grado, anio) == version:
            await conexion.execute(delete(TRABAJO).where(TRABAJO.c.id == trabajo_id))
            return "descartado"
    await _pasar_a(conexion, trabajo_id, EstadoTrabajo.PUBLICADO.value, terminado_en=ahora())
    await _fijar_canonico(conexion, trabajo_id)
    return EstadoTrabajo.PUBLICADO.value


async def fijar_como_canonico(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    nota: str | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(TRABAJO.c.estado, TRABAJO.c.origen).where(TRABAJO.c.id == trabajo_id)
            )
        ).one_or_none()
        if fila is None:
            raise TrabajoNoExiste(str(trabajo_id))
        if fila.origen not in ORIGENES_SIN_ACUDIENTE:
            raise NoCanonizable()
        nuevo = EstadoTrabajo.PUBLICADO.value
        if not puede_pasar(fila.estado, nuevo):
            raise TransicionIlegal(fila.estado, nuevo)
        basado_en = await _basado_en(conexion, trabajo_id)
        if basado_en and await _canonico_vigente_de(conexion, trabajo_id) != basado_en:
            raise BorradorDesactualizado()
        await _recalcular_objetivos(conexion, trabajo_id)
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(
                estado=nuevo,
                revisado_por=actor,
                revisado_en=ahora(),
                nota_revision=nota,
                terminado_en=ahora(),
            )
        )
        await _fijar_canonico(conexion, trabajo_id)
    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}
