"""De un PDF a renglones, sin recortar en silencio.

La percepcion no interpreta la lista: le pide a un modelo que lea cada
pagina como pagina, porque aplanar el PDF a texto parte las filas de las
tablas. Lo que si decide, y no delega, es cuando el archivo no es la lista
de un grado.

Esa decision es de negocio. Un kit armado con los utiles de otro grado es
peor que no tener kit, y el acudiente no tiene como notar el error hasta
que le llega el pedido. La senal es cuantos grados distintos trae el
archivo, no cuantas paginas tiene: hay listas de un grado que ocupan seis
paginas y listas de tres grados que caben en dos.

El numero de paginas solo existe como guarda contra un archivo abusivo, y
cuando salta se rechaza el archivo entero. Nunca se leen las primeras y se
devuelve el resto como si fuera toda la lista: eso ya paso, con un tope de
cinco paginas, y el resultado era un kit incompleto con toda la confianza.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

# Por encima de esto no se llama al modelo. 40 esta justo despues del PDF
# mas largo del corpus (CACS, 39 paginas): ese archivo SI se lee, y si trae
# trece grados se rechaza diciendo cuales, que es una respuesta util. Un
# archivo mas largo que cualquiera que hayamos visto se rechaza antes de
# gastar una llamada, y se dice por que.
TOPE_PAGINAS = 40

# El modelo escribe "4" o "4°" y el colegio escribe "Cuarto". Sin esta
# tabla, un mismo grado contado de dos formas rechazaria una lista valida.
_GRADO = {
    "prejardin": "Prejardin",
    "pre jardin": "Prejardin",
    "pre jard": "Prejardin",
    "jardin": "Jardin",
    "transicion": "Transicion",
    "kinder": "Transicion",
    "primero": "Primero",
    "1": "Primero",
    "segundo": "Segundo",
    "2": "Segundo",
    "tercero": "Tercero",
    "3": "Tercero",
    "cuarto": "Cuarto",
    "4": "Cuarto",
    "quinto": "Quinto",
    "5": "Quinto",
    "sexto": "Sexto",
    "6": "Sexto",
    "septimo": "Septimo",
    "7": "Septimo",
    "octavo": "Octavo",
    "8": "Octavo",
    "noveno": "Noveno",
    "9": "Noveno",
    "decimo": "Decimo",
    "10": "Decimo",
    "once": "Once",
    "undecimo": "Once",
    "11": "Once",
}


_ORDINAL_ANO = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5}
_BACHILLERATO_POR_ANO = {1: "Septimo", 2: "Octavo", 3: "Noveno", 4: "Decimo", 5: "Once"}


class ItemExtraido(BaseModel):
    """Un renglon tal como lo leyo el modelo, antes del parseo."""

    descripcion: str
    cantidad: int | None = None
    confianza: float | None = None


class PaginaLeida(BaseModel):
    """Lo que el modelo devuelve de UNA pagina. Se valida, no se cree."""

    grados: list[str] = Field(default_factory=list)
    completa: bool = True
    items: list[ItemExtraido] = Field(default_factory=list)


class PercepcionFallida(Exception):
    """El modelo no dio una pagina usable. No es un renglon a medias."""


LeerPagina = Callable[[bytes, int], PaginaLeida]
Renderizar = Callable[[bytes], list[bytes]]


@dataclass(frozen=True)
class Percepcion:
    """El resultado de leer un archivo. `aceptada` es la unica puerta.

    Con `aceptada` en falso no se empareja nada: ni un kit parcial ni una
    lista de otro grado. `items` puede venir igual, para poder decirle al
    acudiente que fue lo que se vio, y `error` dice por que no se siguio.
    """

    aceptada: bool
    grados: tuple[str, ...] = ()
    paginas: int = 0
    items: tuple[ItemExtraido, ...] = ()
    error: str | None = None
    mensaje: str = ""
    degradaciones: tuple[str, ...] = field(default_factory=tuple)


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def normalizar_grado(texto: str) -> str:
    """Un grado, en la forma en que se le habla al acudiente.

    Lo que no este en la tabla se conserva, limpio: un grado que el modelo
    invente con un nombre raro tiene que seguir contando como grado distinto,
    porque descartarlo esconderia una lista de varios cursos.
    """
    plano = _sin_tildes(texto)
    plano = plano.replace("°", " ").replace("º", " ")
    plano = re.sub(r"[^a-z0-9 ]", " ", plano)
    plano = re.sub(r"\s+", " ", plano).strip()
    plano = re.sub(r"\bgrado\b", "", plano).strip()
    # "1er Año" .. "5to Año": bachillerato en colegios con ese esquema (Madre Matilde).
    # Es otro conteo: "2do año" no es Segundo de primaria sino el segundo de bachillerato.
    ano = re.fullmatch(
        r"([1-5]|primer|primero|segundo|tercer|tercero|cuarto|quinto)\s*(?:er|ro|do|to|o)?\s*ano", plano
    )
    if ano:
        return _BACHILLERATO_POR_ANO[_ORDINAL_ANO.get(ano.group(1)) or int(ano.group(1))]
    # "1er", "2do", "3ro", "4to": el ordinal abreviado es el numero.
    plano = re.sub(r"\b(\d{1,2})\s*(?:er|ro|do|to|vo|no|mo|o)\b", r"\1", plano)
    if plano in _GRADO:
        return _GRADO[plano]
    # "4 de primaria" y "cuarto de primaria" son el mismo curso.
    primera = plano.split(" ", 1)[0] if plano else ""
    if primera in _GRADO:
        return _GRADO[primera]
    return plano.title() if plano else ""


def grados_distintos(nombres: list[str]) -> tuple[str, ...]:
    vistos: list[str] = []
    for nombre in nombres:
        canon = normalizar_grado(nombre)
        if canon and canon not in vistos:
            vistos.append(canon)
    return tuple(vistos)


def percibir(contenido: bytes, *, renderizar: Renderizar, leer: LeerPagina) -> Percepcion:
    """Lee todas las paginas o no lee ninguna a medias.

    `renderizar` y `leer` llegan de afuera para que esto se pueda probar sin
    un PDF y sin un modelo. El que llama pone el render real y el adaptador
    de Gemini; esta funcion solo impone las dos reglas que no se negocian.
    """
    if not contenido:
        return Percepcion(aceptada=False, error="archivo_vacio", mensaje="El archivo llego vacio.")

    try:
        paginas = list(renderizar(contenido))
    except Exception as exc:  # el render es un puerto: su fallo no es un kit
        return Percepcion(
            aceptada=False,
            error="pdf_ilegible",
            mensaje=f"No pude leer el archivo como lista: {exc}",
        )

    if len(paginas) > TOPE_PAGINAS:
        return Percepcion(
            aceptada=False,
            paginas=len(paginas),
            error="archivo_demasiado_largo",
            mensaje=(
                f"Este archivo tiene {len(paginas)} paginas. Sube solo las paginas del grado de tu hijo."
            ),
        )

    if not paginas:
        return Percepcion(
            aceptada=False,
            error="pdf_sin_paginas",
            mensaje="El archivo no tiene paginas.",
        )

    items: list[ItemExtraido] = []
    crudos: list[str] = []
    degradaciones: list[str] = []

    for numero, png in enumerate(paginas, start=1):
        try:
            pagina = leer(png, numero)
        except PercepcionFallida as exc:
            return Percepcion(
                aceptada=False,
                paginas=len(paginas),
                items=tuple(items),
                error="percepcion_fallida",
                mensaje=f"No pude leer la pagina {numero}: {exc}",
                degradaciones=("gemini",),
            )
        if not pagina.completa:
            degradaciones.append(f"pagina_{numero}_incompleta")
        crudos.extend(pagina.grados)
        items.extend(item for item in pagina.items if item.descripcion.strip())

    grados = grados_distintos(crudos)
    if len(grados) > 1:
        lista = ", ".join(grados)
        return Percepcion(
            aceptada=False,
            grados=grados,
            paginas=len(paginas),
            items=tuple(items),
            error="lista_de_varios_grados",
            mensaje=(
                f"Este archivo tiene la lista de {len(grados)} grados ({lista}). "
                "Sube solo las paginas del grado de tu hijo."
            ),
        )

    if degradaciones:
        return Percepcion(
            aceptada=False,
            grados=grados,
            paginas=len(paginas),
            items=tuple(items),
            error="pagina_incompleta",
            mensaje=(
                "Una pagina no se leyo entera. No armo el kit con lo que alcance a ver: "
                "una lista a medias se parece demasiado a una lista completa."
            ),
            degradaciones=tuple(degradaciones),
        )

    return Percepcion(
        aceptada=True,
        grados=grados,
        paginas=len(paginas),
        items=tuple(items),
    )
