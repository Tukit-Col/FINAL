from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from ..optimizador import (
    ORDEN_NIVEL,
    renglones_con_personaje,
    unidades_a_comprar,
)
from ..repositorios.trabajos import TrabajoNoExiste
from .base import ANIO_LECTIVO_POR_OMISION, KIT, LINEA, RESOLUCION


def _linea_publica(fila: Any) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "item_id": str(fila.item_crudo_id),
        "hijo": fila.hijo_referencia,
        "orden": int(fila.orden),
        "descripcion": fila.descripcion,
        "tipo": fila.tipo,
        "estado_resolucion": fila.estado_resolucion,
        "cantidad_pedida": int(fila.cantidad_pedida),
        "unidad_base": fila.unidad_base,
        "unidades_por_empaque": int(fila.unidades_por_empaque),
        "unidades_a_comprar": int(fila.unidades_a_comprar),
        "informativa": bool(fila.informativa),
        "subtotal_linea": fila.subtotal_cop,
        "mensaje": fila.mensaje,
    }
    concepto = getattr(fila, "concepto_codigo", None)
    if concepto:
        cuerpo["concepto"] = concepto
    if fila.instruccion_colegio:
        cuerpo["instruccion_colegio"] = fila.instruccion_colegio
    if fila.url_externa:
        cuerpo["url_externa"] = fila.url_externa
    if fila.no_consolidable:
        cuerpo["no_consolidable"] = True
        cuerpo["motivo_no_consolidable"] = fila.motivo_no_consolidable
    if fila.sku:
        cuerpo["producto_elegido"] = {
            "sku": fila.sku,
            "nombre": fila.nombre_producto,
            "marca": fila.marca,
            "nivel": fila.nivel,
            "personaje": fila.personaje,
            "imagen_url": fila.imagen_url,
            "precio": fila.precio_unitario_cop,
        }
    cuerpo["alternativas"] = list(fila.alternativas or ())
    return cuerpo


def _sin_apodo(hijo: Any) -> Any:
    return {k: v for k, v in hijo.items() if k != "apodo"} if isinstance(hijo, dict) else hijo


def _identidad_de_grado(hijos: Any) -> tuple[str, str, int, str | None] | None:
    lista = list(hijos or ())
    if len(lista) != 1:
        return None
    hijo = lista[0]
    colegio_id = str(hijo.get("colegio_id") or "")
    grado = str(hijo.get("grado") or "")
    if not (colegio_id and grado):
        return None
    anio = int(hijo.get("anio_lectivo") or ANIO_LECTIVO_POR_OMISION)
    version = hijo.get("version_id")
    return colegio_id, grado, anio, str(version) if version else None


def _objetivos_de_lineas(lineas: list[dict[str, Any]], total: int) -> dict[str, float | int]:
    comprables = [linea for linea in lineas if not linea["informativa"] and not linea.get("descartado")]
    if not comprables:
        return {"costo": total, "fidelidad": 0.0, "disponibilidad": 0.0}
    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    suma_fidelidad = 0.0
    con_precio = 0
    for linea in comprables:
        producto = linea.get("producto_elegido") or {}
        nivel = producto.get("nivel")
        if nivel is not None:
            rango = ORDEN_NIVEL.index(nivel) if nivel in ORDEN_NIVEL else len(ORDEN_NIVEL)
            suma_fidelidad += rango / tope_nivel
        if producto.get("precio") is not None:
            con_precio += 1
    return {
        "costo": total,
        "fidelidad": round(suma_fidelidad / len(comprables), 3),
        "disponibilidad": round(con_precio / len(comprables), 3),
    }


def _alternativa_de(producto: dict[str, Any]) -> dict[str, Any]:
    return {
        "sku": producto.get("sku"),
        "nombre": producto.get("nombre"),
        "nivel": producto.get("nivel"),
        "precio_cop": producto.get("precio"),
        "imagen_url": producto.get("imagen_url"),
    }


