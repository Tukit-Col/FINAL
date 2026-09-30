"""El adaptador de entrada HTTP de Operacion: parsear, llamar al dominio, traducir.

Un solo router (`operacion`) que `api.py` monta. Parsea la peticion (incluidos
los 422 de forma), pide las reglas a `dominio/` y las consultas a
`repositorios/`, y traduce el resultado a un sobre de respuesta o de error. No
calcula negocio ni arma SQL (ADR 0019).
"""

from .operacion import router

__all__ = ["router"]
