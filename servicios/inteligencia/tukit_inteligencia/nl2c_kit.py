from __future__ import annotations

import asyncio
import re
import time
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
    return sanitizar(descripcion, limite=MAX_CARACTERES_DESCRIPCION, del_padre=False).texto


def pesos_fmt(valor: int | None) -> str:
    return "sin precio" if valor is None else f"${int(valor):,}".replace(",", ".")


@dataclass
class ContextoKit:

    texto: str
    lineas: dict[str, dict[str, Any]]
    alternativas: dict[str, list[dict[str, Any]]]
    consolidados: set[str]
    perfil: str
    anterior: dict[str, str] | None = None


def contexto_del_kit(kit: dict[str, Any], anterior: Any = None) -> ContextoKit:
    lineas: dict[str, dict[str, Any]] = {}
    alternativas: dict[str, list[dict[str, Any]]] = {}
    filas: list[str] = []
    consolidados = {str(c.get("sku")) for c in kit.get("consolidaciones") or []}
    n = 0
    for linea in kit.get("lineas") or []:
        actual = linea.get("producto_elegido")
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
    previo = nl2c_lote.validar_anterior(anterior, lineas)
    memoria = f"Pedido anterior del padre: {previo['accion']} en {previo['categoria']}\n" if previo else ""
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
    rechazadas: list[str] = field(default_factory=list)
    explicacion: dict[str, Any] | None = None
    sin_accion: str | None = None
    ayuda: bool = False
    mensaje: str | None = None
    lote: dict[str, Any] | None = None
    lote_props: list[dict[str, Any]] = field(default_factory=list)
    resumen: dict[str, Any] | None = None
    pendientes_variar: list[tuple[str, tuple[str, str]]] = field(default_factory=list)
    pendientes_lote: list[str] = field(default_factory=list)
    sueltas: int = 0


def explicar_kit(kit: dict[str, Any]) -> dict[str, Any]:
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
        else:
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
                        "aplicable": True,
                    },
                }
            )
    if pedido_lote is not None:
        _resolver_lote(pedido_lote, ctx, res, trabajo_id)
    return res


def _resolver_lote(args: dict[str, Any], ctx: ContextoKit, res: ResultadoPropuestas, trabajo_id: str) -> None:
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
        res.mensaje = "¿En qué útil lo quieres? Por ejemplo «más barato en cuadernos»."
        return
    res.lote = {"accion": accion, "categoria": cat.etiqueta, "renglones": len(cat.refs)}
    ya = {p["props"]["item_id"] for p in res.propuestas}
    cupo = MAX_PROPUESTAS_LOTE - len(res.propuestas)
    donde = _donde(cat.etiqueta)
    if accion == "variar":
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
    res.pendientes_lote = [
        ref
        for ref in cat.refs
        if ctx.lineas[ref]["item_id"] not in ya
        and str(ctx.lineas[ref]["producto_elegido"].get("sku")) not in ctx.consolidados
    ]
    if not res.pendientes_lote:
        _cerrar_lote(res, donde)


def _cerrar_lote(res: ResultadoPropuestas, donde: str) -> None:
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
    listos = res.lote.get("ya_en_lo_mejor", 0)
    if listos and accion in ("mas_barato", "mejor_calidad"):
        lo = "lo más barato" if accion == "mas_barato" else "lo mejor"
        texto += f" {listos} ya están en {lo} que hay."
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


def _traedor_de_opciones(
    ctx: ContextoKit, opciones_de: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]] | None
) -> Callable[[str], Awaitable[list[dict[str, Any]]]]:
    semaforo = asyncio.Semaphore(4)

    async def traer(ref: str) -> list[dict[str, Any]]:
        linea = ctx.lineas[ref]
        propias = [a for a in linea.get("alternativas") or [] if a.get("sku")]
        if opciones_de is None:
            return nl2c_lote.opciones_desde_alternativas(linea, propias)
        async with semaforo:
            try:
                encontradas = await opciones_de(linea)
            except Exception:
                encontradas = []
        return encontradas or nl2c_lote.opciones_desde_alternativas(linea, propias)

    return traer


