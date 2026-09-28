"""Compatibilidad: la revision de listas por HTTP se mudo a `routers/admin.py`.

El modulo vivia aqui como un manejador gordo (HTTP + reglas + SQL). Con ADR
0019 se partio: las rutas y las transacciones en `routers/admin.py`, el SQL en
`repositorios/admin.py`, los guards y shapers puros en `dominio/listas.py`. Este
archivo queda como puente para que `api.py` siga montando `router` desde el
nombre historico y para las pruebas que leen las tablas y el motor por aqui.
"""

from __future__ import annotations

from .repositorios.admin import CONCEPTO, PROPUESTA
from .routers.admin import _motor, router

__all__ = ["CONCEPTO", "PROPUESTA", "_motor", "router"]
