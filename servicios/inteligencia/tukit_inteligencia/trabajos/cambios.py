from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert, select, update
from tukit_comun.cifrado import cifrador_desde_entorno

from ..modelos import (
    EstadoTrabajo,
    PerfilKit,
)
from ..optimizador import (
    Candidato,
    FiltrosDuros,
    candidato_permitido,
    filtros_de,
    unidades_a_comprar,
)
from ..remoto import ClienteCatalogo, RemotoCaido
from ..repositorios.trabajos import TrabajoNoExiste
from .anclas import _anclas_de_personaje
from .base import BANDEJA, KIT_CANONICO, TRABAJO, CambioNoPermitido, ahora
from .formas import _lineas_aplicadas
from .lectura import ver


async def _linea_para_cambiar(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    *,
    usuario_id: uuid.UUID | None,
    catalogo: ClienteCatalogo,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    async with motor.engine.begin() as conexion:
        cabeza = (
            await conexion.execute(
                select(TRABAJO.c.estado, TRABAJO.c.usuario_id, TRABAJO.c.cambios).where(
                    TRABAJO.c.id == trabajo_id
                )
            )
        ).one_or_none()
    if cabeza is None:
        raise TrabajoNoExiste(str(trabajo_id))
    if cabeza.usuario_id is not None and cabeza.usuario_id != usuario_id:
        raise CambioNoPermitido(
            "solicitud_ajena", "Inicia sesión con la cuenta que hizo esta solicitud para cambiarla.", 403
        )
    if cabeza.estado != EstadoTrabajo.PUBLICADO.value:
        raise CambioNoPermitido("kit_no_publicado", "Tu kit todavía no está listo para cambios.")

    vista = await ver(motor, trabajo_id, catalogo=catalogo)
    kit = next((k for k in vista["kits"] if k["perfil"] == perfil), None)
    linea = next((ln for ln in (kit or {}).get("lineas", []) if ln["item_id"] == str(item_id)), None)
    if kit is None or linea is None:
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil}/{item_id}")
    actual = linea.get("producto_elegido")
    if linea["informativa"] or not actual:
        raise CambioNoPermitido("linea_sin_producto", "Este renglón no tiene un producto para cambiar.")
    if any(c.get("sku") == actual.get("sku") for c in kit.get("consolidaciones") or []):
        raise CambioNoPermitido(
            "linea_consolidada",
            "Este producto se compra junto con el de tu otro hijo y no se cambia por separado.",
        )
    return cabeza, kit, linea


async def _guardar_cambios(motor: Any, trabajo_id: uuid.UUID, cambios: dict[str, Any]) -> None:
    cambios = {p: {i: c for i, c in kit.items() if c} for p, kit in cambios.items()}
    cambios = {p: c for p, c in cambios.items() if c}
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(cambios=cambios, actualizado_en=ahora())
        )


async def _filtros_del_trabajo(motor: Any, trabajo_id: uuid.UUID) -> FiltrosDuros:
    async with motor.engine.connect() as conexion:
        cifradas = (
            await conexion.execute(select(TRABAJO.c.preferencias_cifradas).where(TRABAJO.c.id == trabajo_id))
        ).scalar_one_or_none()
    return filtros_de(cifrador_desde_entorno().descifrar_json(cifradas) if cifradas else None)


def _producto_permitido(producto: dict[str, Any], texto_renglon: str, filtros: FiltrosDuros) -> bool:
    if not filtros.activos:
        return True
    candidato = Candidato(
        sku=str(producto.get("sku")),
        nombre=str(producto.get("nombre") or ""),
        nivel=str(producto.get("nivel") or ""),
        precio_cop=producto.get("precio_desde", producto.get("precio")),
        marca=producto.get("marca"),
    )
    return candidato_permitido(candidato, texto_renglon, filtros)


