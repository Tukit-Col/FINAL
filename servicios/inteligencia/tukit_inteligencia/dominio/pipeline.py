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
from ..optimizador import (
    Candidato,
    PerfilKit,
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
        # Los atributos del producto de personaje deciden en que renglones cabe
        # (un cuaderno argollado no entra donde el colegio pidio cosido).
        atributos=dict(swap.get("atributos") or {}),
        cumple=True,
    )


def inyectar_personaje_fan(
    kits: list[Any], swaps: dict[str, dict[str, Any]], preferencias: dict[str, Any]
) -> list[Any]:
    """Mete el producto de personaje en las anclas del kit Fan y rehace sus numeros.

    En las rutas verificada/preview el catalogo entrega `/resueltos` con una
    opcion por nivel y SIN la variante de personaje (es una via aparte, curada);
    por eso el optimizador nunca ve un candidato de personaje que elegir y
    `anclar_personaje` no encuentra nada que subir. Aca se cierra ese hueco: para
    cada concepto ancla que el catalogo si surte con el personaje (`swaps`), se
    reemplaza el `elegido` de la linea del kit Fan por ese producto, con la misma
    aritmetica del armado (techo(pedida/empaque)).

    Como el swap cambia el precio del Fan DESPUES de que `armar_los_tres` calculo
    su `total_cop`, sus `objetivos` (incluido `costo`) y el veredicto de
    presupuesto de `recomendar`, hay que rehacer los tres o el kit mostraria un
    total nuevo con objetivos y "cabe en tu presupuesto" viejos —una mentira en
    una pantalla de plata—. Se recomputan `total_cop`/`objetivos` del Fan y se
    re-corre `recomendar` sobre los tres para que la marca y el veredicto de
    presupuesto reflejen los precios verdaderos. Solo toca el Fan; sin swaps
    devuelve los kits intactos (la ruta sin personaje queda byte a byte igual).
    """
    if not swaps:
        return kits

    # El producto de personaje viene del catalogo por una via aparte y no pasa por
    # `armar_los_tres`, asi que los filtros duros del acudiente se aplican aqui
    # tambien: sin esto el Fan podia traer justo la marca que pidio no ver.
    filtros = filtros_de(preferencias)

    recomputados: list[Any] = []
    for kit in kits:
        if kit.perfil != PerfilKit.FAN.value:
            recomputados.append(kit)
            continue

        # Se reconstruye cada linea del Fan en su forma PRE-consolidacion (con el
        # producto de personaje donde aplica) y se vuelve a correr `consolidar`:
        # `armar_los_tres` ya habia consolidado sobre el sku neutral, y cambiar el
        # producto despues sin re-consolidar cobraria dos veces un ancla que dos
        # hermanos comparten (el empaque conjunto se pierde). Re-armar sobre el
        # mismo `consolidar` reproduce lo que el optimizador habria hecho si el
        # producto de personaje hubiera sido candidato. Ambos hermanos reciben el
        # MISMO producto por concepto (los swaps se indexan por concepto), asi que
        # el grupo vuelve a unirse y las notas se regeneran con el sku correcto.
        #
        # El producto de personaje NO va en todos los renglones del concepto: el
        # catalogo entrega uno solo por concepto y personaje, y ponerlo en cada
        # cuaderno de la lista (cuadriculado, cosido, grande, argollado...)
        # repetia el mismo Spiderman de $36.900 cinco veces. `llevan` elige en
        # cuales cabe, una vez por hijo (ver `renglones_con_personaje`); el resto
        # conserva el producto neutral que el optimizador ya habia elegido.
        llevan = _lineas_con_swap(kit.lineas, swaps)

        def producto_de(indice: int, linea: Any, llevan: set[int] = llevan) -> Any:
            if indice not in llevan:
                return linea.elegido
            # Una linea que los filtros dejaron sin producto sigue sin producto:
            # el swap no la puede resucitar con otro que el acudiente no vio.
            if filtros.activos and linea.elegido is None:
                return linea.elegido
            candidato = _candidato_de_swap(swaps[linea.concepto_codigo])
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
                objetivos=_objetivos(lineas, total),
            )
        )

    # El Fan cambio de precio: la marca del recomendado y el veredicto de
    # presupuesto se recalculan sobre los tres kits ya con el precio verdadero.
    return recomendar(recomputados, preferencias)


def _lineas_con_swap(lineas: Any, swaps: dict[str, dict[str, Any]]) -> set[int]:
    """Los indices de las lineas del kit que reciben el producto de personaje.

    Agrupa las lineas comprables por concepto (solo los que tienen swap) y deja
    que `renglones_con_personaje` decida, concepto por concepto, en cuales cabe.
    """
    grupos: dict[str, list[tuple[int, str, dict[str, Any], str]]] = {}
    for indice, linea in enumerate(lineas):
        if linea.informativa or linea.concepto_codigo not in swaps:
            continue
        grupos.setdefault(linea.concepto_codigo, []).append(
            (indice, linea.hijo, linea.atributos_impuestos, linea.descripcion)
        )
    llevan: set[int] = set()
    for concepto, renglones in grupos.items():
        llevan |= renglones_con_personaje(renglones, swaps[concepto].get("atributos") or {})
    return llevan


def _linea_con_producto(linea: Any, elegido: Any) -> Any:
    """La linea en su forma pre-consolidacion (unidades sueltas) para un elegido.

    Deshace la consolidacion que `armar_los_tres` ya aplico —reponiendo las
    unidades y el subtotal de una sola compra— para que `consolidar` pueda volver
    a decidir sobre el producto (posiblemente nuevo). Una informativa o una linea
    sin producto no se toca; su aritmetica ya es cero.
    """
    if linea.informativa or elegido is None:
        return linea
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
    )
