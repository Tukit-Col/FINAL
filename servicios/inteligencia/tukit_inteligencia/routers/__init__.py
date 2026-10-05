"""El adaptador de entrada HTTP de Inteligencia (ADR 0019).

Un solo router (`inteligencia`) que `api.py` monta: parsea la peticion, llama al
orquestador `trabajos` y traduce a un sobre HTTP. El wiring (motor, clientes
remotos, puertos de percepcion) se queda en `api.py` y el router lo alcanza por
el modulo `api`, para no duplicar el singleton `app` ni romper el seam que las
pruebas monkeypatchean.
"""

from __future__ import annotations

from .inteligencia import router

__all__ = ["router"]