async def cambiar_producto_del_acudiente(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    sku: str,
    *,
    usuario_id: uuid.UUID | None,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    cabeza, _kit, linea = await _linea_para_cambiar(
        motor, trabajo_id, perfil, item_id, usuario_id=usuario_id, catalogo=catalogo
    )
    actual = linea["producto_elegido"]
    permitidos = {actual.get("sku")} | {a.get("sku") for a in linea.get("alternativas") or []}
    producto: dict[str, Any] | None = None
    if sku not in permitidos:
        producto = await _producto_del_mismo_concepto(catalogo, sku, linea.get("concepto"))
        if producto is None:
            raise CambioNoPermitido(
                "producto_no_permitido", "Ese producto no es una opción para este renglón.", 422
            )
        filtros = await _filtros_del_trabajo(motor, trabajo_id)
        if not _producto_permitido(producto, linea.get("descripcion") or "", filtros):
            raise CambioNoPermitido(
                "producto_excluido",
                "Ese producto va contra los filtros de tu kit (marca excluida o solo disponibles).",
                422,
            )
    respuesta = {"trabajo_id": str(trabajo_id), "perfil": perfil, "item_id": str(item_id), "sku": sku}
    if sku == actual.get("sku"):
        return respuesta

    cambios = {p: {i: dict(c) for i, c in kit.items()} for p, kit in dict(cabeza.cambios or {}).items()}
    del_item = cambios.setdefault(perfil, {}).setdefault(str(item_id), {})
    sugerido = linea.get("sku_sugerido") or actual.get("sku")
    if sku == sugerido:
        descartado = del_item.get("descartado")
        del_item.clear()
        if descartado:
            del_item["descartado"] = True
    else:
        producto = producto or await catalogo.producto(sku)
        precio = producto.get("precio_desde")
        if precio is None:
            raise CambioNoPermitido("producto_sin_precio", "Ese producto no tiene precio hoy; elige otro.")
        del_item.update(
            {
                "sku": sku,
                "nombre": producto.get("nombre"),
                "marca": producto.get("marca"),
                "nivel": producto.get("nivel"),
                "personaje": producto.get("personaje"),
                "imagen_url": producto.get("imagen_url"),
                "unidades_por_empaque": int(producto.get("unidades_por_empaque") or 1),
                "precio": int(precio),
            }
        )
    await _guardar_cambios(motor, trabajo_id, cambios)
    return respuesta


async def _producto_del_mismo_concepto(
    catalogo: ClienteCatalogo, sku: str, concepto: str | None
) -> dict[str, Any] | None:
    if not concepto:
        return None
    try:
        producto = await catalogo.producto(sku)
    except (KeyError, RemotoCaido):
        return None
    if (producto.get("concepto") or {}).get("codigo") != concepto:
        return None
    return producto


async def opciones_de_la_linea(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    *,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    vista = await ver(motor, trabajo_id, catalogo=catalogo)
    kit = next((k for k in vista["kits"] if k["perfil"] == perfil), None)
    linea = next((ln for ln in (kit or {}).get("lineas", []) if ln["item_id"] == str(item_id)), None)
    if kit is None or linea is None:
        raise TrabajoNoExiste(f"{trabajo_id}/{perfil}/{item_id}")
    return await opciones_de_una_linea(motor, trabajo_id, linea, catalogo=catalogo)


async def opciones_de_una_linea(
    motor: Any, trabajo_id: uuid.UUID, linea: dict[str, Any], *, catalogo: ClienteCatalogo
) -> dict[str, Any]:
    item_id = linea["item_id"]
    actual = linea.get("producto_elegido") or {}
    concepto = linea.get("concepto")
    if linea["informativa"] or not actual or not concepto:
        return {"item_id": str(item_id), "concepto": concepto, "opciones": []}
    clave_subtotal = "subtotal_descartado" if linea.get("descartado") else "subtotal_linea"
    subtotal_hoy = linea.get(clave_subtotal)
    sugerido = linea.get("sku_sugerido") or actual.get("sku")
    pedida = int(linea.get("cantidad_pedida") or 0)

    filtros = await _filtros_del_trabajo(motor, trabajo_id)
    texto_renglon = linea.get("descripcion") or ""
    productos = await catalogo.productos_del_concepto(str(concepto))
    por_sku = {p["sku"]: p for p in productos if _producto_permitido(p, texto_renglon, filtros)}
    for conocido in [actual, *(linea.get("alternativas") or [])]:
        sku = conocido.get("sku")
        if sku and sku not in por_sku:
            precio = conocido.get("precio", conocido.get("precio_cop"))
            if precio is not None:
                por_sku[sku] = {**conocido, "precio_desde": precio, "unidades_por_empaque": 1}

    opciones = []
    for p in por_sku.values():
        precio = p.get("precio_desde")
        if precio is None:
            continue
        empaque = int(p.get("unidades_por_empaque") or 1)
        unidades = unidades_a_comprar(pedida, empaque)
        subtotal = int(precio) * unidades
        opciones.append(
            {
                "sku": p["sku"],
                "nombre": p.get("nombre"),
                "marca": p.get("marca"),
                "nivel": p.get("nivel"),
                "personaje": p.get("personaje"),
                "imagen_url": p.get("imagen_url"),
                "precio": int(precio),
                "unidades_por_empaque": empaque,
                "unidades_a_comprar": unidades,
                "subtotal": subtotal,
                "diferencia": None if subtotal_hoy is None else subtotal - int(subtotal_hoy),
                "en_kit": p["sku"] == actual.get("sku"),
                "sugerido": p["sku"] == sugerido,
            }
        )
    opciones.sort(key=lambda o: (not o["en_kit"], o["subtotal"]))
    return {"item_id": str(item_id), "concepto": concepto, "opciones": opciones}


async def descartar_linea_del_acudiente(
    motor: Any,
    trabajo_id: uuid.UUID,
    perfil: str,
    item_id: uuid.UUID,
    *,
    descartar: bool,
    usuario_id: uuid.UUID | None,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    cabeza, _kit, _linea = await _linea_para_cambiar(
        motor, trabajo_id, perfil, item_id, usuario_id=usuario_id, catalogo=catalogo
    )
    cambios = {p: {i: dict(c) for i, c in kit.items()} for p, kit in dict(cabeza.cambios or {}).items()}
    del_item = cambios.setdefault(perfil, {}).setdefault(str(item_id), {})
    if descartar:
        del_item["descartado"] = True
    else:
        del_item.pop("descartado", None)
    await _guardar_cambios(motor, trabajo_id, cambios)
    return {
        "trabajo_id": str(trabajo_id),
        "perfil": perfil,
        "item_id": str(item_id),
        "descartado": descartar,
    }


async def aplicar_canonico(
    motor: Any,
    *,
    colegio_id: str,
    grado: str,
    anio_lectivo: int,
    perfil: str,
    personaje: str | None = None,
    apodo: str | None = None,
    usuario_id: uuid.UUID | None = None,
    catalogo: ClienteCatalogo,
) -> dict[str, Any]:
    swaps = await _anclas_de_personaje(catalogo, personaje)

    parent_id = uuid.uuid4()
    async with motor.engine.begin() as conexion:
        canonico = (
            await conexion.execute(
                select(KIT_CANONICO.c.trabajo_id).where(
                    KIT_CANONICO.c.colegio_id == colegio_id,
                    KIT_CANONICO.c.grado == grado,
                    KIT_CANONICO.c.anio_lectivo == anio_lectivo,
                )
            )
        ).one_or_none()
        if canonico is None:
            raise TrabajoNoExiste(f"cache {colegio_id}/{grado}/{anio_lectivo}")

        if perfil == PerfilKit.FAN.value:
            base, swaps_kit = PerfilKit.AHORRADOR.value, swaps
        elif perfil in (PerfilKit.AHORRADOR.value, PerfilKit.PREMIUM.value):
            base, swaps_kit = perfil, {}
        else:
            raise TrabajoNoExiste(f"cache {colegio_id}/{grado}/{anio_lectivo}/{perfil}")
        lineas_frias, total, _ = await _lineas_aplicadas(conexion, canonico.trabajo_id, base, swaps_kit)

        await conexion.execute(
            insert(TRABAJO).values(
                id=parent_id,
                usuario_id=usuario_id,
                estado=EstadoTrabajo.PUBLICADO.value,
                origen="parent_apply",
                hijos=[
                    {
                        "colegio_id": colegio_id,
                        "grado": grado,
                        "anio_lectivo": anio_lectivo,
                        "canonico_trabajo_id": str(canonico.trabajo_id),
                        "perfil": perfil,
                        "personaje": personaje,
                        **({"apodo": apodo.strip()} if apodo and apodo.strip() else {}),
                    }
                ],
                terminado_en=ahora(),
            )
        )
        await conexion.execute(
            insert(BANDEJA).values(
                tipo="pedido_solicitado",
                agregado_tipo="trabajo_pipeline",
                agregado_id=parent_id,
                carga={
                    "trabajo_id": str(parent_id),
                    "canonico_trabajo_id": str(canonico.trabajo_id),
                    "usuario_id": str(usuario_id) if usuario_id else None,
                    "colegio_id": colegio_id,
                    "grado": grado,
                    "anio_lectivo": anio_lectivo,
                    "perfil": perfil,
                    "personaje": personaje,
                    "total_cop": total,
                    "lineas": lineas_frias,
                    "solicitado_en": ahora().isoformat(),
                },
            )
        )
    return {"trabajo_id": str(parent_id), "perfil": perfil, "personaje": personaje, "total": total}
