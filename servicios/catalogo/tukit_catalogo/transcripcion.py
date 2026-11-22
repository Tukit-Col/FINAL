"""Acerca lo que dice la lista a las palabras que el catalogo si conoce.

Osito de Miel imprime `SHSRPIE`, `CARPERTAS` y `TAOLLA`. Gemini las lee
tal cual, y hace bien: una correccion inventada por el modelo no se puede
auditar. La correccion va aqui, despues, y solo cuando hay UNA palabra del
catalogo a un cambio de distancia. Si hay dos candidatas, o ninguna, la
palabra se queda como vino. Preferimos no reconocerla a reconocerla mal.
"""

from __future__ import annotations

import re
import unicodedata

from .clasificacion import singular

_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
_PREFIJO = re.compile(r"^@+\s*")


def _plano(token: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFD", token.lower()) if unicodedata.category(c) != "Mn")
    return sin


def lexico_de(conceptos: list[dict]) -> set[str]:
    """Las palabras con las que el catalogo nombra lo que vende.

    Entran el nombre y los sinonimos. Un sinonimo mal escrito (`carperta`)
    tambien entra: si la lista trae esa misma falta, no hay nada que
    corregir, y el clasificador ya sabe emparejarla.
    """
    palabras: set[str] = set()
    for concepto in conceptos:
        fuentes = [concepto.get("nombre") or "", *(concepto.get("sinonimos") or [])]
        for fuente in fuentes:
            for token in _TOKEN.findall(fuente):
                plano = _plano(token)
                if len(plano) < 4:
                    continue
                palabras.add(plano)
                palabras.add(singular(plano))
    return palabras


def _distancia(a: str, b: str) -> int:
    """Damerau-Levenshtein, cortada en 2.

    La transposicion cuenta como un cambio y no como dos. `taolla` y
    `toalla` son el mismo error de dedo; con Levenshtein puro quedan a
    distancia 2 y la correccion no se atreve.
    """
    if abs(len(a) - len(b)) > 1:
        return 2
    filas, cols = len(a) + 1, len(b) + 1
    d = [[0] * cols for _ in range(filas)]
    for i in range(filas):
        d[i][0] = i
    for j in range(cols):
        d[0][j] = j
    for i in range(1, filas):
        for j in range(1, cols):
            costo = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + costo)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def _unica(token: str, lexico: set[str]) -> str | None:
    """La unica palabra del catalogo a un cambio, o ninguna.

    Dos filtros, los dos salidos de Osito. `taolla` esta a un cambio de
    `toalla` y tambien de `talla`; se queda la de la misma longitud, que es
    la transposicion y no la letra que sobra. `nacho` esta a un cambio de
    `ancho`, pero no comparten ni la primera letra: eso no es un dedo
    corrido, es otra palabra, y se deja quieta.
    """
    if len(token) < 5 or token in lexico or singular(token) in lexico:
        return None
    cercanas = [palabra for palabra in lexico if palabra[0] == token[0] and _distancia(token, palabra) <= 1]
    del_mismo_largo = [palabra for palabra in cercanas if len(palabra) == len(token)]
    if del_mismo_largo:
        cercanas = del_mismo_largo
    else:
        # Una letra de mas o de menos solo se acepta cuando no hay empate
        # con una palabra de la misma longitud. `paquetes` no debe volverse
        # `paquete`: el clasificador ya singulariza, y reescribirlo cambia
        # la cabeza de la frase.
        return None
    if len(cercanas) != 1:
        return None
    return cercanas[0]


def _con_la_caja(original: str, correccion: str) -> str:
    if original.isupper():
        return correccion.upper()
    if original[:1].isupper():
        return correccion.capitalize()
    return correccion


def corregir(texto: str, lexico: set[str]) -> str:
    """Devuelve el renglon con las palabras dudosas sustituidas.

    El `@` del margen de Osito no es una letra: marca el renglon y, si se
    queda pegado, el clasificador busca un concepto que empieza por arroba.
    """
    limpio = _PREFIJO.sub("", texto.strip())

    def cambiar(coincidencia: re.Match[str]) -> str:
        original = coincidencia.group(0)
        plano = _plano(original)
        correccion = _unica(plano, lexico)
        if correccion is None:
            return original
        return _con_la_caja(original, correccion)

    return _TOKEN.sub(cambiar, limpio)
