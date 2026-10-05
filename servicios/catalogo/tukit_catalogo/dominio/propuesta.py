"""Los builders puros de una propuesta de curaduria (ADR 0019).

Arman el dict que `_encolar` mete en la bandeja de propuestas, sin I/O ni
motor, para que lo compartan las tres superficies: la SPA de revision
(`admin_http`, que encola sin aprobar), el `http.server` de curaduria
(`admin`, que encola y aprueba en el acto) y las CLIs. El id sale de
`_uuid_estable` sobre la llave natural (slug + sku/isbn) para que reencolar el
mismo candidato no lo duplique.

`_uuid_estable` se reusa de `cargador` --es el mismo hash de contenido que usa
la carga-- en vez de duplicarlo aqui.
"""

from __future__ import annotations

import uuid
from typing import Any

from .. import tiendas
from ..cargador import _uuid_estable  # noqa: F401  (reexportado: lo usan admin/admin_http)


def _ean_valido(ean: str | None) -> str | None:
    ean = (ean or "").strip()
    return ean if ean.isdigit() and len(ean) in (8, 12, 13) else None


def construir_propuesta_util(
    concepto_id: uuid.UUID,
    nombre_concepto: str,
    slug: str,
    tienda_id: uuid.UUID,
    oferta: tiendas.Oferta,
    nivel: str,
) -> dict[str, Any]:
    """El dict de propuesta de un util elegido, listo para `_encolar`.

    Funcion pura --sin I/O, sin motor-- para que la comparta el CLI (que encola
    y aprueba en el acto) y la SPA (que solo encola, y una persona decide el
    nivel al aprobar). El id sale de `_uuid_estable("util", slug, sku)` para que
    reencolar el mismo candidato no lo duplique. Precio en CENTAVOS, puntaje 0.6
    porque lo eligio una persona de una lista de candidatos reales.
    """
    return {
        "id": _uuid_estable("util", slug, oferta.sku),
        "concepto_id": concepto_id,
        "concepto_sugerido": None,
        "texto_origen": nombre_concepto,
        "tienda_id": tienda_id,
        "referencia_externa": oferta.sku,
        "url": oferta.url or None,
        "nombre": oferta.nombre[:512],
        "marca": oferta.marca,
        "ean": _ean_valido(oferta.ean),
        "imagen_url": oferta.imagen_url,
        "especificaciones": oferta.especificaciones or {},
        "precio_centavos": oferta.precio_cop * 100,
        "disponible": oferta.disponible,
        "nivel_sugerido": nivel,
        "puntaje": 0.6,
        "estado": "pendiente",
        "origen": "manual",
        "version_lista_id": None,
        "item_lista_id": None,
    }


def construir_propuesta_libro(
    concepto_id: uuid.UUID,
    nombre_concepto: str,
    slug: str,
    tienda_id: uuid.UUID,
    isbn: str,
    titulo: str,
    precio_cop: int,
    nivel: str,
) -> dict[str, Any]:
    """El dict de propuesta de un libro por ISBN, listo para `_encolar`.

    Gemelo puro de `construir_propuesta_util` para libros: el ISBN es la
    referencia (identifica la edicion, no un titulo) y va tambien en `ean` y en
    `especificaciones`. Puntaje 0.9 porque un ISBN es un dato duro, no una
    coincidencia de busqueda. Precio en CENTAVOS. `nombre_concepto` no se usa en
    el dict pero se recibe por simetria con el util y para futuras trazas.
    """
    return {
        "id": _uuid_estable("propuesta", slug, isbn),
        "concepto_id": concepto_id,
        "concepto_sugerido": None,
        "texto_origen": titulo,
        "tienda_id": tienda_id,
        "referencia_externa": isbn,
        "url": None,
        "nombre": titulo[:512],
        "marca": None,
        "ean": isbn,
        "imagen_url": None,
        "especificaciones": {"isbn": isbn},
        "precio_centavos": precio_cop * 100,
        "disponible": True,
        "nivel_sugerido": nivel,
        "puntaje": 0.9,
        "estado": "pendiente",
        "origen": "manual",
        "version_lista_id": None,
        "item_lista_id": None,
    }
