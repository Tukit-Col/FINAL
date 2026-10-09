"""Inteligencia con el puerto de Gemini cambiado por las respuestas grabadas de los dorados.

Solo para los E2E de la fase 4 de QA. Levanta la misma app de
`tukit_inteligencia.api`, contra las mismas bases y los mismos vecinos, con un
unico cambio: `api._LEER` (el adaptador de Gemini, `gemini.py`) se sustituye por
un lector que busca la pagina por su sha256 en
`datos/golden/fixtures-modelo/indice.json` y devuelve la respuesta grabada, con
el mismo manejo de errores del adaptador. Asi la subida del acudiente recorre el
stack real con lo que el modelo "dijo", sin clave y sin red.

Ademas instala una guardia de DNS: si algo del proceso intenta resolver el
dominio de Gemini, lo anota en `TUKIT_QA_GUARDIA` y falla. Es la mitad de
NFR-COS-01 que la guardia de pytest no ve, porque corre en otro proceso.

    TUKIT_QA_GUARDIA=/tmp/guardia.log TUKIT_QA_LECTURAS=/tmp/lecturas.log \
        PYTHONPATH=ensayos/e2e .venv/bin/python -m inteligencia_lector_fixtures --puerto 8113
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
from pathlib import Path

from tukit_inteligencia import api
from tukit_inteligencia.percepcion import PaginaLeida, PercepcionFallida

RAIZ = Path(__file__).resolve().parents[2]
INDICE: dict[str, str] = json.loads(
    (RAIZ / "datos" / "golden" / "fixtures-modelo" / "indice.json").read_text()
)
GUARDIA = Path(os.environ.get("TUKIT_QA_GUARDIA", "guardia-gemini.log"))
LECTURAS = Path(os.environ.get("TUKIT_QA_LECTURAS", "lecturas.log"))
_DOMINIO_GEMINI = "generativelanguage.googleapis.com"


def leer_fixture(imagen: bytes, numero: int) -> PaginaLeida:
    huella = hashlib.sha256(imagen).hexdigest()
    ruta = INDICE.get(huella)
    with LECTURAS.open("a") as registro:
        registro.write(f"{numero} {huella} {ruta or '-'}\n")
    if ruta is None:
        raise PercepcionFallida(f"la pagina {numero} no tiene fixture en el indice de los dorados")
    respuesta = json.loads((RAIZ / ruta).read_text())["respuesta_http"]
    if respuesta["status"] != 200:
        raise PercepcionFallida(f"Gemini respondio {respuesta['status']}: {str(respuesta['cuerpo'])[:300]}")
    texto = respuesta["cuerpo"]["candidates"][0]["content"]["parts"][0]["text"]
    return PaginaLeida.model_validate_json(texto)


_original = socket.getaddrinfo


def _vigilada(host, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    nombre = host.decode() if isinstance(host, bytes) else str(host or "")
    if _DOMINIO_GEMINI in nombre.lower():
        with GUARDIA.open("a") as registro:
            registro.write(f"{nombre}\n")
        raise OSError("guardia de QA: intento de llamada real a Gemini")
    return _original(host, *args, **kwargs)


socket.getaddrinfo = _vigilada
api._LEER = leer_fixture

if __name__ == "__main__":
    raise SystemExit(api.main(sys.argv[1:]))
