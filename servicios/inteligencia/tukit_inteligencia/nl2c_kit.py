"""NL2C sobre el kit: de "mas barato en cuadernos" a propuestas de cambio o descarte.

El modelo ve los renglones con referencias cortas (L1, A1) y devuelve solo
referencias. El servidor las resuelve contra el kit que lee del trabajo del
portador: un id de otro kit, un sku inventado o una referencia que no existe
no tienen a que resolverse y se descartan con un codigo. Los precios, nombres e
imagenes de las tarjetas salen del kit, nunca del modelo.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .nl2c import (
    CLAVES_PESO,
    HERRAMIENTAS_KIT,
    MAX_CARACTERES_DESCRIPCION,
    MAX_LINEAS_EN_PROMPT,
    MAX_PROPUESTAS,
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


def contexto_del_kit(kit: dict[str, Any]) -> ContextoKit:
    lineas: dict[str, dict[str, Any]] = {}
    alternativas: dict[str, list[dict[str, Any]]] = {}
    filas: list[str] = []
    consolidados = {str(c.get("sku")) for c in kit.get("consolidaciones") or []}
    n = 0
    for linea in kit.get("lineas") or []:
        actual = linea.get("producto_elegido")
        if linea.get("informativa") or not actual:
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
    texto = "<renglones_del_kit>\n" + "\n".join(filas) + "\n</renglones_del_kit>"
    return ContextoKit(texto, lineas, alternativas, consolidados, str(kit.get("perfil") or ""))


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


def validar_llamadas_kit(
    llamadas: list[dict[str, Any]], ctx: ContextoKit, kit: dict[str, Any], trabajo_id: str
) -> ResultadoPropuestas:
    """Cada llamada del modelo pasa por aqui; lo que no encaja se descarta con un codigo."""
    res = ResultadoPropuestas()
    vistas: set[tuple[str, str]] = set()
    for llamada in llamadas:
        nombre, args = llamada.get("name"), llamada.get("args")
        if nombre not in HERRAMIENTAS_KIT or not isinstance(args, dict):
            res.rechazadas.append("herramienta_no_permitida")
            continue
        if nombre == "sin_accion":
            motivo = args.get("motivo")
            res.sin_accion = motivo if motivo in MOTIVOS_SIN_ACCION else "ambiguo"
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
        if len(res.propuestas) >= MAX_PROPUESTAS or (nombre, ref) in vistas:
            res.rechazadas.append("exceso_o_repetida")
            continue
        vistas.add((nombre, ref))
        linea = ctx.lineas[ref]
        actual = linea["producto_elegido"]
        unidades = int(linea.get("unidades_a_comprar") or 1)
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
            res.propuestas.append(
                {
                    "tipo": "PropuestaCambio",
                    "props": {
                        "trabajo_id": trabajo_id,
                        "perfil": ctx.perfil,
                        "item_id": linea["item_id"],
                        "descripcion": _texto_renglon(str(linea.get("descripcion") or "")),
                        "antes": _tarjeta_producto(actual, precio=int(precio_act)),
                        "despues": _tarjeta_producto(alt, precio=int(precio_alt)),
                        "unidades": unidades,
                        "delta_cop": (int(precio_alt) - int(precio_act)) * unidades,
                        "aplicable": True,
                    },
                }
            )
        else:  # proponer_descarte
            motivo = args.get("motivo")
            if motivo not in MOTIVOS_DESCARTE:
                res.rechazadas.append("motivo_invalido")
                continue
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
                        # Descartar lo construye S3; hasta que exista su endpoint solo se propone.
                        "aplicable": False,
                    },
                }
            )
    return res


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
