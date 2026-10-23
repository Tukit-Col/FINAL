"""Lo que los scripts de `ensayos/` comparten para arrancar fuera de `make`.

Los servicios no leen `.env` en Python: lo carga `tukit.ps1` en el entorno antes
de levantarlos. Un script de ensayos que se corre a mano (`python ensayos/...`)
no pasa por ahi, asi que lo carga el mismo con `cargar_env`.

Las cachés que un ensayo guarda entre corridas (lo que Gemini ya leyo, por
ejemplo) van a `carpeta_cache()`: `TUKIT_CACHE_ENSAYOS` si esta definida y, si
no, `.cache/ensayos/` en la raiz del repositorio, que git ignora. Antes iban a
`/tmp`, que en Windows es `C:\\tmp`.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def cargar_env(ruta: Path = RAIZ / ".env") -> None:
    """Pone en el entorno las lineas `VARIABLE=valor` de `ruta`, sin pisar lo que ya este.

    Lo que ya esta en el entorno gana: quien exporta una variable antes de
    correr el script (o `make`, o `tukit.ps1`) no quiere que `.env` la cambie.
    Si el archivo no existe no hace nada.
    """
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def carpeta_cache() -> Path:
    """Donde guardan los ensayos lo que reutilizan entre corridas."""
    return Path(os.environ.get("TUKIT_CACHE_ENSAYOS") or RAIZ / ".cache" / "ensayos")
