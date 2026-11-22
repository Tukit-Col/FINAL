"""De un PDF a renglones, sin recortar en silencio.

Decisiones:
- La percepcion no interpreta la lista: le pide a un modelo que lea cada pagina como pagina, porque
  aplanar el PDF a texto parte las filas de las tablas.
- Decide, y no delega, cuando el archivo no es la lista de un grado: un kit con los utiles de otro
  grado es peor que no tener kit. La senal es cuantos grados distintos trae, no cuantas paginas.
- El numero de paginas es solo una guarda contra archivos abusivos y, si salta, se rechaza el
  archivo entero: nunca se leen las primeras y se devuelve el resto como si fuera la lista completa.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

TOPE_PAGINAS = 40

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

    descripcion: str
    cantidad: int | None = None
    confianza: float | None = None


class PaginaLeida(BaseModel):

    grados: list[str] = Field(default_factory=list)
    completa: bool = True
    items: list[ItemExtraido] = Field(default_factory=list)


class PercepcionFallida(Exception):
    pass


LeerPagina = Callable[[bytes, int], PaginaLeida]
Renderizar = Callable[[bytes], list[bytes]]


@dataclass(frozen=True)
class Percepcion:

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
    plano = _sin_tildes(texto)
    plano = plano.replace("°", " ").replace("º", " ")
    plano = re.sub(r"[^a-z0-9 ]", " ", plano)
    plano = re.sub(r"\s+", " ", plano).strip()
    plano = re.sub(r"\bgrado\b", "", plano).strip()
    ano = re.fullmatch(
        r"([1-5]|primer|primero|segundo|tercer|tercero|cuarto|quinto)\s*(?:er|ro|do|to|o)?\s*ano", plano
    )
    if ano:
        return _BACHILLERATO_POR_ANO[_ORDINAL_ANO.get(ano.group(1)) or int(ano.group(1))]
    plano = re.sub(r"\b(\d{1,2})\s*(?:er|ro|do|to|vo|no|mo|o)\b", r"\1", plano)
    if plano in _GRADO:
        return _GRADO[plano]
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
    if not contenido:
        return Percepcion(aceptada=False, error="archivo_vacio", mensaje="El archivo llego vacio.")

    try:
        paginas = list(renderizar(contenido))
    except Exception as exc:
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
