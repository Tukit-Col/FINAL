from __future__ import annotations

from tukit_comercio.modelos import Base
from tukit_comun.esquema import materializar

if __name__ == "__main__":
    materializar("comercio", Base)
