from __future__ import annotations

from typing import Any

from tukit_comun.http import ErrorDominio

_ORDEN_NIVEL = ("economico", "confiable", "premium")

_CAMPOS_EDITABLES = frozenset(
    {
        "nombre",
        "descripcion",
        "marca",
        "nivel",
        "personaje",
        "imagen_url",
        "unidad_base",
        "unidades_por_empaque",
        "atributos",
        "quality_score",
        "es_propio",
    }
)

_UNIDADES_BASE = ("unidad", "hoja", "pliego", "metro", "gramo", "mililitro")

_CAMPOS_QUE_REEMBEBEN = frozenset({"nombre", "atributos"})


def pesos(centavos: int | None) -> int | None:
    return None if centavos is None else int(centavos) // 100


def _sobre(pagina: int, por_pagina: int, total: int, clave: str, filas: list[Any]) -> dict[str, Any]:
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, clave: filas}


def _concepto_publico(fila: Any) -> dict[str, Any]:
    return {
        "codigo": fila.codigo,
        "nombre": fila.nombre_canonico,
        "categoria": fila.categoria,
        "tipo_item": fila.tipo_item,
        "sinonimos": list(fila.sinonimos or ()),
        "admite_personaje": bool(fila.admite_personaje),
        "atributos_discriminantes": list(fila.atributos_discriminantes or ()),
        "atributos_descriptivos": list(fila.atributos_descriptivos or ()),
        "frecuencia_demanda": int(fila.frecuencia_demanda or 0),
    }


def _producto_publico(fila: Any) -> dict[str, Any]:
    return {
        "sku": fila.sku_interno,
        "ean": fila.ean,
        "nombre": fila.nombre,
        "marca": fila.marca,
        "nivel": fila.nivel,
        "personaje": fila.personaje,
        "imagen_url": fila.imagen_url,
        "descripcion": fila.descripcion,
        "es_propio": bool(fila.es_propio),
        "unidad_base": fila.unidad_base,
        "unidades_por_empaque": int(fila.unidades_por_empaque or 1),
        "atributos": dict(fila.atributos or {}),
        "quality_score": float(fila.quality_score),
        "concepto": {"codigo": fila.concepto_codigo, "nombre": fila.concepto_nombre},
        "precio_desde": pesos(getattr(fila, "centavos", None)),
        "tiendas": int(getattr(fila, "tiendas", 0) or 0),
    }


def _oferta_publica(fila: Any) -> dict[str, Any]:
    return {
        "tienda": fila.slug,
        "tienda_nombre": fila.tienda_nombre,
        "tipo_tienda": fila.tipo,
        "url": fila.url,
        "disponible": fila.disponible,
        "precio": pesos(fila.valor_centavos),
        "vigente_desde": fila.vigente_desde.isoformat() if fila.vigente_desde else None,
        "vigente_hasta": fila.vigente_hasta.isoformat() if fila.vigente_hasta else None,
        "visto_en": fila.vigente_desde.isoformat() if fila.vigente_desde else None,
        "fuente_precio": fila.fuente,
        "metodo_vinculacion": fila.metodo_vinculacion,
        "confianza_vinculacion": float(fila.confianza_vinculacion),
    }


def _ordenar_ofertas(ofertas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(ofertas, key=lambda o: (o["precio"] is None, o["precio"] or 0))


def _validar_edicion(cambios: dict[str, Any]) -> None:
    for campo in cambios:
        if campo not in _CAMPOS_EDITABLES:
            raise ErrorDominio(
                "campo_no_editable",
                f"El campo {campo} no se edita por esta ruta.",
                campo=campo,
            )
    if "nivel" in cambios and cambios["nivel"] not in _ORDEN_NIVEL:
        raise ErrorDominio(
            "nivel_invalido", f"El nivel debe ser uno de {', '.join(_ORDEN_NIVEL)}.", campo="nivel"
        )
    if "unidad_base" in cambios and cambios["unidad_base"] not in _UNIDADES_BASE:
        raise ErrorDominio(
            "unidad_base_invalida",
            f"La unidad base debe ser una de {', '.join(_UNIDADES_BASE)}.",
            campo="unidad_base",
        )
    if "unidades_por_empaque" in cambios and int(cambios["unidades_por_empaque"]) < 1:
        raise ErrorDominio(
            "empaque_invalido",
            "Las unidades por empaque tienen que ser al menos 1.",
            campo="unidades_por_empaque",
        )
    if "quality_score" in cambios and not (0 <= float(cambios["quality_score"]) <= 1):
        raise ErrorDominio(
            "quality_score_invalido", "El quality_score va entre 0 y 1.", campo="quality_score"
        )
    if "atributos" in cambios:
        for clave, valor in (cambios["atributos"] or {}).items():
            if valor is not None and not isinstance(valor, (str, int, float)):
                raise ErrorDominio(
                    "atributos_invalido",
                    f"El atributo '{clave}' debe ser un valor simple.",
                    estado=422,
                    campo="atributos",
                )
