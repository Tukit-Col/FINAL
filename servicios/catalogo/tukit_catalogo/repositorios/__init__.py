"""Los adaptadores de salida a la base de Catalogo: aqui vive el SQL (ADR 0019).

`RepoCatalogo` es la lectura publica (conceptos, productos, ofertas, listas) y la
escritura de un producto por su sku. Se construye atado a una conexion, dentro
del `async with motor.sesion()` de quien lo use; no abre ni cierra la sesion.
"""

from __future__ import annotations

from .catalogo import RepoCatalogo

__all__ = ["RepoCatalogo"]
