"""El adaptador de entrada HTTP de Identidad: parsear, verificar token, traducir.

Un solo router (`identidad`) que `api.py` monta. Parsea la peticion (incluidos
los 422 de forma), resuelve el token, pide el SQL a `repositorios/` y las reglas
puras a `dominio/`, y traduce el resultado a un sobre de respuesta o de error. No
arma SQL ni conoce el motor mas alla de `peticion.app.state` (ADR 0019).
"""

from .identidad import router

__all__ = ["router"]
