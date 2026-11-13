"""Normalizacion de texto que varios servicios tienen que hacer igual.

`normalizar_personaje` es la clave con que se compara un personaje: la usan el
filtro del Catalogo (`_normalizar_personaje` en Python; `_normalizado_sql` repite
las mismas reglas en SQL) y la ruta del Fan en Inteligencia (cache de anclas y
`anclar_personaje`). Si cambia una regla aqui, cambia para los dos.
"""

from __future__ import annotations

import re
import unicodedata

_RUIDO = re.compile(r"[\s\-_]+")


def normalizar_personaje(texto: str) -> str:
    """Sin tildes, mayusculas, guiones, espacios ni guiones bajos: "Spider-Man" == "spiderman"."""
    base = unicodedata.normalize("NFD", texto)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return _RUIDO.sub("", base.lower())


__all__ = ["normalizar_personaje"]
