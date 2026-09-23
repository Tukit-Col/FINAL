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


class TipoItem(enum.StrEnum):
    """Que clase de renglon de lista escolar representa un concepto.

    Existe porque no todo lo que pide una lista se compra, y forzarle un
    emparejamiento a lo que no se compra no es cobertura sino un defecto. Los
    casos son reales del corpus: "Plan lector virtual RAZ-PLUS ... Link de
    pago: https://pagoslearning.com/" se paga fuera, "Diccionario: el
    disponible en casa" es una instruccion de NO comprar, y "durante el ano se
    incluiran algunos textos" todavia no se puede resolver.

    Solo `UTIL` cuenta para la metrica de "catalogo sin huecos". Un concepto
    `LICENCIA_DIGITAL` sin producto no es un hueco: es un item que por diseno
    no pasa por el carrito, y contarlo como hueco empujaria a taparlo con un
    producto inventado.
    """

    UTIL = "util"
    TEXTO = "texto"
    LIBRO_LIBRE = "libro_libre"
    LICENCIA_DIGITAL = "licencia_digital"
    NO_COMPRAR = "no_comprar"
    DIFERIDO = "diferido"
    UNIFORME = "uniforme"
    OTRO = "otro"


class ModoAdquisicion(enum.StrEnum):
    """Quien puede vender el item, que no es lo mismo que que clase de item es.

    Es ortogonal a `TipoItem` y es la diferencia entre un catalogo que promete
    y uno que cumple: hay textos que Tukit no puede surtir, y no por falta de
    proveedor sino porque el colegio los cerro.

    Los valores salieron de leer los 14 PDF originales, no de imaginar casos.
    Osito de Miel: "el jardin ofrece las instalaciones a las diferentes
    editoriales para que les hagan la venta directa a las familias sabado 24
    enero... las editoriales reciben dinero en efectivo". Modelia: "Sistema
    Flex TAC-Lenguaje 1, edicion exclusiva para la institucion".

    `LIBRO_LIBRE` es el caso opuesto y el mas valioso: "La casa de los
    espiritus. Autor: Isabella Allende. Cualquier editorial". Ahi la
    restriccion se invierte —en vez de una sola edicion valida, sirve
    cualquiera— y es el unico segmento de libros donde Tukit tiene margen para
    optimizar por precio.
    """

    MERCADO_ABIERTO = "mercado_abierto"
    LIBRO_LIBRE = "libro_libre"
    VENTA_DIRECTA_EDITORIAL = "venta_directa_editorial"
    EDICION_EXCLUSIVA = "edicion_exclusiva"
    PLATAFORMA = "plataforma"
    DIFERIDO = "diferido"


# Los modos en los que Tukit puede poner el item en el carrito. Los demas se
# muestran al acudiente como linea informativa con la instruccion del colegio,
# sin precio y fuera del total: prometer lo que no se puede entregar es el modo
# de falla mas caro del negocio, y ocultarlo reproduce el dolor que el acudiente
# vino a evitar, porque descubre el hueco tarde.
MODOS_SURTIBLES: frozenset[ModoAdquisicion] = frozenset(
    {ModoAdquisicion.MERCADO_ABIERTO, ModoAdquisicion.LIBRO_LIBRE}
)


class UnidadBase(enum.StrEnum):
    """En que se cuenta lo que la lista pide, antes de empaquetarlo.

    Es la mitad del arreglo de unidades. La otra mitad es
    `producto_canonico.unidades_por_empaque`, y juntas permiten expresar
    `unidades_a_comprar = techo(cantidad_pedida / unidades_por_empaque)`.

    Sin esta columna, el tamano del empaque y las dimensiones fisicas
    quedaban mezclados en el mismo campo de texto: para "Bloc origami x 50
    unidades (15 x 15 cm)" el catalogo anterior guardaba
    `['15:cm', '15:x', '50:unidades', '50:x']`, donde nada distingue el 50 que
    es empaque del 15 que es un lado. De ahi salia sumar 12 cajas de lapices
    cuando la lista pedia 12 lapices.
    """

    UNIDAD = "unidad"
    HOJA = "hoja"
    PLIEGO = "pliego"
    METRO = "metro"
    GRAMO = "gramo"
    MILILITRO = "mililitro"


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
