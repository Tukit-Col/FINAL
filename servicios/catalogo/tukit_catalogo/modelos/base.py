from __future__ import annotations

import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


Texto = JSON().with_variant(JSONB(), "postgresql")
ListaTexto = JSON().with_variant(ARRAY(String), "postgresql")
Embedding = JSON().with_variant(Vector(1024), "postgresql")

DIMENSION_EMBEDDING = 1024


class Nivel(enum.StrEnum):
    ECONOMICO = "economico"
    CONFIABLE = "confiable"
    PREMIUM = "premium"


CALIDAD_POR_NIVEL: dict[Nivel, float] = {
    Nivel.ECONOMICO: 0.40,
    Nivel.CONFIABLE: 0.70,
    Nivel.PREMIUM: 0.95,
}


class TipoItem(enum.StrEnum):
    UTIL = "util"
    TEXTO = "texto"
    LIBRO_LIBRE = "libro_libre"
    LICENCIA_DIGITAL = "licencia_digital"
    NO_COMPRAR = "no_comprar"
    DIFERIDO = "diferido"
    UNIFORME = "uniforme"
    OTRO = "otro"


class ModoAdquisicion(enum.StrEnum):
    MERCADO_ABIERTO = "mercado_abierto"
    LIBRO_LIBRE = "libro_libre"
    VENTA_DIRECTA_EDITORIAL = "venta_directa_editorial"
    EDICION_EXCLUSIVA = "edicion_exclusiva"
    PLATAFORMA = "plataforma"
    DIFERIDO = "diferido"


MODOS_SURTIBLES: frozenset[ModoAdquisicion] = frozenset(
    {ModoAdquisicion.MERCADO_ABIERTO, ModoAdquisicion.LIBRO_LIBRE}
)


class UnidadBase(enum.StrEnum):
    UNIDAD = "unidad"
    HOJA = "hoja"
    PLIEGO = "pliego"
    METRO = "metro"
    GRAMO = "gramo"
    MILILITRO = "mililitro"


class MetodoVinculacion(enum.StrEnum):
    EAN = "ean"
    ATRIBUTOS = "atributos"
    MANUAL = "manual"


UMBRAL_REVISION_MANUAL = 0.800


class FuentePrecio(enum.StrEnum):
    SCRAPER = "scraper"
    MANUAL = "manual"
    REFERENCIA = "referencia"
