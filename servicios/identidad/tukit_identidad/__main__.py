"""Provision del esquema de Identidad en su base Postgres.

    $ python -m tukit_identidad

Lee `TUKIT_IDENTIDAD_DB_URL` (o las piezas comunes `TUKIT_DB_*`) del entorno.
El nombre de la base nunca se escribe aqui: lo deriva `tukit_comun` desde el
nombre del servicio. Ver la funcion de aptitud de la regla 3.
"""

from __future__ import annotations

from tukit_comun.esquema import materializar
from tukit_identidad.modelos import Base

if __name__ == "__main__":
    materializar("identidad", Base)
