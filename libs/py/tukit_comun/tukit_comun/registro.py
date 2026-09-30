"""Logs estructurados atados al id de correlacion (ADR 0021, B.4).

Un fallo cruza cinco servicios; sin un hilo comun, son cinco lineas sueltas.
El id de correlacion ya viaja por HTTP (`http.py`) y por el outbox (`bandeja.py`);
aqui solo se INYECTA en cada linea de log, para poder filtrar por peticion en el
agregador. Es un `logging.Filter` de stdlib —no una libreria de logging nueva—:
lee el contextvar y pega `correlacion` en el registro. `crear_app` lo configura.

Formato JSON por linea: un agregador (Loki, CloudWatch) lo parsea sin regex. Sin
`TUKIT_LOG_JSON` se deja el formato humano de siempre, para no ensuciar la
consola en desarrollo —misma degradacion honesta que el resto del backbone."""

from __future__ import annotations

import json
import logging
import os

from .http import id_de_correlacion


class _FiltroCorrelacion(logging.Filter):
    """Pega el id de correlacion de la peticion en curso en cada registro."""

    def filter(self, registro: logging.LogRecord) -> bool:
        registro.correlacion = id_de_correlacion() or "-"
        return True


class _FormatoJSON(logging.Formatter):
    """Una linea JSON por registro, con la correlacion ya inyectada por el filtro."""

    def format(self, registro: logging.LogRecord) -> str:
        cuerpo = {
            "nivel": registro.levelname,
            "logger": registro.name,
            "mensaje": registro.getMessage(),
            "correlacion": getattr(registro, "correlacion", "-"),
        }
        if registro.exc_info:
            cuerpo["excepcion"] = self.formatException(registro.exc_info)
        return json.dumps(cuerpo, ensure_ascii=False)


def configurar_registro(titulo: str) -> None:
    """Ata el logging raiz al id de correlacion. Idempotente (lo llama cada app).

    Con `TUKIT_LOG_JSON` emite JSON por linea; sin ella, texto humano con la
    correlacion al final. No reconfigura si ya hay un handler nuestro puesto."""
    raiz = logging.getLogger()
    if any(getattr(h, "_tukit", False) for h in raiz.handlers):
        return

    handler = logging.StreamHandler()
    handler._tukit = True  # type: ignore[attr-defined]
    handler.addFilter(_FiltroCorrelacion())
    if os.environ.get("TUKIT_LOG_JSON"):
        handler.setFormatter(_FormatoJSON())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s [%(correlacion)s] %(message)s"))
    raiz.addHandler(handler)
    raiz.setLevel(os.environ.get("TUKIT_LOG_NIVEL", "INFO"))


__all__ = ["configurar_registro"]
