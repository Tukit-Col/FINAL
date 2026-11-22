"""Revision humana de las lineas: decidir, fijar productos y cerrar la lista como canonica."""

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
    """El producto que "validar el elegido" confirma cuando no llega `sku`.

    Primero el que la LINEA tiene en el kit recomendado —es el que el admin ve
    marcado como "elegido por el sistema"—, luego el de cualquier otro kit, y
    al final el del candidato que la resolucion ya apuntaba. La LINEA va antes
    que el candidato porque la ruta lenta deja `candidato_item_id` nulo en todo
    lo que no es RESUELTO_AUTO, y el optimizador igual eligio un producto para
    el kit: ese es el que hay que confirmar.
    """
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
    """El CANDIDATO de (item, sku); si no existe, lo da de alta.

    El producto que una linea muestra no siempre fue candidato del item: el
    interruptor de personaje del Fan y `fijar_producto_en_linea` ponen en la
    LINEA productos que el emparejamiento nunca ofrecio. Validarlo es una
    decision legitima del revisor, y la resolucion exige un candidato
    (CHECK `resolucion_resuelta_tiene_candidato`), asi que se registra uno con
    los datos que ya tiene la LINEA —o, si no hay LINEA con ese sku, con los
    del catalogo—. `confianza=1.0` porque lo confirmo una persona.
    """
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
    """AD-04: una persona valida el emparejamiento o lo marca sin coincidencia.

    Escribe la transicion ANTES de cambiar el estado y en la misma
    transaccion, porque una decision humana sin rastro de quien la tomo es
    justo el control sin dueno que la cola existe para no ser.

    Validar (RESUELTO_AUTO) sin `sku` confirma el producto que la linea tiene
    en el kit (`_sku_a_validar`). Si ese producto no es candidato del item se
    registra (`_registrar_candidato`); solo cuando no hay producto por ningun
    lado se rechaza con `SinProductoQueValidar` —antes eso llegaba a la base
    como RESUELTO_AUTO sin candidato y el CHECK lo convertia en un 500—.

    El estado se copia tambien a las LINEA del item en los tres kits: la
    consola clasifica por `linea.estado_resolucion`, y sin esto una linea ya
    validada seguia apareciendo como pendiente.
    """
    resuelto = estado == EstadoResolucion.RESUELTO_AUTO.value

    # El catalogo se consulta FUERA de la transaccion (una llamada HTTP no debe
    # sostener un lock), y solo cuando el sku no esta ni como candidato ni en
    # una LINEA del item: es el caso raro, no el comun.
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
    """Deja las LINEA del item como un hueco del optimizador: sin producto ni precio.

    "Sin coincidencia" es decir "no lo tenemos". Si la linea conservara el
    producto que el optimizador eligio, `ordenar` la cobraria (cobra toda linea
    con sku y precio) mientras el acudiente la ve como hueco. Las alternativas
    se conservan: el revisor puede fijar una despues con `fijar_producto_en_linea`.
    """
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
    """Fija un producto en UNA linea (un kit + un item) con su precio recalculado.

    La decision de producto es por-nivel (tres LINEA por item, una por kit),
    no por-item: `decidir_linea` escribe RESOLUCION y solo copia su estado a la
    LINEA —nunca cambia su producto—, asi que el kit publicado seguia mostrando
    el producto del optimizador. Esta es la
    ruta de escritura que faltaba. El producto se pide al catalogo (no al
    CANDIDATO) porque un personaje puede no ser candidato del item y aun asi ser
    una eleccion valida del revisor.

    `subtotal = precio * techo(cantidad_pedida / unidades_por_empaque)`, la misma
    aritmetica del armado (optimizador._construir_linea). Recalcula KIT.total_cop.
    """
    # Se niega antes de ir al catalogo: no tiene caso pagar la llamada HTTP.
    # Se vuelve a mirar dentro de la transaccion que escribe.
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

        # El producto que sale pasa a ser alternativa y el que entra deja de
        # serlo: sin esto la consola lo mostraba dos veces y el anterior ya no
        # se podia volver a elegir. Mismo tope de dos que pone el armado.
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

        # Una linea informativa no lleva precio (CHECK del modelo): fijarle un
        # producto no puede introducir un subtotal por la puerta de atras.
        empaque = int(producto.get("unidades_por_empaque") or 1)
        unidades = unidades_a_comprar(int(fila.cantidad_pedida or 0), empaque)
        # La linea que otra ya cubre (las tijeras pedidas en tres materias: «Ya va
        # en la linea 58») tiene producto y cero unidades. Cambiarle el producto
        # no la vuelve a cobrar: el Fan cobraba tres tijeras.
        if fila.sku and fila.unidades_a_comprar == 0 and int(fila.cantidad_pedida or 0) > 0:
            unidades = 0
        # Salvo que el revisor la vuelva comprable a proposito: eligio un producto
        # para un renglon que el armado dejo como «consiguelo por tu cuenta».
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
    """El producto que el revisor eligio para un renglon, en TODOS los kits.

    Resolver un hueco («No lo tenemos -> Resolver») es una decision sobre el
    renglon, no sobre un nivel: la consola lo dice («lo que decidas aqui vale
    para todos los kits») y antes solo cambiaba el kit abierto. Si el renglon
    era informativo (lo dejo «consiguelo por tu cuenta»), elegir un producto lo
    vuelve comprable: tiene precio y entra al total.
    """
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
    """Niega editar las lineas de unos kits canonicos ya publicados.

    Canonico es lo que no tiene acudiente (preview fijado, `canonico_lista`) o
    lo que la cache de su grado apunta hoy (datos de antes, cuando aprobar el
    trabajo de un acudiente tambien la fijaba). El trabajo publicado de un
    acudiente que no es la cache sigue el flujo de siempre.
    """
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
    """AD-06: aprobar publica al acudiente, devolver reabre sin avisar."""
    # Devolver reencola: el trabajador durable (ADR 0024) lo retoma, no una tarea
    # en proceso. Antes iba a PROCESANDO y el API arrancaba la corrutina; ahora
    # queda ENCOLADO y el worker lo drena con SKIP LOCKED.
    nuevo = EstadoTrabajo.PUBLICADO.value if decision == "aprobar" else EstadoTrabajo.ENCOLADO.value
    async with motor.engine.begin() as conexion:
        actual = await _estado(conexion, trabajo_id)
        if not puede_pasar(actual, nuevo):
            raise TransicionIlegal(actual, nuevo)
        # Un preview de onboarding no tiene acudiente (`usuario_id` NULL): no es
        # el trabajo del padre, es la vista de los kits que saldrian de la lista.
        # Publicarlo no avisa a nadie (el `kits_publicados` que emite se queda
        # sin destinatario y el repartidor lo reintenta sin fin) y no crea el
        # colegio (eso lo hace aprobar la LISTA en Catalogo). Lo que se hace con
        # un preview es fijarlo como canonico (`fijar_como_canonico`).
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
            # No se publica un kit del que nadie puede comprar nada: si NINGUNA
            # linea de NINGUN perfil tiene producto+precio, el acudiente solo
            # veria el 409 "sin lineas comprables" en el checkout. Se niega la
            # aprobacion con un motivo claro (falta fijar producto/precio en las
            # lineas). Misma definicion de "comprable" que `ordenar`: no
            # informativa, con sku y precio.
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
            # Aprobar el trabajo de un acudiente NO lo vuelve el canonico de su
            # grado: lleva sus preferencias (presupuesto, prioridad, personaje) y
            # es solo suyo. El canonico sale de la LISTA aprobada
            # (`canonico_lista`) o de un preview fijado (`fijar_como_canonico`).

    return {"trabajo_id": str(trabajo_id), "estado": nuevo, "nota": nota}


