"""Los adaptadores de entrada HTTP de Catalogo (ADR 0019).

`routers/catalogo.py` es la lectura publica y la escritura de un producto;
`admin_http` (aun en su sitio) es la revision de listas por `/v1/admin`. Cada uno
expone un `APIRouter` que `api.py` monta sobre la misma app y el mismo motor.
"""

from __future__ import annotations

from .catalogo import router as router_catalogo

__all__ = ["router_catalogo"]
