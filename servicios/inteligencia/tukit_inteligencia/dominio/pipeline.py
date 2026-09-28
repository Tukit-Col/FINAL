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

from typing import Any

from ..modelos import EstadoResolucion
from ..optimizador import Candidato, anclar_personaje
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
