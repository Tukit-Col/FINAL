from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from ..modelos import EstadoResolucion, PerfilKit
from ..optimizador import (
    NOTA_CONSOLIDADA,
    Candidato,
    _objetivos,
    anclar_personaje,
    candidato_permitido,
    consolidar,
    filtros_de,
    recomendar,
    renglones_con_personaje,
    unidades_a_comprar,
)
from ..parseo import mensaje_para_papa, parsear_renglon

logger = logging.getLogger(__name__)


def _normalizar(renglones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalizados = []
    for crudo in renglones:
        demanda = parsear_renglon(crudo["texto"], cantidad=crudo.get("cantidad"))
        tipo = crudo.get("tipo_item_lista") or demanda.tipo_item
        modo = crudo.get("modo_lista") or demanda.modo_adquisicion
        normalizados.append(
            {
                **crudo,
                "tipo_item": tipo,
                "modo_adquisicion": modo,
                "cantidad": demanda.cantidad,
                "unidad_base": demanda.unidad_base,
                "url_externa": crudo.get("url_externa") or demanda.url_externa,
                "nota": demanda.nota,
                "mensaje": mensaje_para_papa(demanda),
                "busca_en_catalogo": tipo in {"util", "libro_libre"}
                and modo in {"mercado_abierto", "libro_libre"},
            }
        )
    return normalizados


def estado_desde_emparejamiento(emparejamiento: dict[str, Any], umbral: float) -> str:
    estado = emparejamiento.get("estado")
    if estado == "reconocido":
        if not emparejamiento.get("opciones"):
            return EstadoResolucion.HUECO_CATALOGO.value
        parecido = float(emparejamiento.get("parecido") or 0.0)
        return EstadoResolucion.RESUELTO_AUTO.value if parecido >= umbral else EstadoResolucion.AMBIGUO.value
    if estado in {"hueco_catalogo", "abstencion"}:
        return EstadoResolucion.HUECO_CATALOGO.value
    return EstadoResolucion.SIN_MATCH.value


def _candidato(opcion: dict[str, Any]) -> Candidato:
    return Candidato(
        sku=opcion.get("sku") or "",
        nombre=opcion.get("nombre") or "",
        nivel=opcion.get("nivel") or "confiable",
        precio_cop=opcion.get("precio_cop"),
        producto_id=opcion.get("producto_id"),
        marca=opcion.get("marca"),
        personaje=opcion.get("personaje"),
        imagen_url=opcion.get("imagen_url"),
        unidad_base=opcion.get("unidad_base") or "unidad",
        unidades_por_empaque=int(opcion.get("unidades_por_empaque") or 1),
        atributos=dict(opcion.get("atributos") or {}),
        cumple=bool(opcion.get("cumple", True)),
    )


def personajes_por_hijo(preferencias: dict[str, Any]) -> dict[str, str]:
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    return {str(hijo): str(valores[0]) for hijo, valores in por_hijo.items() if valores}


def clave_de_hijo(preferencias: dict[str, Any], linea_hijo: str, hijos_del_kit: list[str]) -> str | None:
    claves = [str(k) for k in (preferencias.get("personaje_por_hijo") or {})]
    if linea_hijo in claves:
        return linea_hijo
    if any(h in claves for h in hijos_del_kit) or linea_hijo not in hijos_del_kit:
        return None
    if len(claves) != len(hijos_del_kit) or len(hijos_del_kit) < 2:
        logger.debug(
            "hijo %s sin clave de personaje (claves=%s, hijos=%s): queda neutral",
            linea_hijo,
            claves,
            hijos_del_kit,
        )
        return None
    return claves[hijos_del_kit.index(linea_hijo)]


def personajes_de_los_hijos(preferencias: dict[str, Any], hijos_del_kit: list[str]) -> dict[str, str]:
    pedidos = personajes_por_hijo(preferencias)
    distintos = list(dict.fromkeys(hijos_del_kit))
    salida: dict[str, str] = {}
    for hijo in distintos:
        clave = clave_de_hijo(preferencias, hijo, distintos)
        if clave is not None and clave in pedidos:
            salida[hijo] = pedidos[clave]
    return salida


def _personaje_pedido(preferencias: dict[str, Any]) -> str | None:
    return next(iter(personajes_por_hijo(preferencias).values()), None)


def _anclar_kits(kits: list[Any], preferencias: dict[str, Any]) -> list[Any]:
    personaje = _personaje_pedido(preferencias)
    if personaje is None:
        return kits
    return [anclar_personaje(kit, personaje) for kit in kits]


def _candidato_de_swap(swap: dict[str, Any]) -> Candidato:
    return Candidato(
        sku=swap.get("sku") or "",
        nombre=swap.get("nombre") or "",
        nivel=swap.get("nivel") or "confiable",
        precio_cop=swap.get("precio_desde"),
        producto_id=swap.get("producto_id"),
        marca=swap.get("marca"),
        personaje=swap.get("personaje"),
        imagen_url=swap.get("imagen_url"),
        unidad_base=swap.get("unidad_base") or "unidad",
        unidades_por_empaque=int(swap.get("unidades_por_empaque") or 1),
        atributos=dict(swap.get("atributos") or {}),
        cumple=True,
    )


def _variantes(swap: Any) -> list[dict[str, Any]]:
    if not swap:
        return []
    return list(swap) if isinstance(swap, (list, tuple)) else [swap]


def inyectar_personaje_fan(
    kits: list[Any], swaps_por_hijo: dict[str, dict[str, Any]], preferencias: dict[str, Any]
) -> list[Any]:
    if not any(swaps_por_hijo.values()):
        return kits

    filtros = filtros_de(preferencias)

    recomputados: list[Any] = []
    for kit in kits:
        if kit.perfil != PerfilKit.FAN.value:
            recomputados.append(kit)
            continue

        llevan, sin_encaje = _lineas_con_swap(kit.lineas, swaps_por_hijo)

        def producto_de(indice: int, linea: Any, llevan: dict[int, dict[str, Any]] = llevan) -> Any:
            if indice not in llevan:
                return linea.elegido
            if filtros.activos and linea.elegido is None:
                return linea.elegido
            candidato = _candidato_de_swap(llevan[indice])
            if not candidato_permitido(candidato, linea.descripcion, filtros):
                return linea.elegido
            return candidato

        crudas = tuple(
            _linea_con_producto(linea, producto_de(i, linea)) for i, linea in enumerate(kit.lineas)
        )
        lineas, consolidaciones = consolidar(crudas)
        total = sum(li.subtotal_cop or 0 for li in lineas if not li.informativa)
        recomputados.append(
            replace(
                kit,
                lineas=lineas,
                consolidaciones=consolidaciones,
                total_cop=total,
                objetivos={
                    **_objetivos(lineas, total),
                    **({"personaje_sin_encaje": sin_encaje} if sin_encaje else {}),
                },
            )
        )

    return recomendar(recomputados, preferencias)


def _lineas_con_swap(
    lineas: Any, swaps_por_hijo: dict[str, dict[str, Any]]
) -> tuple[dict[int, dict[str, Any]], list[dict[str, str]]]:
    grupos: dict[tuple[str, str], list[tuple[int, str, dict[str, Any], str]]] = {}
    for indice, linea in enumerate(lineas):
        if linea.informativa or not _variantes(swaps_por_hijo.get(linea.hijo, {}).get(linea.concepto_codigo)):
            continue
        grupos.setdefault((linea.concepto_codigo, linea.hijo), []).append(
            (indice, linea.hijo, linea.atributos_impuestos, linea.descripcion)
        )
    llevan: dict[int, dict[str, Any]] = {}
    sin_encaje: list[dict[str, str]] = []
    for (concepto, hijo), renglones in grupos.items():
        variantes = _variantes(swaps_por_hijo[hijo][concepto])
        elegidos = renglones_con_personaje(renglones, variantes)
        if not elegidos:
            personaje = next((v.get("personaje") for v in variantes if v.get("personaje")), "")
            sin_encaje.append({"hijo": hijo, "concepto": concepto, "personaje": str(personaje)})
        llevan.update({indice: variantes[i] for indice, i in elegidos.items()})
    return llevan, sin_encaje


def _linea_con_producto(linea: Any, elegido: Any) -> Any:
    if linea.informativa or elegido is None:
        return linea
    mensaje = linea.mensaje
    if mensaje and mensaje.startswith(NOTA_CONSOLIDADA):
        mensaje = None
    unidades = unidades_a_comprar(linea.cantidad_pedida, elegido.unidades_por_empaque)
    subtotal = None if elegido.precio_cop is None else elegido.precio_cop * unidades
    return replace(
        linea,
        elegido=elegido,
        unidad_base=elegido.unidad_base or linea.unidad_base,
        unidades_por_empaque=elegido.unidades_por_empaque,
        unidades_a_comprar=unidades,
        precio_unitario_cop=elegido.precio_cop,
        subtotal_cop=subtotal,
        mensaje=mensaje,
    )
