from __future__ import annotations

import uuid

ESPACIO = uuid.NAMESPACE_URL
PREFIJO = "tukit:"


def derivar(*partes: str) -> uuid.UUID:
    return uuid.uuid5(ESPACIO, PREFIJO + ":".join(str(p) for p in partes))
