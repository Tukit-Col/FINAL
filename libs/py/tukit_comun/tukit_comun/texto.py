from __future__ import annotations

import re
import unicodedata

_RUIDO = re.compile(r"[\s\-_]+")


def normalizar_personaje(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return _RUIDO.sub("", base.lower())


__all__ = ["normalizar_personaje"]
