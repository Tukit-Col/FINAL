"""Provision del esquema de Comercio en su base Postgres.

    $ python -m tukit_comercio

Lee `TUKIT_COMERCIO_DB_URL` (o las piezas comunes `TUKIT_DB_*`) del entorno.
El nombre de la base nunca se escribe aqui: lo deriva `tukit_comun` desde el
nombre del servicio. Ver la funcion de aptitud de la regla 3.
"""

from __future__ import annotations

from tukit_comercio.modelos import Base
from tukit_comun.esquema import materializar

if __name__ == "__main__":
    materializar("comercio", Base)
