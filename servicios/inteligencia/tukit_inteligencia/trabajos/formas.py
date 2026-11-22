"""Forma publica de las lineas del kit y aplicacion de los cambios pendientes del acudiente."""

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
    # El codigo del concepto (`C001`) sale de RESOLUCION, no de LINEA: es la
    # llave con la que la matriz agrupa y con la que el interruptor de personaje
    # del Fan encuentra sus anclas. `getattr` porque los otros llamadores de
    # `_linea_publica` pasan una fila de solo-LINEA sin el join.
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
    """El hijo sin su `apodo`: lo que ve quien no es el acudiente."""
    return {k: v for k, v in hijo.items() if k != "apodo"} if isinstance(hijo, dict) else hijo


def _identidad_de_grado(hijos: Any) -> tuple[str, str, int, str | None] | None:
    """(colegio, grado, anio, version_id) de un trabajo de UN solo hijo, o None."""
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
    """Los objetivos de display de un kit aplicado, desde sus lineas publicas.

    El kit de la ruta rapida no tiene fila propia en `kit` (es un puntero al
    canonico, con el personaje aplicado), asi que sus objetivos se recalculan
    con la misma regla que `optimizador._objetivos`: solo lo comprable, la
    fidelidad como nivel de marca promedio en [0, 1] y la disponibilidad como
    fraccion de lineas con precio. Sin esto iban vacios y la web pintaba
    "NaN% con precio confirmado".
    """
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
    """Un producto elegido, con la forma de una alternativa guardada en la linea."""
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
    """Las lineas de un kit con lo que el acudiente cambio, y su total.

    Un cambio puede traer un producto elegido (`sku`) y/o la marca `descartado`.
    El producto elegido reemplaza al de su linea con la misma aritmetica del
    armado (techo(pedida/empaque)) y deja el sugerido como una alternativa mas,
    para que siempre se pueda volver a el; la linea queda marcada
    (`cambiado_por_acudiente`, `sku_sugerido`) para que la pantalla lo diga.
    Una linea descartada ("ya lo tengo") se queda en el kit, marcada
    `descartado`, pero sin subtotal: no suma al total y no entra a la orden. Su
    subtotal anterior viaja en `subtotal_descartado` para poder mostrar cuanto
    se ahorra y deshacerlo. El total se vuelve a sumar desde las lineas, que es
    como lo suma el armado (`_recalcular_total_kit`).
    """
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
                    unidades = 0  # otra linea ya la cubre («Ya va en la linea 58»)
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
    """Las lineas del kit canonico de un perfil, con el personaje aplicado, el total y lo que no cupo.

    El tercer valor es `personaje_sin_encaje` (misma forma que en el armado):
    cada concepto ancla con variantes de personaje pero sin renglon que las acepte.

    Es la fuente unica del kit aplicado: la usan tanto `aplicar_canonico` (para
    congelar el pedido) como `ver` (para pintarle al acudiente su kit sin copiar
    filas). Sobre un ancla con personaje elegido congela el producto del
    personaje en vez del neutral, con la misma aritmetica del armado
    (techo(pedida/empaque)); una linea informativa nunca lleva precio.
    """
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

    # El producto de personaje no va en cada renglon del concepto: se reparte con
    # la misma regla del armado (una vez por hijo, solo donde el renglon lo
    # acepta; ver `renglones_con_personaje`). Sin esto, el kit Fan de la ruta
    # rapida repetia el mismo cuaderno de personaje en todos los cuadernos.
    grupos: dict[str, list[tuple[int, str, dict[str, Any], str]]] = {}
    for indice, fila in enumerate(filas):
        concepto = getattr(fila, "concepto_codigo", None)
        if concepto in swaps and not fila.informativa:
            grupos.setdefault(concepto, []).append(
                (indice, fila.hijo_referencia, dict(fila.atributos_impuestos or {}), fila.descripcion)
            )
    # Cada renglon que lleva personaje recibe la variante que mejor le encaja
    # (misma regla que `inyectar_personaje_fan`), no siempre la primera.
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
                unidades = 0  # otra linea ya la cubre: no se cobra dos veces
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
