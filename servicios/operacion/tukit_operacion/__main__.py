from __future__ import annotations

from tukit_comun.esquema import materializar
from tukit_operacion.modelos import Base

if __name__ == "__main__":
    materializar("operacion", Base)
