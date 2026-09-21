"""Base declarativa y tipos portables del servicio de Catalogo."""

from __future__ import annotations

import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Tipos que en Postgres son nativos y en SQLite degradan, para poder probar el
# esquema sin levantar una base. El vector es la excepcion interesante: en
# SQLite queda como JSON y la busqueda semantica no funciona, lo cual esta
# bien porque esa se prueba contra Postgres con pgvector.
Texto = JSON().with_variant(JSONB(), "postgresql")
ListaTexto = JSON().with_variant(ARRAY(String), "postgresql")
Embedding = JSON().with_variant(Vector(1024), "postgresql")

DIMENSION_EMBEDDING = 1024


class Nivel(enum.StrEnum):
    """Nivel de calidad de marca del producto.

    Es la etiqueta que alimenta el armado de kits multiperfil aguas abajo: un
    kit economico se compone de productos `ECONOMICO`, y asi. El personaje NO
    es un nivel sino una columna aparte, porque un producto con personaje
    tambien tiene nivel de marca.
    """

    ECONOMICO = "economico"
    CONFIABLE = "confiable"
    PREMIUM = "premium"


# Puntuacion de calidad derivada del nivel. Se materializa en columna en vez de
# calcularse al vuelo porque el reordenamiento la lee en el camino caliente.
CALIDAD_POR_NIVEL: dict[Nivel, float] = {
    Nivel.ECONOMICO: 0.40,
    Nivel.CONFIABLE: 0.70,
    Nivel.PREMIUM: 0.95,
}


class MetodoVinculacion(enum.StrEnum):
    """Como se vinculo una oferta de tienda con un producto canonico.

    `ATRIBUTOS` no es un caso degradado sino el camino normal de todo el canal
    mayorista: el perfilado midio EAN valido en 61,57 % de una tienda, 0,18 %
    de otra y 0,00 % del mayorista. Vincular por EAN simplemente no esta
    disponible donde mas se necesita.
    """

    EAN = "ean"
    ATRIBUTOS = "atributos"
    MANUAL = "manual"


# Por debajo de esta confianza, la vinculacion por atributos va a cola de
# revision manual en vez de darse por buena.
UMBRAL_REVISION_MANUAL = 0.800


class FuentePrecio(enum.StrEnum):
    SCRAPER = "scraper"
    MANUAL = "manual"
    REFERENCIA = "referencia"
