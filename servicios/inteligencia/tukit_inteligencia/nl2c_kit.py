"""NL2C sobre el kit: de "mas barato en cuadernos" a propuestas de cambio o descarte.

El modelo ve los renglones con referencias cortas (L1, A1) y devuelve solo
referencias. El servidor las resuelve contra el kit que lee del trabajo del
portador: un id de otro kit, un sku inventado o una referencia que no existe
no tienen a que resolverse y se descartan con un codigo. Los precios, nombres e
imagenes de las tarjetas salen del kit, nunca del modelo.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from tukit_comun.texto import normalizar_personaje

from . import nl2c_lote
from .nl2c import (
    ACCIONES_LOTE,
    CLAVES_PESO,
    HERRAMIENTAS_KIT,
    MAX_CARACTERES_DESCRIPCION,
    MAX_LINEAS_EN_PROMPT,
    MAX_PROPUESTAS,
    MAX_PROPUESTAS_LOTE,
    MOTIVOS_DESCARTE,
    MOTIVOS_SIN_ACCION,
    RestriccionesR,
    huella_usuario,
    sanitizar,
)

_RE_REF_LINEA = re.compile(r"L\d{1,3}")
_RE_REF_ALT = re.compile(r"A[1-3]")
TEXTO_MOTIVO = {
    "ya_lo_tengo": "Ya lo tienes en casa",
    "no_lo_necesito": "No lo necesitas",
    "otro": "Prefieres no comprarlo",
}


def _texto_renglon(descripcion: str) -> str:
    """La descripcion viene de la lista del colegio: dato no confiable, acotado."""
    return sanitizar(descripcion, limite=MAX_CARACTERES_DESCRIPCION).texto


def pesos_fmt(valor: int | None) -> str:
    return "sin precio" if valor is None else f"${int(valor):,}".replace(",", ".")


@dataclass
class ContextoKit:
    """Lo que el modelo ve del kit y la tabla para resolver sus referencias."""

    texto: str
    lineas: dict[str, dict[str, Any]]  # "L3" -> linea del kit
    alternativas: dict[str, list[dict[str, Any]]]  # "L3" -> hasta 3 alternativas
    consolidados: set[str]
    perfil: str
    # El pedido anterior ya validado contra ESTE kit ({"accion", "categoria"}) o None.
    anterior: dict[str, str] | None = None


def contexto_del_kit(kit: dict[str, Any], anterior: Any = None) -> ContextoKit:
    lineas: dict[str, dict[str, Any]] = {}
    alternativas: dict[str, list[dict[str, Any]]] = {}
    filas: list[str] = []
    consolidados = {str(c.get("sku")) for c in kit.get("consolidaciones") or []}
    n = 0
    for linea in kit.get("lineas") or []:
        actual = linea.get("producto_elegido")
        # Lo ya descartado no se le muestra al modelo: no hay nada que cambiar ni quitar.
        if linea.get("informativa") or linea.get("descartado") or not actual:
            continue
        n += 1
        if n > MAX_LINEAS_EN_PROMPT:
            break
        ref = f"L{n}"
        alts = [a for a in (linea.get("alternativas") or []) if a.get("sku") != actual.get("sku")][:3]
        lineas[ref], alternativas[ref] = linea, alts
        partes = [
            f"{ref} | {_texto_renglon(str(linea.get('descripcion') or ''))}",
            f"actual: {_texto_renglon(str(actual.get('marca') or actual.get('nombre') or ''))} "
            f"{pesos_fmt(actual.get('precio'))} ({actual.get('nivel')})",
        ]
        for i, alt in enumerate(alts, start=1):
            partes.append(
                f"A{i}: {_texto_renglon(str(alt.get('nombre') or ''))} "
                f"{pesos_fmt(alt.get('precio_cop'))} ({alt.get('nivel')})"
            )
        filas.append(" | ".join(partes))
    perfil = str(kit.get("perfil") or "")
    # El pedido anterior llega del navegador: solo vale si es una accion de la lista y una
    # categoria que ESTE kit usa. Lo que pasa son dos palabras acotadas, sin texto del padre.
    previo = nl2c_lote.validar_anterior(anterior, lineas)
    memoria = f"Pedido anterior del padre: {previo['accion']} en {previo['categoria']}\n" if previo else ""
    # El perfil va fuera del bloque de datos: explicar_kit lo pide y el modelo no debe adivinarlo.
    texto = (
        f"Perfil del kit: {perfil}\n{memoria}<renglones_del_kit>\n"
        + "\n".join(filas)
        + "\n</renglones_del_kit>"
    )
    return ContextoKit(texto, lineas, alternativas, consolidados, perfil, previo)


def _tarjeta_producto(p: dict[str, Any], *, precio: int | None) -> dict[str, Any]:
    return {
        "sku": p.get("sku"),
        "nombre": _texto_renglon(str(p.get("nombre") or "")),
        "marca": p.get("marca"),
        "nivel": p.get("nivel"),
        "imagen_url": p.get("imagen_url"),
        "precio_unitario": precio,
    }


@dataclass
class ResultadoPropuestas:
    propuestas: list[dict[str, Any]] = field(default_factory=list)
    rechazadas: list[str] = field(default_factory=list)  # codigos, nunca texto del modelo
    explicacion: dict[str, Any] | None = None
    sin_accion: str | None = None
    ayuda: bool = False
    # Texto del servidor para cuando no hay nada que proponer (nunca texto del modelo).
    mensaje: str | None = None
    # Pedido por categoria: lo que se resolvio, sus propuestas y el resumen que ve el padre.
    lote: dict[str, Any] | None = None
    lote_props: list[dict[str, Any]] = field(default_factory=list)
    resumen: dict[str, Any] | None = None
    pendientes_variar: list[tuple[str, tuple[str, str]]] = field(default_factory=list)
    sueltas: int = 0  # propuestas que vienen de llamadas por renglon (tope MAX_PROPUESTAS)


def explicar_kit(kit: dict[str, Any]) -> dict[str, Any]:
    """Resumen de plantilla sobre datos del servidor: el modelo solo pide verlo."""
    con_producto = [
        ln for ln in kit.get("lineas") or [] if ln.get("producto_elegido") and not ln.get("informativa")
    ]
    por_nivel: dict[str, int] = {}
    for ln in con_producto:
        nivel = str(ln["producto_elegido"].get("nivel"))
        por_nivel[nivel] = por_nivel.get(nivel, 0) + 1
    total = kit.get("total")
    if isinstance(total, dict):
        total = total.get("monto")
    return {
        "tipo": "ExplicacionKit",
        "props": {
            "perfil": kit.get("perfil"),
            "renglones": len(con_producto),
            "por_nivel": por_nivel,
            "total_cop": total if isinstance(total, int) else None,
        },
    }


def _propuesta_cambio(
    ctx: ContextoKit,
    linea: dict[str, Any],
    despues: dict[str, Any],
    precio_despues: int,
    trabajo_id: str,
    *,
    unidades: int | None = None,
    subtotal_despues: int | None = None,
) -> dict[str, Any]:
    """La tarjeta de cambio, con todo lo que ve el padre armado desde el kit y el catalogo.

    `delta_cop` es el subtotal nuevo menos el de hoy: con `subtotal_despues` (una opcion del
    carrusel, que ya trae su propio empaque) o, por omision, precio por las mismas unidades.
    """
    actual = linea["producto_elegido"]
    unidades = unidades or int(linea.get("unidades_a_comprar") or 1)
    if subtotal_despues is None:
        delta = (precio_despues - int(actual["precio"])) * unidades
    else:
        delta = subtotal_despues - int(linea.get("subtotal_linea") or 0)
    return {
        "tipo": "PropuestaCambio",
        "props": {
            "trabajo_id": trabajo_id,
            "perfil": ctx.perfil,
            "item_id": linea["item_id"],
            "descripcion": _texto_renglon(str(linea.get("descripcion") or "")),
            "antes": _tarjeta_producto(actual, precio=int(actual["precio"])),
            "despues": _tarjeta_producto(despues, precio=precio_despues),
            "unidades": unidades,
            "delta_cop": delta,
            "aplicable": True,
        },
    }


def _donde(etiqueta: str) -> str:
    return "tu kit" if etiqueta == "kit" else etiqueta


def _plural(n: int, uno: str, varios: str) -> str:
    return uno if n == 1 else varios


def validar_llamadas_kit(
    llamadas: list[dict[str, Any]], ctx: ContextoKit, kit: dict[str, Any], trabajo_id: str
) -> ResultadoPropuestas:
    """Cada llamada del modelo pasa por aqui; lo que no encaja se descarta con un codigo."""
    res = ResultadoPropuestas()
    vistas: set[tuple[str, str]] = set()
    pedido_lote: dict[str, Any] | None = None
    for llamada in llamadas:
        nombre, args = llamada.get("name"), llamada.get("args")
        if nombre not in HERRAMIENTAS_KIT or not isinstance(args, dict):
            res.rechazadas.append("herramienta_no_permitida")
            continue
        if nombre == "sin_accion":
            motivo = args.get("motivo")
            res.sin_accion = motivo if motivo in MOTIVOS_SIN_ACCION else "ambiguo"
            continue
        if nombre == "mostrar_capacidades":
            res.ayuda = True
            continue
        if nombre == "pedir_por_categoria":
            # Un solo pedido por categoria por respuesta: se resuelve al final, con las
            # propuestas sueltas ya contadas, para no repetir renglon ni pasar el tope.
            if pedido_lote is None:
                pedido_lote = args
            else:
                res.rechazadas.append("exceso_o_repetida")
            continue
        if nombre == "explicar_kit":
            if args.get("perfil") == ctx.perfil and res.explicacion is None:
                res.explicacion = explicar_kit(kit)
            else:
                res.rechazadas.append("perfil_ajeno")
            continue
        ref = str(args.get("linea") or "")
        if not _RE_REF_LINEA.fullmatch(ref) or ref not in ctx.lineas:
            res.rechazadas.append("linea_inexistente")
            continue
        if res.sueltas >= MAX_PROPUESTAS or (nombre, ref) in vistas:
            res.rechazadas.append("exceso_o_repetida")
            continue
        vistas.add((nombre, ref))
        linea = ctx.lineas[ref]
        actual = linea["producto_elegido"]
        if nombre == "proponer_cambio":
            if str(actual.get("sku")) in ctx.consolidados:
                res.rechazadas.append("linea_consolidada")
                continue
            ref_alt = str(args.get("alternativa") or "")
            indice = int(ref_alt[1]) - 1 if _RE_REF_ALT.fullmatch(ref_alt) else -1
            alts = ctx.alternativas[ref]
            if not 0 <= indice < len(alts):
                res.rechazadas.append("alternativa_inexistente")
                continue
            alt = alts[indice]
            precio_alt, precio_act = alt.get("precio_cop"), actual.get("precio")
            if precio_alt is None or precio_act is None:
                res.rechazadas.append("sin_precio")
                continue
            res.propuestas.append(_propuesta_cambio(ctx, linea, alt, int(precio_alt), trabajo_id))
            res.sueltas += 1
        else:  # proponer_descarte
            motivo = args.get("motivo")
            if motivo not in MOTIVOS_DESCARTE:
                res.rechazadas.append("motivo_invalido")
                continue
            res.sueltas += 1
            res.propuestas.append(
                {
                    "tipo": "PropuestaDescarte",
                    "props": {
                        "trabajo_id": trabajo_id,
                        "perfil": ctx.perfil,
                        "item_id": linea["item_id"],
                        "descripcion": _texto_renglon(str(linea.get("descripcion") or "")),
                        "motivo": motivo,
                        "motivo_texto": TEXTO_MOTIVO[motivo],
                        "producto": _tarjeta_producto(actual, precio=actual.get("precio")),
                        "ahorro_cop": int(linea.get("subtotal_linea") or 0),
                        # El modelo solo propone: el descarte lo aplica el padre al confirmar,
                        # por el endpoint de S3 (`PUT .../descarte`) con su propia sesion.
                        "aplicable": True,
                    },
                }
            )
    if pedido_lote is not None:
        _resolver_lote(pedido_lote, ctx, res, trabajo_id)
    return res


# --- Pedidos por categoria (deterministas) --------------------------------------------------
def _resolver_lote(args: dict[str, Any], ctx: ContextoKit, res: ResultadoPropuestas, trabajo_id: str) -> None:
    """Un pedido sobre un tipo de util completo, expandido con reglas sobre el kit.

    El modelo aporto como mucho dos cosas: la accion (de una lista) y una palabra de
    categoria. Los renglones, los skus y los precios salen del kit: lo que el modelo diga
    de mas no tiene por donde entrar.
    """
    accion = args.get("accion")
    if accion not in ACCIONES_LOTE:
        res.rechazadas.append("accion_invalida")
        return
    crudo = args.get("categoria")
    categoria = crudo if isinstance(crudo, str) and crudo.strip() else None
    previo = ctx.anterior
    if accion == "igual_que_antes":
        if previo is None:
            res.mensaje = (
                "¿Qué quieres que haga ahí? Puedo dejarlo más barato, de mejor calidad o con más variedad."
            )
            return
        accion = previo["accion"]
        if categoria is None and previo["categoria"] != "kit":
            categoria = previo["categoria"]
    if categoria is not None:
        cat = nl2c_lote.resolver_categoria(categoria, ctx.lineas)
        if cat is None:
            res.rechazadas.append("categoria_inexistente")
            res.mensaje = (
                "No encontré ese tipo de útil en tu kit. Dime cuál quieres, por ejemplo «cuadernos»."
            )
            return
    elif accion == "variar":
        cat = nl2c_lote.todo_el_kit(ctx.lineas)
    else:
        # Cambiar precio o calidad de TODO el kit de una vez no se propone: se pide el tipo de util.
        # Asi un pedido ambiguo (o una inyeccion que diga "todos") no se expande a todo el kit.
        res.mensaje = "¿En qué útil lo quieres? Por ejemplo «más barato en cuadernos»."
        return
    res.lote = {"accion": accion, "categoria": cat.etiqueta, "renglones": len(cat.refs)}
    ya = {p["props"]["item_id"] for p in res.propuestas}
    cupo = MAX_PROPUESTAS_LOTE - len(res.propuestas)
    donde = _donde(cat.etiqueta)
    if accion == "variar":
        # Elegir variantes pide las opciones del carrusel (E/S): lo termina `completar_variar`.
        candidatos = [
            (ref, clave)
            for ref, clave in nl2c_lote.renglones_a_variar(cat.refs, ctx.lineas, ctx.consolidados)
            if ctx.lineas[ref]["item_id"] not in ya
        ]
        res.pendientes_variar = candidatos[: max(cupo, 0)]
        res.lote["repetidos"] = len(candidatos)
        if not candidatos:
            res.mensaje = f"En {donde} no veo productos repetidos. Ya está variado."
        return
    regla = (
        nl2c_lote.alternativa_mas_barata if accion == "mas_barato" else nl2c_lote.alternativa_de_mejor_calidad
    )
    for ref in cat.refs:
        linea = ctx.lineas[ref]
        actual = linea["producto_elegido"]
        if linea["item_id"] in ya or str(actual.get("sku")) in ctx.consolidados:
            continue
        alts = [
            a for a in linea.get("alternativas") or [] if a.get("sku") and a.get("sku") != actual.get("sku")
        ]
        alt = regla(actual, alts)
        if alt is None:
            continue
        if len(res.propuestas) >= MAX_PROPUESTAS_LOTE:
            res.lote["fuera_por_tope"] = res.lote.get("fuera_por_tope", 0) + 1
            continue
        propuesta = _propuesta_cambio(ctx, linea, alt, int(alt["precio_cop"]), trabajo_id)
        res.propuestas.append(propuesta)
        res.lote_props.append(propuesta)
    _cerrar_lote(res, donde)


def _cerrar_lote(res: ResultadoPropuestas, donde: str) -> None:
    """El resumen del lote (texto del servidor) o, si no hubo nada, el mensaje de por que."""
    assert res.lote is not None
    accion, n = res.lote["accion"], len(res.lote_props)
    if n == 0:
        if res.mensaje is None:
            res.mensaje = {
                "mas_barato": f"En {donde} ya tienes lo más barato que encontré.",
                "mejor_calidad": f"En {donde} no encontré una opción de mejor nivel.",
                "variar": f"No encontré otras opciones para variar en {donde}.",
            }[accion]
        return
    delta = sum(int(p["props"]["delta_cop"]) for p in res.lote_props)
    cambios = _plural(n, "cambio", "cambios")
    if accion == "mas_barato":
        texto = f"Encontré {n} {cambios} en {donde}: ahorras {pesos_fmt(-delta)} en total."
    elif accion == "mejor_calidad":
        texto = f"Te propongo {n} {cambios} de mejor calidad en {donde}. "
        texto += f"Costarían {pesos_fmt(delta)} más." if delta > 0 else f"Y ahorras {pesos_fmt(-delta)}."
    else:
        restantes = res.lote.get("repetidos", n) - n
        texto = (
            f"Encontré {n} {_plural(n, 'renglón repetido', 'renglones repetidos')} en {donde} "
            "y te propongo otros distintos."
        )
        if restantes > 0:
            texto += f" Quedaron {restantes} sin cambio."
        if delta:
            texto += f" Diferencia total: {'+' if delta > 0 else '-'}{pesos_fmt(abs(delta))}."
    if res.lote.get("fuera_por_tope"):
        texto += f" Te muestro {n}; pídeme el resto después."
    res.resumen = {
        "tipo": "ResumenLote",
        "props": {
            "accion": accion,
            "categoria": res.lote["categoria"],
            "propuestas": n,
            "delta_total_cop": delta,
            "texto": texto,
        },
    }


async def completar_variar(
    res: ResultadoPropuestas,
    ctx: ContextoKit,
    trabajo_id: str,
    opciones_de: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]] | None,
    personajes_por_hijo: dict[str, list[str]] | None = None,
) -> None:
    """Termina un pedido de variedad: elige, por renglon repetido, otra opcion del carrusel.

    Las opciones salen del mismo calculo que el carrusel de LineaDeKit
    (`trabajos.opciones_de_una_linea`), filtros del trabajo incluidos; si no responde se
    usan las alternativas guardadas en el kit. La eleccion la hacen las reglas de
    `nl2c_lote.elegir_variante`, nunca el modelo.

    `personajes_por_hijo` es `{hijo de la linea: [personajes pedidos]}` (lo que `ver`
    expone): con el, la variedad no trae franquicias que ese hijo no pidio. Sin el, toda
    opcion de personaje queda fuera y solo se proponen neutras.
    """
    if not res.pendientes_variar or res.lote is None:
        return
    semaforo = asyncio.Semaphore(4)

    async def traer(ref: str) -> list[dict[str, Any]]:
        linea = ctx.lineas[ref]
        propias = [a for a in linea.get("alternativas") or [] if a.get("sku")]
        if opciones_de is None:
            return nl2c_lote.opciones_desde_alternativas(linea, propias)
        async with semaforo:
            try:
                encontradas = await opciones_de(linea)
            except Exception:  # catalogo caido o linea sin concepto: se sigue con lo del kit
                encontradas = []
        return encontradas or nl2c_lote.opciones_desde_alternativas(linea, propias)

    todas = await asyncio.gather(*(traer(ref) for ref, _ in res.pendientes_variar))
    usados_skus = {str(ln["producto_elegido"].get("sku")) for ln in ctx.lineas.values()}
    usados_pers = {
        normalizar_personaje(str(ln["producto_elegido"].get("personaje") or "")) for ln in ctx.lineas.values()
    }
    pedidos = {
        str(hijo): frozenset(normalizar_personaje(str(p)) for p in valores if p)
        for hijo, valores in (personajes_por_hijo or {}).items()
    }
    for (ref, clave), opciones in zip(res.pendientes_variar, todas, strict=True):
        linea = ctx.lineas[ref]
        if linea.get("subtotal_linea") is None or linea["producto_elegido"].get("precio") is None:
            continue
        elegida = nl2c_lote.elegir_variante(
            linea,
            clave,
            opciones,
            usados_skus,
            usados_pers,
            personajes_del_hijo=pedidos.get(str(linea.get("hijo") or ""), frozenset()),
        )
        if elegida is None:
            continue
        usados_skus.add(str(elegida["sku"]))
        usados_pers.add(normalizar_personaje(str(elegida.get("personaje") or "")))
        propuesta = _propuesta_cambio(
            ctx,
            linea,
            elegida,
            int(elegida["precio"]),
            trabajo_id,
            unidades=int(elegida.get("unidades_a_comprar") or 1),
            subtotal_despues=int(elegida["subtotal"]),
        )
        res.propuestas.append(propuesta)
        res.lote_props.append(propuesta)
    res.pendientes_variar = []
    _cerrar_lote(res, _donde(res.lote["categoria"]))


def respuesta_ayuda(ctx: ContextoKit) -> dict[str, Any]:
    """Que puede pedir el padre, con ejemplos tocables armados con las palabras de SU kit."""
    cats = nl2c_lote.categorias_del_kit(ctx.lineas)
    ejemplos: list[str] = []
    if cats:
        ejemplos.append(f"Más barato en {cats[0]}")
    if len(cats) > 1:
        ejemplos.append(f"Mejor marca en {cats[1]}")
    ejemplos += ["Más variedad en mi kit", "¿Por qué este kit cuesta eso?"]
    if len(cats) > 2:
        ejemplos.append(f"Quita {cats[2]}")
    return {
        "estado": "ayuda",
        "mensaje": (
            "Te puedo ayudar a ajustar este kit: dejar una categoría más barata, subir la calidad, "
            "variar lo repetido, quitar lo que no necesitas o explicarte el total. "
            "Yo propongo y tú decides cada cambio."
        ),
        "ejemplos": ejemplos,
    }


def texto_resumen_R(r: RestriccionesR) -> str:
    """El resumen que ve el padre, armado por el servidor desde R validada."""
    prm = r.preferencias_PRM
    partes: list[str] = []
    if prm.personajes:
        partes.append("personaje: " + ", ".join(prm.personajes))
    partes.append(
        {"economico": "gastar poco", "punto_medio": "un punto medio", "estirarse": "estirarte por calidad"}[
            prm.estilo_gasto
        ]
    )
    if r.filtros_duros.presupuesto_max_cop:
        partes.append(f"tope de {pesos_fmt(r.filtros_duros.presupuesto_max_cop)} por hijo")
    if r.filtros_duros.marcas_excluidas:
        partes.append("sin " + ", ".join(r.filtros_duros.marcas_excluidas))
    mayor = max(CLAVES_PESO, key=lambda k: getattr(r.pesos_NSGA, k))
    etiqueta = {
        "precio": "el precio",
        "marca_exigida": "la marca del colegio",
        "calidad": "la calidad",
        "personaje": "el personaje",
    }[mayor]
    partes.append(f"lo que mas pesa es {etiqueta}")
    return "Entendimos: " + "; ".join(partes) + "."


# Propuestas emitidas: una aceptacion solo puede citar una que el servidor emitio,
# a nombre del mismo portador.
_EMITIDAS: dict[str, tuple[str | None, str | None]] = {}


def registrar_emision(usuario_id: str | uuid.UUID | None, trabajo_id: str | None = None) -> str:
    if len(_EMITIDAS) >= 5000:
        _EMITIDAS.pop(next(iter(_EMITIDAS)))
    propuesta_id = uuid.uuid4().hex
    _EMITIDAS[propuesta_id] = (huella_usuario(usuario_id), trabajo_id)
    return propuesta_id


def emision_de(propuesta_id: str) -> tuple[str | None, str | None] | None:
    return _EMITIDAS.get(propuesta_id)
