"""Helpers puros del pipeline de resolucion (ADR 0019).

Las decisiones que no tocan la base ni la red: traducir el vocabulario del
catalogo a un `EstadoResolucion` del contrato, normalizar un renglon crudo a una
demanda con lo que la lista ya sabia, y anclar los conceptos del personaje
pedido al tope del kit. `trabajos/` las orquesta dentro de sus transacciones;
aqui son funciones sin efectos, probables con `assert`.

Importan solo de `modelos`, `optimizador` y `parseo` —ninguno arrastra
SQLAlchemy/FastAPI/httpx a nivel de modulo—, asi que `dominio/` queda puro.
"""

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


def personajes_por_hijo(preferencias: dict[str, Any]) -> dict[str, str]:
    """Cada hijo con su primer personaje pedido; los hijos sin personaje se omiten.

    Correspondencia de claves (verificada en el flujo completo, 12-nov):

    - `personaje_por_hijo` viene del paso 3 de /empezar (`FormularioEmpezar.tsx`),
      indexado por la `referencia` de cada hijo del formulario (`hijo-1`,
      `hijo-2`...; `hijoVacio(i)` numera desde 1). Esa MISMA referencia viaja en
      `hijos[].referencia` de `POST /v1/trabajos`, `_listas_de` la copia a la
      entrada (`"hijo": referencia`) y las dos rutas la ponen tal cual en
      `Renglon.hijo` -> `LineaKit.hijo` -> `linea_kit.hijo_referencia`. En la
      ruta principal las claves casan EXACTAS.
    - `nl2c.a_preferencias` escribe `{"hijo-1": [...]}` (el primer hijo del
      formulario), asi que tambien casa.
    - El formulario OMITE a los hijos sin personaje: las preferencias pueden
      ser dispersas (`{"hijo-2": [...]}` sin `hijo-1`).
    - El poller arma el kit de una lista subida con la referencia REAL del hijo
      que la subio: viaja en la importacion (`referencias`), el Catalogo la
      guarda y la reenvia en `lista_verificada`, asi que tambien casa exacta.
      Solo un evento viejo, encolado antes de ese cambio, cae en `"hijo-1"`.
      El canonico usa `"canonico"` (sin preferencias); los tests usan
      `"hijo-0"`, `"ana"`. `clave_de_hijo` solo une por orden cuando no hay
      ambiguedad (ver ahi); si la hay, el hijo queda neutral.
    """
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    return {str(hijo): str(valores[0]) for hijo, valores in por_hijo.items() if valores}


def clave_de_hijo(preferencias: dict[str, Any], linea_hijo: str, hijos_del_kit: list[str]) -> str | None:
    """La clave de `personaje_por_hijo` que corresponde a `linea_hijo`, o None (neutral).

    1. Exacta si existe (el caso del formulario y de nl2c).
    2. Si ninguna clave casa con ningun hijo del kit, se unen por posicion SOLO
       cuando hay tantas claves como hijos distintos en el kit y son dos o mas:
       entonces cada hijo declaro su personaje y el orden es lo unico que los
       distingue. Con un solo hijo y una sola clave ajena (un evento viejo del
       poller, que caia en `"hijo-1"` aunque fuera otro hijo) no
       hay forma de saber si esa clave es de este hijo o de un hermano omitido
       por no tener personaje (el formulario omite a esos), asi que queda
       neutral: es peor ponerle a un hijo el personaje de su hermano que no
       ponerle ninguno.
    3. En cualquier otro caso, None.

    Riesgo aceptado del paso 2: con dos o mas hijos y ninguna clave exacta, el
    orden de las claves (orden de `personaje_por_hijo`) se asume igual al de
    aparicion de los hijos en el kit; si no lo es, un hermano puede recibir el
    personaje del otro. Hoy eso solo puede ocurrir en un trabajo armado fuera
    del formulario con varios hijos de referencias propias (el poller y el
    canonico arman un solo hijo, el de la lista/`"canonico"`, y el canonico no trae
    preferencias), asi que el caso no se da en produccion; se acepta antes que
    dejar neutral a hermanos que si declararon su personaje.
    """
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
    """`{hijo del kit: personaje}` ya resuelto con `clave_de_hijo` (omite neutrales)."""
    pedidos = personajes_por_hijo(preferencias)
    distintos = list(dict.fromkeys(hijos_del_kit))
    salida: dict[str, str] = {}
    for hijo in distintos:
        clave = clave_de_hijo(preferencias, hijo, distintos)
        if clave is not None and clave in pedidos:
            salida[hijo] = pedidos[clave]
    return salida


def _personaje_pedido(preferencias: dict[str, Any]) -> str | None:
    """El primer personaje declarado; solo para el reordenamiento de `_anclar_kits`.

    El anclaje reordena el kit completo y `anclar_personaje` recibe un solo
    personaje, asi que se toma el primero. Es una decision documentada: el
    reordenamiento es visual y no cambia que producto se eligio (eso ya lo
    hizo `inyectar_personaje_fan` hijo por hijo). Con dos hermanos de
    personajes distintos, solo las anclas del primero suben al tope.
    """
    return next(iter(personajes_por_hijo(preferencias).values()), None)


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