async def _tiene_lineas_comprables(conexion: Any, trabajo_id: uuid.UUID) -> bool:
    """True si algun kit del trabajo tiene una linea que Tukit pueda cobrar.

    Comprable = no informativa, con `sku` y `precio_unitario_cop`. Es la misma
    condicion que filtra `ordenar` al armar la orden; se comparte aqui para que
    aprobar y comprar no discrepen sobre que es un kit vendible.
    """
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
    """Al publicar, apunta la cache canonica de (colegio, grado, anio) a este trabajo."""
    await RepoTrabajos(conexion).fijar_canonico(trabajo_id)


async def version_canonica(conexion: Any, colegio_id: str, grado: str, anio: int) -> str | None:
    """La version de lista con que se armo el canonico vigente del grado.

    Sale del hijo del trabajo al que apunta la cache. None si no hay canonico o
    si el trabajo es anterior a que los hijos cargaran su `version_id`.
    """
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
    """El cierre de un `canonico_lista`: publica sin avisar y fija la cache.

    No hay acudiente, asi que no se emite `kits_publicados` y no pasa por la
    cola de revision: la persona ya reviso la LISTA, que es lo que la aprobacion
    certifica, igual que en el kit del padre que esperaba (`lista_verificada`).

    Si mientras el optimizador corria alguien fijo a mano un canonico de ESTA
    misma version —aprobar desde el preview, con sus ajustes— ese gana: este
    trabajo sobra y se borra en vez de pisarle el puntero.
    """
    fila = (await conexion.execute(select(TRABAJO.c.hijos).where(TRABAJO.c.id == trabajo_id))).one_or_none()
    identidad = _identidad_de_grado(fila.hijos if fila else None)
    # `regenera` lo pone solo `poller.regenerar_canonicos`, que ya salto los
    # canonicos aprobados o corregidos a mano: ahi la version repetida es
    # justamente lo que se pidio rearmar.
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
    """Publica un trabajo SIN acudiente y lo deja como kit canonico de su grado.

    Es lo que hace "Aprobar la lista y guardar estos kits" desde un preview: el
    admin ya miro (y quiza ajusto) los tres kits, asi que esos —y no un calculo
    nuevo— son los que la ruta rapida le sirve al proximo acudiente. No emite
    `kits_publicados`: no hay a quien avisar.
    """
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
        # Un borrador de edicion solo reemplaza al canonico del que salio: si
        # mientras tanto la lista se reaprobo, ese ya no es el vigente.
        basado_en = await _basado_en(conexion, trabajo_id)
        if basado_en and await _canonico_vigente_de(conexion, trabajo_id) != basado_en:
            raise BorradorDesactualizado()
        # La disponibilidad ("91% con precio confirmado") es la del armado; si
        # el admin fijo o vacio productos, se recalcula sobre lo que se publica.
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
