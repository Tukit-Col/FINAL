from __future__ import annotations

import json
import logging
import os

from .http import id_de_correlacion


class _FiltroCorrelacion(logging.Filter):

    def filter(self, registro: logging.LogRecord) -> bool:
        registro.correlacion = id_de_correlacion() or "-"
        return True


class _FormatoJSON(logging.Formatter):

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
