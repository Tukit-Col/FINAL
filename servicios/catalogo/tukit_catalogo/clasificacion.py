from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from .embeddings import coseno


def _plano(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


VACIAS = frozenset({"de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "para", "con", "en"})


RUIDO = re.compile(
    r"\b(\d+\s*)?(unidades?|unds?|uds?|paquetes?|bolsas?|cajas?|docenas?|pares?|"
    r"rollos?|tarros?|frascos?|pliegos?|hojas?|juegos?|sets?|metros?|x\d+)\b"
)


FRACCION = re.compile(r"\b\d+\s*/\s*\d+\b")


RANGO_DUREZA = re.compile(r"\b\d?[hb]{1,2}(?:\s*(?:-|,|y|a|al|hasta)\s*\d?[hb]{1,2}\b)+")


PAR_DE_ESCUADRAS = re.compile(
    r"\bescuadras?\b\D*\b(?:30|45|60)\s*(?:°|grados?)?\s*(?:y|,|-|/)?\s*(?:30|45|60)\b\s*(?:°|grados?)?"
)


_PREFIJO_DE_GRUPO = re.compile(r"^(kit|materiales?|para)\b")


_PALABRAS_MAXIMAS_DE_ENCABEZADO = 5


_CLASES_DE_LIBRO = frozenset({"texto", "novela", "lecto", "lectoescritura"})


def consulta_desde_renglon(renglon: str) -> str:
    texto = _plano(renglon)
    grupo, dos_puntos, resto = texto.partition(":")
    if dos_puntos and resto.strip() and _PREFIJO_DE_GRUPO.match(grupo.strip()):
        texto = resto
    texto = re.sub(r"[(),;:.]", " ", texto)
    texto = FRACCION.sub(" ", texto)
    texto = RUIDO.sub(" ", texto)
    texto = re.sub(r"\b\d+\s*(gr?|grs|gramos?|ml|cc|cm|mm|mts?|metros?)\b", " ", texto)
    texto = re.sub(r"^\s*\d+\s+", "", texto)
    texto = re.sub(
        r"^\s*(un|una|unos|unas|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|doce)\s+", "", texto
    )
    palabras = [
        p for p in texto.split() if len(p) > 1 and p not in ("de", "del", "la", "el", "y", "o", "para", "con")
    ]
    return " ".join(palabras[:6])


def _parecido(a: str, b: str) -> float:
    pa = _significativas(a)
    pb = _significativas(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


def _significativas(texto: str) -> set[str]:
    return {singular(p) for p in _plano(texto).split() if p not in VACIAS and not p.isdigit() and len(p) > 1}


def cabeza(renglon: str) -> str:
    palabras = [p for p in consulta_desde_renglon(renglon).split() if not p.isdigit()]
    return palabras[0] if palabras else ""


def singular(palabra: str) -> str:
    if len(palabra) > 4 and palabra.endswith("ces"):
        return palabra[:-3] + "z"
    if len(palabra) > 4 and palabra.endswith("es"):
        return palabra[:-2]
    if palabra.endswith("es"):
        return palabra
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def _sin_encabezado_de_grupo(renglon: str, conceptos: list[dict[str, Any]]) -> str:
    grupo, dos_puntos, resto = renglon.partition(":")
    if not dos_puntos or not resto.strip():
        return renglon
    if _PREFIJO_DE_GRUPO.match(grupo.strip()):
        return resto
    if not grupo.split() or len(grupo.split()) > _PALABRAS_MAXIMAS_DE_ENCABEZADO or "." in grupo:
        return renglon
    nucleo = singular(cabeza(grupo))
    if not nucleo or nucleo in _CLASES_DE_LIBRO:
        return renglon
    if nucleo == "editorial" and "serie" in resto.split():
        return renglon
    for concepto in conceptos:
        for candidato in [concepto["nombre"], *(concepto["sinonimos"] or [])]:
            palabras = _plano(candidato).split()
            if palabras and singular(palabras[0]) == nucleo:
                return renglon
    return resto


def _misma_cosa(a: str, b: str) -> bool:
    sa, sb = singular(a), singular(b)
    return sa[:5] == sb[:5] if min(len(sa), len(sb)) >= 5 else sa == sb


_APORTE_COSENO = 0.15


def clasificar(
    renglon: str,
    conceptos: list[dict[str, Any]],
    *,
    embedding_renglon: list[float] | None = None,
) -> tuple[uuid.UUID | None, str, float]:
    mejor_id, mejor_nombre, mejor = None, "", 0.0
    renglon = RANGO_DUREZA.sub(" serie durezas ", _plano(renglon))
    renglon = PAR_DE_ESCUADRAS.sub(" escuadras juego ", renglon)
    renglon = _sin_encabezado_de_grupo(renglon, conceptos)
    nucleo = cabeza(renglon)
    for concepto in conceptos:
        cos = (
            max(0.0, coseno(embedding_renglon, concepto["embedding"]))
            if embedding_renglon is not None and concepto.get("embedding")
            else 0.0
        )
        for candidato in [concepto["nombre"], *(concepto["sinonimos"] or [])]:
            palabras_candidato = _plano(candidato).split()
            en_la_cabeza = bool(nucleo) and any(_misma_cosa(nucleo, w) for w in palabras_candidato[:1])
            nombra_la_cabeza = bool(nucleo) and any(_misma_cosa(nucleo, w) for w in palabras_candidato)
            if en_la_cabeza:
                puntaje = min(1.0, 0.6 + 0.4 * _parecido(renglon, candidato) + _APORTE_COSENO * cos)
            elif nombra_la_cabeza:
                puntaje = min(1.0, _parecido(renglon, candidato) + _APORTE_COSENO * cos)
            else:
                puntaje = 0.0
            if puntaje > mejor:
                mejor_id, mejor_nombre, mejor = concepto["id"], concepto["nombre"], puntaje
    return mejor_id, mejor_nombre, mejor
