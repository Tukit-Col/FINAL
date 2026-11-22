"""Lo que los scripts de `ensayos/` comparten para arrancar fuera de `make`."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def cargar_env(ruta: Path = RAIZ / ".env") -> None:
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def carpeta_cache() -> Path:
    return Path(os.environ.get("TUKIT_CACHE_ENSAYOS") or RAIZ / ".cache" / "ensayos")