def _variantes(swap: Any) -> list[dict[str, Any]]:
    """Las variantes de un ancla: lista (forma actual) o un solo producto (forma vieja)."""
    if not swap:
        return []
    return list(swap) if isinstance(swap, (list, tuple)) else [swap]


def inyectar_personaje_fan(
    kits: list[Any], swaps_por_hijo: dict[str, dict[str, Any]], preferencias: dict[str, Any]
) -> list[Any]:
    """Mete el producto de personaje en las anclas del kit Fan y rehace sus numeros.

    En las rutas verificada/preview el catalogo entrega `/resueltos` con una
    opcion por nivel y SIN la variante de personaje (es una via aparte, curada);
    por eso el optimizador nunca ve un candidato de personaje que elegir y
    `anclar_personaje` no encuentra nada que subir. Aca se cierra ese hueco: para
    cada hijo y cada concepto ancla que el catalogo si surte con el personaje
    de ESE hijo (`swaps_por_hijo[hijo][concepto]`, una lista de variantes), se
    reemplaza el `elegido`
    de sus lineas del kit Fan por ese producto, con la misma aritmetica del
    armado (techo(pedida/empaque)). Un hijo sin entrada queda neutral; el caso
    de un solo hijo es `{hijo: swaps}`.

    Como el swap cambia el precio del Fan DESPUES de que `armar_los_tres` calculo
    su `total_cop`, sus `objetivos` (incluido `costo`) y el veredicto de
    presupuesto de `recomendar`, hay que rehacer los tres o el kit mostraria un
    total nuevo con objetivos y "cabe en tu presupuesto" viejos —una mentira en
    una pantalla de plata—. Se recomputan `total_cop`/`objetivos` del Fan y se
    re-corre `recomendar` sobre los tres para que la marca y el veredicto de
    presupuesto reflejen los precios verdaderos. Solo toca el Fan; sin swaps
    devuelve los kits intactos (la ruta sin personaje queda byte a byte igual).
    """
    if not any(swaps_por_hijo.values()):
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
        # producto de personaje hubiera sido candidato. Cada hermano recibe el
        # producto de SU personaje: si comparten personaje el sku coincide y el
        # grupo vuelve a unirse (una sola compra); si no, son skus distintos y
        # `consolidar` nunca los junta.
        #
        # El producto de personaje NO va en todos los renglones del concepto: el
        # catalogo entrega uno solo por concepto y personaje, y ponerlo en cada
        # cuaderno de la lista (cuadriculado, cosido, grande, argollado...)
        # repetia el mismo Spiderman de $36.900 cinco veces. `llevan` elige en
        # cuales cabe, una vez por hijo (ver `renglones_con_personaje`); el resto
        # conserva el producto neutral que el optimizador ya habia elegido.
        llevan, sin_encaje = _lineas_con_swap(kit.lineas, swaps_por_hijo)

        def producto_de(indice: int, linea: Any, llevan: dict[int, dict[str, Any]] = llevan) -> Any:
            if indice not in llevan:
                return linea.elegido
            # Una linea que los filtros dejaron sin producto sigue sin producto:
            # el swap no la puede resucitar con otro que el acudiente no vio.
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
                # `personaje_sin_encaje` viaja en el JSON de objetivos (sin
                # migracion); la lectura publica lo saca a `kit.personaje_sin_encaje`.
                objetivos={
                    **_objetivos(lineas, total),
                    **({"personaje_sin_encaje": sin_encaje} if sin_encaje else {}),
                },
            )
        )

    # El Fan cambio de precio: la marca del recomendado y el veredicto de
    # presupuesto se recalculan sobre los tres kits ya con el precio verdadero.
    return recomendar(recomputados, preferencias)


def _lineas_con_swap(
    lineas: Any, swaps_por_hijo: dict[str, dict[str, Any]]
) -> tuple[dict[int, dict[str, Any]], list[dict[str, str]]]:
    """Que lineas del kit reciben producto de personaje, con cual variante, y que no cupo.

    Agrupa las lineas comprables por `(concepto, hijo)` (solo las que tienen
    variantes para ese hijo) y deja que `renglones_con_personaje` elija, entre
    las variantes de ESE hijo, el par (renglon, variante) que mejor encaja.
    Devuelve `{indice_de_linea: variante}` y la lista `personaje_sin_encaje`:
    cada (hijo, concepto) con renglones en la lista y variantes en el catalogo
    pero sin ningun par que encaje, para avisarle al acudiente en vez de callar.
    """
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
    """La linea en su forma pre-consolidacion (unidades sueltas) para un elegido.

    Deshace la consolidacion que `armar_los_tres` ya aplico —reponiendo las
    unidades y el subtotal de una sola compra— para que `consolidar` pueda volver
    a decidir sobre el producto (posiblemente nuevo). Una informativa o una linea
    sin producto no se toca; su aritmetica ya es cero.
    """
    if linea.informativa or elegido is None:
        return linea
    # La nota "Se compra junto con..." la escribio `consolidar` sobre el armado
    # anterior; si el hermano cambio de producto ya no es cierta. `consolidar`
    # la vuelve a escribir si el grupo se rehace.
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
