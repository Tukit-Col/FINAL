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
        personajes_por_hijo_pa: dict[str, list[str]] | None = None
        recomendado: dict[str, Any] | None = None
        cambios: dict[str, Any] = dict(cabeza.cambios or {})

        if mostrar and cabeza.origen == "parent_apply":
            hijo = (list(cabeza.hijos or ()) or [{}])[0]
            canonico_id = hijo.get("canonico_trabajo_id")
            perfil = str(hijo.get("perfil") or "")
            if canonico_id and perfil:
                personaje = hijo.get("personaje")
                swaps = await _anclas_de_personaje(catalogo, personaje) if catalogo else {}
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
                            "personaje_sin_encaje": sin_encaje,
                            "lineas": lineas,
                            "consolidaciones": [],
                            "informativas": sum(1 for linea in lineas if linea["informativa"]),
                        }
                    )
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
                "contacto_id": str(cabeza.usuario_id) if cabeza.usuario_id else "",
                "lineas_pendientes": [str(f.id) for f in pendientes],
            }

    return {
        "trabajo_id": str(cabeza.id),
        "estado": cabeza.estado,
        "origen": cabeza.origen,
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
    hijos = list(cabeza.hijos or ())
    if cabeza.origen == "parent_apply":
        personaje = (hijos[0] if hijos else {}).get("personaje")
        return {"canonico": [str(personaje)]} if personaje else {}
    if not cabeza.preferencias_cifradas:
        return {}
    try:
        preferencias = cifrador_desde_entorno().descifrar_json(cabeza.preferencias_cifradas) or {}
    except Exception:
        logger.warning("preferencias ilegibles al exponer personajes_por_hijo", exc_info=True)
        return {}
    pedidos = {
        str(hijo): [str(p) for p in valores if p]
        for hijo, valores in (preferencias.get("personaje_por_hijo") or {}).items()
        if valores
    }
    referencias = [str(h.get("referencia")) for h in hijos if isinstance(h, dict) and h.get("referencia")]
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
    async with motor.engine.begin() as conexion:
        cabeza = (await conexion.execute(select(TRABAJO).where(TRABAJO.c.id == trabajo_id))).one_or_none()
        if cabeza is None:
            raise TrabajoNoExiste(str(trabajo_id))
        usuario_id = cabeza.usuario_id
        hijos = list(cabeza.hijos or ())
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
