"""Provision del esquema de Catalogo en su base Postgres.

    $ python -m tukit_catalogo

Lee `TUKIT_CATALOGO_DB_URL` (o las piezas comunes `TUKIT_DB_*`) del entorno.
Necesita pgvector habilitado en la base: el tipo Vector(1024) de los embeddings
de producto no materializa sin la extension (la crea el init de Postgres).
"""

from __future__ import annotations

from tukit_comun.esquema import materializar

from tukit_catalogo.modelos import Base

if __name__ == "__main__":
    materializar("catalogo", Base)
