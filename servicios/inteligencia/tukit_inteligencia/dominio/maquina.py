"""La maquina de estados del trabajo, expuesta como dominio (ADR 0019).

Es el nombre unico por el que el dominio pregunta "esta transicion es legal".
No define la maquina: la fuente de verdad es `modelos.TRANSICIONES` (la tabla)
y `modelos.trabajo.puede_pasar` (el guard que el repo consulta antes de
escribir un cambio de estado). Aqui solo se reexporta, para que la regla viva en
un solo sitio y no en dos que puedan divergir.

# ponytail: fuente unica de verdad es modelos.TRANSICIONES; este modulo solo la
# reexpone bajo el nombre de dominio. No copiar la tabla ni el guard.
"""

from __future__ import annotations

from ..modelos import TRANSICIONES
from ..modelos.trabajo import puede_pasar

__all__ = ["TRANSICIONES", "puede_pasar"]
