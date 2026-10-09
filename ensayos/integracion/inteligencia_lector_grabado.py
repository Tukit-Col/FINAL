"""Inteligencia con el puerto de Gemini cambiado por un lector que graba lo que recibe.

Solo para las pruebas de integracion de privacidad (NFR-SEG-07, H-C-15). Levanta
la misma app de `tukit_inteligencia.api`, contra las mismas bases y los mismos
vecinos, con un unico cambio: `api._LEER` (el adaptador de Gemini, `gemini.py`)
se sustituye por un lector que escribe en `TUKIT_QA_CAPTURAS` los bytes que el
producto le habria mandado al proveedor y devuelve una pagina fija. Asi se ve lo
que saldria hacia el modelo sin clave y sin red.

    TUKIT_QA_CAPTURAS=/tmp/capturas PYTHONPATH=ensayos/integracion \
        .venv/bin/python -m inteligencia_lector_grabado --puerto 8113
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from tukit_inteligencia import api
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida

CAPTURAS = Path(os.environ.get("TUKIT_QA_CAPTURAS", "capturas"))


def leer_grabado(imagen: bytes, numero: int) -> PaginaLeida:
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    (CAPTURAS / f"pagina-{numero}.bin").write_bytes(imagen)
    return PaginaLeida(
        grados=["Primero"],
        completa=True,
        items=[ItemExtraido(descripcion="Cuaderno cuadriculado de 100 hojas", cantidad=2, confianza=0.97)],
    )


api._LEER = leer_grabado

if __name__ == "__main__":
    raise SystemExit(api.main(sys.argv[1:]))