def _aplicar_cambios(
    lineas: list[dict[str, Any]], cambios_del_kit: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    salida: list[dict[str, Any]] = []
    for linea in lineas:
        cambio = cambios_del_kit.get(str(linea.get("item_id")))
        sugerido = linea.get("producto_elegido")
        if cambio and sugerido and not linea["informativa"]:
            linea = dict(linea)
            if cambio.get("sku"):
                empaque = int(cambio.get("unidades_por_empaque") or 1)
                precio = cambio.get("precio")
                unidades = unidades_a_comprar(int(linea.get("cantidad_pedida") or 0), empaque)
                if linea.get("unidades_a_comprar") == 0:
                    unidades = 0
                linea["producto_elegido"] = {
                    "sku": cambio.get("sku"),
                    "nombre": cambio.get("nombre"),
                    "marca": cambio.get("marca"),
                    "nivel": cambio.get("nivel"),
                    "personaje": cambio.get("personaje"),
                    "imagen_url": cambio.get("imagen_url"),
                    "precio": precio,
                }
                linea["unidades_por_empaque"] = empaque
                linea["unidades_a_comprar"] = unidades
                linea["subtotal_linea"] = None if precio is None else precio * unidades
                linea["alternativas"] = [_alternativa_de(sugerido)] + [
                    a for a in (linea.get("alternativas") or []) if a.get("sku") != cambio.get("sku")
                ]
                linea["cambiado_por_acudiente"] = True
                linea["sku_sugerido"] = sugerido.get("sku")
            if cambio.get("descartado"):
                linea["descartado"] = True
                linea["subtotal_descartado"] = linea.get("subtotal_linea")
                linea["subtotal_linea"] = None
        salida.append(linea)
    total = sum(
        int(linea.get("subtotal_linea") or 0)
        for linea in salida
        if not linea["informativa"] and not linea.get("descartado")
    )
    return salida, total


async def _lineas_aplicadas(
    conexion: Any, canonico_trabajo_id: uuid.UUID, perfil: str, swaps: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], int, list[dict[str, str]]]:
    kit = (
        await conexion.execute(
            select(KIT.c.id, KIT.c.perfil).where(
                KIT.c.trabajo_id == canonico_trabajo_id, KIT.c.perfil == perfil
            )
        )
    ).one_or_none()
    if kit is None:
        raise TrabajoNoExiste(f"{canonico_trabajo_id}/{perfil}")

    lineas: list[dict[str, Any]] = []
    total = 0
    filas = await conexion.execute(
        select(LINEA, RESOLUCION.c.concepto_codigo, RESOLUCION.c.atributos_impuestos)
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
    filas = list(filas)

    grupos: dict[str, list[tuple[int, str, dict[str, Any], str]]] = {}
    for indice, fila in enumerate(filas):
        concepto = getattr(fila, "concepto_codigo", None)
        if concepto in swaps and not fila.informativa:
            grupos.setdefault(concepto, []).append(
                (indice, fila.hijo_referencia, dict(fila.atributos_impuestos or {}), fila.descripcion)
            )
    llevan: dict[int, dict[str, Any]] = {}
    sin_encaje: list[dict[str, str]] = []
    for concepto, renglones_del_concepto in grupos.items():
        variantes = list(swaps[concepto])
        elegidos = renglones_con_personaje(renglones_del_concepto, variantes)
        if not elegidos:
            personaje = next((v.get("personaje") for v in variantes if v.get("personaje")), "")
            hijo_ref = renglones_del_concepto[0][1]
            sin_encaje.append({"hijo": str(hijo_ref), "concepto": concepto, "personaje": str(personaje)})
        llevan.update({indice: variantes[i] for indice, i in elegidos.items()})

    for indice, fila in enumerate(filas):
        linea = _linea_publica(fila)
        swap = llevan.get(indice)
        if swap and not fila.informativa:
            empaque = int(swap.get("unidades_por_empaque") or 1)
            precio = swap.get("precio_desde")
            unidades = unidades_a_comprar(int(fila.cantidad_pedida or 0), empaque)
            if fila.sku and fila.unidades_a_comprar == 0:
                unidades = 0
            linea["producto_elegido"] = {
                "sku": swap.get("sku"),
                "nombre": swap.get("nombre"),
                "marca": swap.get("marca"),
                "nivel": swap.get("nivel"),
                "personaje": swap.get("personaje"),
                "imagen_url": swap.get("imagen_url"),
                "precio": precio,
            }
            linea["unidades_por_empaque"] = empaque
            linea["unidades_a_comprar"] = unidades
            linea["subtotal_linea"] = None if precio is None else precio * unidades
        if not linea["informativa"] and linea.get("subtotal_linea"):
            total += int(linea["subtotal_linea"])
        lineas.append(linea)
    return lineas, total, sin_encaje
