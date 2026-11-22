"""Lectura del trabajo y sus kits para el acudiente, y el reordenamiento de lineas."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from tukit_comun.cifrado import cifrador_desde_entorno

from ..dominio.pipeline import (
    personajes_de_los_hijos,
)
from ..modelos import (
    EstadoResolucion,
    EstadoTrabajo,
    PerfilKit,
)
from ..modelos.trabajo import ETAPAS
from ..remoto import ClienteCatalogo, ClienteComercio, ClienteIdentidad, RemotoCaido
from ..repositorios.trabajos import TrabajoNoExiste
from .anclas import _anclas_de_personaje
from .base import ETAPA, ITEM, KIT, LINEA, RESOLUCION, TRABAJO, CambioNoPermitido, CheckoutRechazado
from .formas import _aplicar_cambios, _linea_publica, _lineas_aplicadas, _objetivos_de_lineas, _sin_apodo

logger = logging.getLogger(__name__)


async def dueno(motor: Any, trabajo_id: uuid.UUID) -> uuid.UUID | None:
    """El `usuario_id` del trabajo, o `None` si no tiene dueno.

    Lo usan las lecturas del acudiente para comprobar quien pide el kit: el id
    del trabajo viaja en enlaces y no es un secreto.
    """
    async with motor.engine.connect() as conexion:
        fila = (
            await conexion.execute(select(TRABAJO.c.usuario_id).where(TRABAJO.c.id == trabajo_id))
        ).one_or_none()
    if fila is None:
        raise TrabajoNoExiste(str(trabajo_id))
    return fila.usuario_id


async def ver(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    incluir_kits: bool | None = None,
    incluir_admin: bool = False,
    catalogo: ClienteCatalogo | None = None,
) -> dict[str, Any]:
    """El cuerpo de `GET /v1/trabajos/{id}`.

    Mientras el estado no sea `publicado`, `kits` va vacio: el acudiente
    nunca ve un kit sin revisar, y esa es la razon de ser de
    `espera_revision`. Admin usa el mismo lector con `incluir_kits=True`,
    porque su trabajo es justamente mirar lo que todavia no se publica.

    Un trabajo `parent_apply` NO tiene kits propios: es un puntero al canonico
    (modelo por referencia). Sus kits se resuelven al vuelo siguiendo
    `hijos[0].canonico_trabajo_id` + su perfil, con el personaje aplicado sobre
    las anclas. Por eso `ver` acepta `catalogo`: sin el, el swap de personaje no
    se puede hacer y el kit sale con sus productos neutrales.

    `incluir_admin` agrega los campos que solo la consola interna ve
    (`recibido_en`, `contacto_id`, `lineas_pendientes`). El acudiente nunca
    los recibe: `contacto_id` reintroduciria a mano la referencia que la
    notificacion resuelve al vuelo, y esa asimetria es intencional.
    """
    async with motor.engine.begin() as conexion:
        cabeza = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        if cabeza is None:
            raise TrabajoNoExiste(str(trabajo_id))

        etapas = [
            {
                "nombre": f.nombre,
                "estado": f.estado,
                "ms": f.ms,
                "detalle": dict(f.detalle or {}),
            }
            for f in await conexion.execute(select(ETAPA).where(ETAPA.c.trabajo_id == trabajo_id))
        ]
        etapas.sort(key=lambda e: ETAPAS.index(e["nombre"]) if e["nombre"] in ETAPAS else 99)

        mostrar = incluir_kits if incluir_kits is not None else cabeza.estado == EstadoTrabajo.PUBLICADO.value
        kits: list[dict[str, Any]] = []
        # Override de personajes_por_hijo para la ruta parent_apply (sus claves son
        # las de las lineas del canonico, no las del trabajo); None = usar el camino normal.
        personajes_por_hijo_pa: dict[str, list[str]] | None = None
        recomendado: dict[str, Any] | None = None
        # Lo que el acudiente cambio en sus kits: se aplica al leer, nunca se
        # escribe en `linea_kit` (ver `TrabajoPipeline.cambios`).
        cambios: dict[str, Any] = dict(cabeza.cambios or {})

        if mostrar and cabeza.origen == "parent_apply":
            # Un puntero al canonico: no tiene kits propios. Se sigue
            # `hijos[0].canonico_trabajo_id` y se pintan los TRES kits del
            # canonico, con el personaje aplicado sobre las anclas: el que eligio
            # al empezar va marcado, y si prefiere otro puede pagar ese.
            hijo = (list(cabeza.hijos or ()) or [{}])[0]
            canonico_id = hijo.get("canonico_trabajo_id")
            perfil = str(hijo.get("perfil") or "")
            if canonico_id and perfil:
                # ponytail: 4 llamadas de catalogo dentro de la txn de lectura
                # (SELECT puro, sin locks). Si molesta, resolver los swaps antes
                # de abrir la txn con una pre-lectura de cabeza.
                personaje = hijo.get("personaje")
                swaps = await _anclas_de_personaje(catalogo, personaje) if catalogo else {}
                # Los canonicos traen Ahorrador y Premium (ADR 0030); uno viejo
                # puede traer tambien un Fan, que ya no se muestra: el Fan es del
                # acudiente que pidio un personaje, y se arma para el.
                canonicos = [
                    p
                    for p in (
                        await conexion.execute(
                            select(KIT.c.perfil)
                            .where(KIT.c.trabajo_id == uuid.UUID(str(canonico_id)))
                            .order_by(KIT.c.total_cop)
                        )
                    ).scalars()
                    if p != PerfilKit.FAN.value
                ]
                perfiles = list(canonicos)
                if personaje and PerfilKit.AHORRADOR.value in canonicos:
                    perfiles.insert(canonicos.index(PerfilKit.AHORRADOR.value) + 1, PerfilKit.FAN.value)
                for perfil_kit in perfiles:
                    # El Fan es el Ahorrador canonico con el personaje en las
                    # anclas; los demas se pintan tal cual los reviso una persona.
                    base, swaps_kit = (
                        (PerfilKit.AHORRADOR.value, swaps)
                        if perfil_kit == PerfilKit.FAN.value
                        else (perfil_kit, {})
                    )
                    lineas, total, sin_encaje = await _lineas_aplicadas(
                        conexion, uuid.UUID(str(canonico_id)), base, swaps_kit
                    )
                    if cambios.get(perfil_kit):
                        lineas, total = _aplicar_cambios(lineas, cambios[perfil_kit])
                    kits.append(
                        {
                            "perfil": perfil_kit,
                            "total": total,
                            "objetivos": _objetivos_de_lineas(lineas, total),
                            # Mismo `hijo` que sus lineas (el del canonico), para
                            # que la web los junte sin adivinar.
                            "personaje_sin_encaje": sin_encaje,
                            "lineas": lineas,
                            "consolidaciones": [],
                            "informativas": sum(1 for linea in lineas if linea["informativa"]),
                        }
                    )
                # `personajes_por_hijo` usa la clave REAL de las lineas (un canonico
                # nacido de un preview dice "preview", no "canonico"); si no, la franja
                # Fan de la web no casa y se queda vacia.
                if personaje:
                    hijos_de_lineas = {
                        linea["hijo"] for kit in kits for linea in kit["lineas"] if linea.get("hijo")
                    }
                    personajes_por_hijo_pa = {h: [str(personaje)] for h in hijos_de_lineas}
                recomendado = {
                    "perfil": perfil,
                    "razon": (
                        "Es el kit que elegiste al empezar. Puedes mirar los otros y cambiarte si prefieres."
                    ),
                    "dentro_de_presupuesto": None,
                }
        elif mostrar:
            for kit in await conexion.execute(
                select(KIT).where(KIT.c.trabajo_id == trabajo_id).order_by(KIT.c.total_cop)
            ):
                lineas = [
                    _linea_publica(f)
                    for f in await conexion.execute(
                        select(LINEA, RESOLUCION.c.concepto_codigo)
                        .select_from(
                            LINEA.join(
                                RESOLUCION,
                                RESOLUCION.c.item_crudo_id == LINEA.c.item_crudo_id,
                                isouter=True,
                            )
                        )
                        .where(LINEA.c.kit_id == kit.id)
                        .order_by(LINEA.c.hijo_referencia, LINEA.c.orden)
                    )
                ]
                total = int(kit.total_cop)
                objetivos = dict(kit.objetivos or {})
                # Lo que no cupo viaja dentro del JSON de objetivos (sin
                # migracion), pero no es un objetivo: se saca a su propio campo.
                sin_encaje = list(objetivos.pop("personaje_sin_encaje", None) or ())
                if cambios.get(kit.perfil):
                    lineas, total = _aplicar_cambios(lineas, cambios[kit.perfil])
                    objetivos = _objetivos_de_lineas(lineas, total)
                cuerpo = {
                    "perfil": kit.perfil,
                    "total": total,
                    "objetivos": objetivos,
                    "personaje_sin_encaje": sin_encaje,
                    "lineas": lineas,
                    "consolidaciones": list(kit.consolidaciones or ()),
                    "informativas": sum(1 for linea in lineas if linea["informativa"]),
                }
                kits.append(cuerpo)
                if kit.recomendado:
                    recomendado = {
                        "perfil": kit.perfil,
                        "razon": kit.razon_recomendacion,
                        "dentro_de_presupuesto": kit.dentro_de_presupuesto,
                    }

        campos_admin: dict[str, Any] = {}
        if incluir_admin:
            # Los item_id que todavia esperan a una persona: los que la
            # resolucion no dejo en RESUELTO_AUTO. Es el mismo criterio que
            # `cola()`, pero devolviendo los ids de este trabajo en vez de un
            # conteo, porque la consola los necesita uno a uno.
            pendientes = await conexion.execute(
                select(ITEM.c.id)
                .select_from(ITEM.join(RESOLUCION, RESOLUCION.c.item_crudo_id == ITEM.c.id))
                .where(
                    ITEM.c.trabajo_id == trabajo_id,
                    RESOLUCION.c.estado != EstadoResolucion.RESUELTO_AUTO.value,
                )
                .order_by(ITEM.c.orden)
            )
            campos_admin = {
                "recibido_en": cabeza.creado_en.isoformat() if cabeza.creado_en else None,
                # Nunca el correo ni el celular: la consola referencia al
                # acudiente por identificador y `operacion` lo resuelve al
                # enviar. Un trabajo de preview o anonimo no tiene usuario.
                "contacto_id": str(cabeza.usuario_id) if cabeza.usuario_id else "",
                "lineas_pendientes": [str(f.id) for f in pendientes],
            }

    return {
        "trabajo_id": str(cabeza.id),
        "estado": cabeza.estado,
        "origen": cabeza.origen,
        # La consola interna nunca recibe el apodo de un menor (Ley 1581, nota
        # de `TrabajoAdmin` en el contrato); la vista del acudiente si, porque
        # rotula su propio kit con el.
        "hijos": [_sin_apodo(h) for h in cabeza.hijos or ()] if incluir_admin else list(cabeza.hijos or ()),
        "personajes_por_hijo": (
            personajes_por_hijo_pa
            if personajes_por_hijo_pa is not None
            else _personajes_por_hijo_publico(cabeza)
        ),
        "etapas": etapas,
        "kits": kits,
        "recomendado": recomendado,
        "cambios": cambios,
        "degradaciones": list(cabeza.degradaciones or ()),
        "error": cabeza.error,
        "mensaje": cabeza.mensaje,
        "creado_en": cabeza.creado_en.isoformat() if cabeza.creado_en else None,
        "terminado_en": cabeza.terminado_en.isoformat() if cabeza.terminado_en else None,
        "nota_revision": cabeza.nota_revision,
        **campos_admin,
    }


def _personajes_por_hijo_publico(cabeza: Any) -> dict[str, list[str]]:
    """`{hijo de las lineas: [franquicias pedidas]}` para la vista y el asistente.

    Solo nombres de franquicia (Spiderman, Minnie), nunca el apodo del menor. Las
    claves son las de las lineas del kit: las del trabajo resueltas con
    `personajes_de_los_hijos`; en un `parent_apply` la linea es del canonico
    (`"canonico"`) y se le asigna el personaje que el acudiente eligio.
    """
    hijos = list(cabeza.hijos or ())
    if cabeza.origen == "parent_apply":
        personaje = (hijos[0] if hijos else {}).get("personaje")
        return {"canonico": [str(personaje)]} if personaje else {}
    if not cabeza.preferencias_cifradas:
        return {}
    try:
        preferencias = cifrador_desde_entorno().descifrar_json(cabeza.preferencias_cifradas) or {}
    except Exception:
        # Una rotacion de llave o un VARIABLE_LLAVE mal puesto no debe tumbar ver()
        # (y con el checkout, opciones y el chat): sin preferencias, sin personajes.
        logger.warning("preferencias ilegibles al exponer personajes_por_hijo", exc_info=True)
        return {}
    pedidos = {
        str(hijo): [str(p) for p in valores if p]
        for hijo, valores in (preferencias.get("personaje_por_hijo") or {}).items()
        if valores
    }
    referencias = [str(h.get("referencia")) for h in hijos if isinstance(h, dict) and h.get("referencia")]
    # Las mismas reglas del armado (exacta, o por orden sin ambiguedad), para que la
    # vista nombre al hijo cuyas lineas recibieron el personaje.
    unidos = personajes_de_los_hijos(preferencias, referencias)
    return {hijo: pedidos.get(hijo) or [personaje] for hijo, personaje in unidos.items()}


async def ordenar(
    motor: Any,
    trabajo_id: uuid.UUID,
    *,
    portador: uuid.UUID | None = None,
    perfil: str,
    entrega: dict[str, str],
    correo: str,
    metodo: str = "pse",
    url_redireccion: str | None = None,
    comercio: ClienteComercio,
    catalogo: ClienteCatalogo,
    identidad: ClienteIdentidad | None = None,
) -> dict[str, Any]:
    """El checkout del acudiente: del trabajo publicado a la orden y el pago.

    El navegador manda `trabajo_id` + perfil + direccion + correo, nada mas.
    Aqui se lee el kit de ese perfil (por `ver`, que ya sabe seguir el puntero
    de un `parent_apply` y aplicar el personaje), se arma la orden con SOLO sku
    y precio publico —el id canonico lo resuelve Comercio— y se manda a Comercio
    a congelar y cobrar. Asi ningun id de base sale a la superficie (RPO cero).

    El `usuario_id` sale del trabajo. Un trabajo anonimo (la ruta rapida de
    `/empezar` no exige login) no lo tiene: se registra el contacto con el correo
    del pago, igual que en `crear`. Sin `usuario_id` Comercio no cierra la orden,
    asi que aqui no se degrada: sin destinatario no hay a quien cobrarle.
    """
    async with motor.engine.begin() as conexion:
        cabeza = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        if cabeza is None:
            raise TrabajoNoExiste(str(trabajo_id))
        usuario_id = cabeza.usuario_id
        hijos = list(cabeza.hijos or ())
    # Un trabajo con dueno solo lo paga su dueno (`portador` es la sesion de
    # quien llama): el id del trabajo viaja en enlaces y no es un secreto.
    if usuario_id is not None and usuario_id != portador:
        raise CambioNoPermitido(
            "solicitud_ajena", "Inicia sesión con la cuenta que hizo esta solicitud para pagarla.", 403
        )

    if usuario_id is None:
        cliente = identidad or ClienteIdentidad()
        crudo = await cliente.registrar_contacto(correo)
        if not crudo:
            raise RemotoCaido("identidad", "no se pudo registrar el contacto para el pago")
        usuario_id = uuid.UUID(crudo)

    vista = await ver(motor, trabajo_id, incluir_kits=True, catalogo=catalogo)
    kit = next((k for k in vista["kits"] if k["perfil"] == perfil), None)
    if kit is None:
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil}")

    lineas = []
    for linea in kit["lineas"]:
        elegido = linea.get("producto_elegido")
        # Una linea informativa (o sin producto/precio) no se compra: se muestra
        # en el kit pero no entra a la orden. Tampoco la que quedo en cero por
        # ir junto a otra ("Ya va en la linea N", o la de un hermano): Comercio
        # exige cantidad > 0 y una sola en cero tumbaba el checkout entero.
        # Lo que el acudiente descarto ("ya lo tengo") tampoco se cobra.
        if linea["informativa"] or linea.get("descartado") or not elegido or elegido.get("precio") is None:
            continue
        if int(linea["unidades_a_comprar"]) <= 0:
            continue
        lineas.append(
            {
                "sku": elegido["sku"],
                "nombre": elegido["nombre"],
                "cantidad": int(linea["unidades_a_comprar"]),
                "precio_unitario": int(elegido["precio"]),
            }
        )
    if not lineas:
        # El kit del perfil EXISTE, pero ninguna linea tiene producto+precio que
        # Tukit pueda cobrar hoy: no es "no hay kit" (eso es el 404 de arriba),
        # es un kit sin nada comprable. Se distingue para no mentirle al
        # acudiente con "no tiene un kit de ese perfil". `CheckoutRechazado`
        # lleva su propio estado y el router lo reenvia verbatim.
        raise CheckoutRechazado(
            409,
            {
                "error": "kit_sin_lineas",
                "mensaje": "Este kit no tiene productos que Tukit pueda vender hoy.",
            },
        )

    colegios = sorted({h["colegio_id"] for h in hijos if h.get("colegio_id")})
    estado, orden = await comercio.crear_orden(
        {
            "usuario_id": str(usuario_id),
            "trabajo_id": str(trabajo_id),
            "hijos": len(hijos),
            "colegios": colegios,
            "lineas": lineas,
            "entrega": entrega,
        }
    )
    if estado != 201:
        raise CheckoutRechazado(estado, orden)

    estado, pago = await comercio.iniciar_pago(
        orden["pedido_id"],
        {"correo_cliente": correo, "metodo": metodo, "url_redireccion": url_redireccion},
    )
    if estado != 201:
        raise CheckoutRechazado(estado, pago)

    return {"pedido_id": orden["pedido_id"], "total": orden["total"], **pago}
