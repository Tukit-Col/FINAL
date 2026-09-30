"""Adaptador de entrada de Comercio: HTTP, y nada de negocio ni de SQL.

La tercera pata de la ADR 0019 junto a `dominio/` (qué decide) y
`repositorios/` (cómo se guarda): aquí vive el `APIRouter` que parsea la
petición, llama al dominio puro, traduce sus resultados a sobres de error
(`ErrorDominio`) y delega la persistencia al repo atado a la sesión. No calcula
totales ni arma SQL: sólo orquesta. `api.py` queda como el ensamblador
(`crear_app` + `include_router`).
"""

from .comercio import router

__all__ = ["router"]
