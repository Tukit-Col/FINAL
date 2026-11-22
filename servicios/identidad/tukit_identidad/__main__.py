from __future__ import annotations

from tukit_comun.esquema import materializar
from tukit_identidad.modelos import Base

if __name__ == "__main__":
    materializar("identidad", Base)
