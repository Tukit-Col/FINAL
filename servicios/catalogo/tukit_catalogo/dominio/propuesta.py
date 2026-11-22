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
