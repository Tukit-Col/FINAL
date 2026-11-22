from __future__ import annotations

import os

from pydantic import BaseModel


class ConfigBD(BaseModel):

    host: str = "localhost"
    puerto: int = 5432
    usuario: str = "tukit"
    clave: str = "tukit"
    base: str = ""

    def url(self, *, async_: bool = True) -> str:
        driver = "postgresql+asyncpg" if async_ else "postgresql+psycopg"
        return f"{driver}://{self.usuario}:{self.clave}@{self.host}:{self.puerto}/{self.base}"


def _entorno(nombre: str) -> str:
    return f"TUKIT_{nombre.upper()}_DB_URL"


def url_desde_entorno(servicio: str, *, async_: bool = True) -> str:
    directa = os.environ.get(_entorno(servicio))
    if directa:
        return directa

    cfg = ConfigBD(
        host=os.environ.get("TUKIT_DB_HOST", "localhost"),
        puerto=int(os.environ.get("TUKIT_DB_PORT", "5432")),
        usuario=os.environ.get("TUKIT_DB_USER", "tukit"),
        clave=os.environ.get("TUKIT_DB_PASSWORD", "tukit"),
        base=f"tukit_{servicio}",
    )
    return cfg.url(async_=async_)
