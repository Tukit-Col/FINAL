"""Entorno del proceso. Con `TUKIT_ENTORNO=produccion` una configuracion insegura no arranca."""

from __future__ import annotations

import os

VARIABLE_ENTORNO = "TUKIT_ENTORNO"
PRODUCCION = "produccion"

__all__ = ["PRODUCCION", "VARIABLE_ENTORNO", "ConfiguracionInsegura", "en_produccion", "exigir_en_produccion"]


class ConfiguracionInsegura(RuntimeError):
    pass


def en_produccion() -> bool:
    return os.environ.get(VARIABLE_ENTORNO, "").strip().lower() == PRODUCCION


def exigir_en_produccion(condicion: bool, mensaje: str) -> None:
    if not condicion and en_produccion():
        raise ConfiguracionInsegura(f"{VARIABLE_ENTORNO}={PRODUCCION}: {mensaje}")
