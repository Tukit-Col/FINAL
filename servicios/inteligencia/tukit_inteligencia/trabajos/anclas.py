from __future__ import annotations

import logging
from typing import Any

from tukit_comun.texto import normalizar_personaje

from ..optimizador import (
    CONCEPTOS_ANCLA,
)
from ..remoto import ClienteCatalogo

logger = logging.getLogger(__name__)


_TOPE_ANCLAS_AVISADAS = 256


_ANCLAS_AVISADAS: set[tuple[str, str]] = set()


async def anclas_por_hijo(
    catalogo: ClienteCatalogo, personajes: dict[str, str]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
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
    if not personaje:
        return {}
    return (await anclas_por_hijo(catalogo, {"_": personaje})).get("_", {})
