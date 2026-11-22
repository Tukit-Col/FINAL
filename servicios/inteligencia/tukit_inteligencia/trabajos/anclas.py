"""Anclas de personaje por hijo: que concepto del kit lleva producto del personaje pedido."""

from __future__ import annotations

import logging
from typing import Any

from tukit_comun.texto import normalizar_personaje

from ..optimizador import (
    CONCEPTOS_ANCLA,
)
from ..remoto import ClienteCatalogo

logger = logging.getLogger(__name__)


# (personaje, concepto) ya avisados como ancla sin producto (ver `anclas_por_hijo`).
# Con tope: el personaje lo escribe el acudiente, y sin limite cada nombre
# inventado dejaria cuatro entradas vivas por el resto del proceso. Pasado el
# tope se deja de anotar (el aviso puede repetirse; la memoria no crece).
_TOPE_ANCLAS_AVISADAS = 256


_ANCLAS_AVISADAS: set[tuple[str, str]] = set()


async def anclas_por_hijo(
    catalogo: ClienteCatalogo, personajes: dict[str, str]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Las variantes de las cuatro anclas de cada hijo: `{hijo: {concepto: [producto, ...]}}`.

    Cada concepto trae TODAS las variantes que el catalogo surte (hasta 8, en
    orden estable): el armado elige la que encaja con cada renglon
    (`renglones_con_personaje`), y un unico cuaderno multimaterias ya no deja
    al hijo sin personaje si hay otro de una materia.

    `personajes` es `{hijo: personaje}` (ver `personajes_de_los_hijos`); un hijo
    sin personaje no aparece y su kit queda neutral. Se consulta el catalogo una
    sola vez por personaje distinto (dos hermanos con el mismo comparten el MISMO
    producto, que es lo que deja a `consolidar` juntarlos en una compra). Es I/O
    de red: se resuelve FUERA de cualquier transaccion abierta. Un ancla que el
    catalogo no surte no entra (ese concepto queda con su producto neutral) y se
    registra con `logger.warning` (una vez por personaje y concepto por proceso):
    un Fan sin cuaderno de personaje no debe pasar callado.
    """
    por_personaje: dict[str, dict[str, list[dict[str, Any]]]] = {}
    salida: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for hijo, personaje in personajes.items():
        if not personaje:
            continue
        clave = normalizar_personaje(personaje)
        if clave not in por_personaje:
            swaps: dict[str, list[dict[str, Any]]] = {}
            for concepto in CONCEPTOS_ANCLA:
                productos = await catalogo.productos_de_personaje(concepto, personaje)
                if productos:
                    swaps[concepto] = productos
                elif (clave, concepto) not in _ANCLAS_AVISADAS:
                    # Una vez por (personaje, concepto) por proceso: la vista
                    # `parent_apply` pasa por aqui en cada lectura.
                    if len(_ANCLAS_AVISADAS) < _TOPE_ANCLAS_AVISADAS:
                        _ANCLAS_AVISADAS.add((clave, concepto))
                    logger.warning(
                        "ancla sin producto de personaje: personaje=%s concepto=%s", personaje, concepto
                    )
            por_personaje[clave] = swaps
        if por_personaje[clave]:
            salida[hijo] = por_personaje[clave]
    return salida


async def _anclas_de_personaje(
    catalogo: ClienteCatalogo, personaje: str | None
) -> dict[str, list[dict[str, Any]]]:
    """Las anclas de UN personaje, indexadas por concepto (ruta del kit aplicado).

    `aplicar_canonico` y la vista `parent_apply` son de un solo hijo y pintan
    las lineas del canonico (`hijo_referencia = "canonico"`), asi que usan la
    forma plana; pasa por `anclas_por_hijo` para compartir cache y avisos.
    """
    if not personaje:
        return {}
    return (await anclas_por_hijo(catalogo, {"_": personaje})).get("_", {})