async def completar_lote(
    res: ResultadoPropuestas,
    ctx: ContextoKit,
    trabajo_id: str,
    opciones_de: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]] | None,
) -> None:
    if not res.pendientes_lote or res.lote is None:
        return
    accion = res.lote["accion"]
    regla = (
        nl2c_lote.alternativa_mas_barata if accion == "mas_barato" else nl2c_lote.alternativa_de_mejor_calidad
    )
    traer = _traedor_de_opciones(ctx, opciones_de)
    todas = await asyncio.gather(*(traer(ref) for ref in res.pendientes_lote))
    ya_en_lo_mejor = 0
    for ref, opciones in zip(res.pendientes_lote, todas, strict=True):
        linea = ctx.lineas[ref]
        actual = linea["producto_elegido"]
        alts = [
            {**o, "precio_cop": o.get("precio")}
            for o in opciones
            if o.get("sku") and o.get("sku") != actual.get("sku") and o.get("precio") is not None
        ]
        alt = regla(actual, alts)
        if alt is None:
            ya_en_lo_mejor += 1
            continue
        if len(res.propuestas) >= MAX_PROPUESTAS_LOTE:
            res.lote["fuera_por_tope"] = res.lote.get("fuera_por_tope", 0) + 1
            continue
        unidades = alt.get("unidades_a_comprar")
        subtotal = alt.get("subtotal")
        propuesta = _propuesta_cambio(
            ctx,
            linea,
            alt,
            int(alt["precio"]),
            trabajo_id,
            unidades=int(unidades) if unidades else None,
            subtotal_despues=int(subtotal) if subtotal is not None else None,
        )
        res.propuestas.append(propuesta)
        res.lote_props.append(propuesta)
    res.lote["ya_en_lo_mejor"] = ya_en_lo_mejor
    res.pendientes_lote = []
    _cerrar_lote(res, _donde(res.lote["categoria"]))


async def completar_variar(
    res: ResultadoPropuestas,
    ctx: ContextoKit,
    trabajo_id: str,
    opciones_de: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]] | None,
    personajes_por_hijo: dict[str, list[str]] | None = None,
) -> None:
    if not res.pendientes_variar or res.lote is None:
        return
    traer = _traedor_de_opciones(ctx, opciones_de)

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


VIGENCIA_EMISION_S = 30 * 60
MAX_EMISIONES_POR_PORTADOR = 200
MAX_PORTADORES = 5000
TIPO_DE_COMPONENTE = {"PropuestaCambio": "cambio", "PropuestaDescarte": "descarte"}


@dataclass(frozen=True)
class Emision:
    portador: str | None
    trabajo_id: str | None
    tipos: frozenset[str]
    vence: float


_EMITIDAS: dict[str | None, dict[str, Emision]] = {}


def registrar_emision(
    usuario_id: str | uuid.UUID | None,
    trabajo_id: str | None = None,
    tipos: frozenset[str] | set[str] = frozenset({"restricciones"}),
    *,
    ahora: float | None = None,
) -> str:
    ahora = time.monotonic() if ahora is None else ahora
    portador = huella_usuario(usuario_id)
    propias = _EMITIDAS.pop(portador, None) or {}
    _EMITIDAS[portador] = propias
    for vieja in [k for k, e in propias.items() if e.vence <= ahora]:
        del propias[vieja]
    while len(propias) >= MAX_EMISIONES_POR_PORTADOR:
        propias.pop(next(iter(propias)))
    while len(_EMITIDAS) > MAX_PORTADORES:
        _EMITIDAS.pop(next(iter(_EMITIDAS)))
    propuesta_id = uuid.uuid4().hex
    propias[propuesta_id] = Emision(portador, trabajo_id, frozenset(tipos), ahora + VIGENCIA_EMISION_S)
    return propuesta_id


def emision_de(
    propuesta_id: str, usuario_id: str | uuid.UUID | None = None, *, ahora: float | None = None
) -> Emision | None:
    ahora = time.monotonic() if ahora is None else ahora
    emision = (_EMITIDAS.get(huella_usuario(usuario_id)) or {}).get(propuesta_id)
    return emision if emision is not None and emision.vence > ahora else None
