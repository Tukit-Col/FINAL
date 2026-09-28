"""Helpers puros del pipeline de resolucion (ADR 0019).

Las decisiones que no tocan la base ni la red: traducir el vocabulario del
catalogo a un `EstadoResolucion` del contrato, normalizar un renglon crudo a una
demanda con lo que la lista ya sabia, y anclar los conceptos del personaje
pedido al tope del kit. `trabajos.py` las orquesta dentro de sus transacciones;
aqui son funciones sin efectos, probables con `assert`.

Importan solo de `modelos`, `optimizador` y `parseo` —ninguno arrastra
SQLAlchemy/FastAPI/httpx a nivel de modulo—, asi que `dominio/` queda puro.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..modelos import EstadoResolucion
from ..optimizador import Candidato, PerfilKit, anclar_personaje, unidades_a_comprar
from ..parseo import mensaje_para_papa, parsear_renglon


def _normalizar(renglones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cada renglon a una demanda, con lo que la lista ya sabia por encima.

    El parseo lee el texto; la lista oficial, cuando existe, ya trae el tipo
    y el modo revisados por quien la cargo. Se prefiere lo de la lista porque
    es un dato curado y el parseo es una heuristica sobre texto: adivinar
    encima de un dato que ya esta es como se pierde informacion buena.
    """
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
    """Traduce el vocabulario del catalogo al `EstadoResolucion` del contrato.

    La traduccion que importa es la de `abstencion`. El catalogo se abstiene
    cuando entendio el concepto y ningun producto declara el atributo que el
    renglon exige ("block tamano oficio"), y eso es exactamente
    `HUECO_CATALOGO`: te entendi y no lo tengo. Mandarlo a `SIN_MATCH` seria
    decir "no te entendi", que es la confusion que el contrato separa a
    proposito porque solo una de las dos se puede responder con una
    alternativa.
    """
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


def _personaje_pedido(preferencias: dict[str, Any]) -> str | None:
    """El personaje que el acudiente pidio, para anclar sus 4 items al tope.

    El anclaje reordena el kit completo, asi que se toma el primer personaje
    declarado en `personaje_por_hijo`. En el caso comun (un hijo con un
    personaje) es exactamente el suyo; con varios hijos se ancla el primero,
    que es suficiente para el gesto de "poner arriba lo del personaje" sin
    reordenar de forma ambigua entre hermanos.
    """
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    for valores in por_hijo.values():
        if valores:
            return str(valores[0])
    return None


def _anclar_kits(kits: list[Any], preferencias: dict[str, Any]) -> list[Any]:
    """Sube los 4 conceptos ancla del personaje pedido al tope de cada kit.

    Post-proceso puro: no cambia totales ni que producto se eligio (NSGA-II
    queda intacto). Si no se pidio personaje, `anclar_personaje` devuelve el
    kit sin tocar.
    """
    personaje = _personaje_pedido(preferencias)
    if personaje is None:
        return kits
    return [anclar_personaje(kit, personaje) for kit in kits]


def _candidato_de_swap(swap: dict[str, Any]) -> Candidato:
    """Un `Candidato` del producto de personaje que trae el catalogo (`precio_desde`)."""
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
        atributos={},
        cumple=True,
    )


def inyectar_personaje_fan(kits: list[Any], swaps: dict[str, dict[str, Any]]) -> list[Any]:
    """Mete el producto de personaje en las anclas del kit Fan y recalcula su total.

    En las rutas verificada/preview el catalogo entrega `/resueltos` con una
    opcion por nivel y SIN la variante de personaje (es una via aparte, curada);
    por eso el optimizador nunca ve un candidato de personaje que elegir y
    `anclar_personaje` no encuentra nada que subir. Aca se cierra ese hueco: para
    cada concepto ancla que el catalogo si surte con el personaje (`swaps`), se
    reemplaza el `elegido` de la linea del kit Fan por ese producto, con la misma
    aritmetica del armado (techo(pedida/empaque)) y se rehace `total_cop`. Solo
    toca el Fan —los otros perfiles son neutrales a proposito—; sin swaps
    devuelve los kits intactos.
    """
    if not swaps:
        return kits

    resultado: list[Any] = []
    for kit in kits:
        if kit.perfil != PerfilKit.FAN.value:
            resultado.append(kit)
            continue

        lineas = []
        for linea in kit.lineas:
            swap = swaps.get(linea.concepto_codigo) if linea.concepto_codigo else None
            if swap is None or linea.informativa:
                lineas.append(linea)
                continue
            elegido = _candidato_de_swap(swap)
            unidades = unidades_a_comprar(linea.cantidad_pedida, elegido.unidades_por_empaque)
            subtotal = None if elegido.precio_cop is None else elegido.precio_cop * unidades
            lineas.append(
                replace(
                    linea,
                    elegido=elegido,
                    unidad_base=elegido.unidad_base or linea.unidad_base,
                    unidades_por_empaque=elegido.unidades_por_empaque,
                    unidades_a_comprar=unidades,
                    precio_unitario_cop=elegido.precio_cop,
                    subtotal_cop=subtotal,
                )
            )
        total = sum(li.subtotal_cop or 0 for li in lineas if not li.informativa)
        resultado.append(replace(kit, lineas=tuple(lineas), total_cop=total))
    return resultado
