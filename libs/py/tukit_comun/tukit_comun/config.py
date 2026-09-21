"""Configuracion de conexion, leida del entorno.

Ningun servicio escribe el nombre de su base ni el de otra en el codigo: lo
lee del entorno. Esto no es solo higiene de doce factores, es lo que mantiene
verde la funcion de aptitud `test_ningun_servicio_nombra_la_base_de_otro`, que
falla si el string de una base ajena aparece en un `.py` de servicio.

El servicio arma su URL con una sola llamada:

    from tukit_comun import url_desde_entorno
    URL = url_desde_entorno("identidad")   # lee TUKIT_IDENTIDAD_DB_URL, o la
                                            # construye desde las piezas comunes
"""

from __future__ import annotations

import os

from pydantic import BaseModel


class ConfigBD(BaseModel):
    """Piezas de una conexion a Postgres. Inmutable una vez armada."""

    host: str = "localhost"
    puerto: int = 5432
    usuario: str = "tukit"
    clave: str = "tukit"
    base: str = ""

    def url(self, *, async_: bool = True) -> str:
        driver = "postgresql+asyncpg" if async_ else "postgresql+psycopg"
        return f"{driver}://{self.usuario}:{self.clave}@{self.host}:{self.puerto}/{self.base}"


def _entorno(nombre: str) -> str:
    """Nombre de la variable de entorno con la URL completa de un servicio.

    `identidad` -> `TUKIT_IDENTIDAD_DB_URL`. Cada servicio define solo la suya;
    ninguno conoce la de otro.
    """
    return f"TUKIT_{nombre.upper()}_DB_URL"


def url_desde_entorno(servicio: str, *, async_: bool = True) -> str:
    """URL de conexion del servicio, con dos fuentes en orden de precedencia.

    1. `TUKIT_<SERVICIO>_DB_URL` completa, si esta definida. Es la via de
       produccion y la de un compose que inyecta la URL entera.
    2. Piezas comunes (`TUKIT_DB_HOST`, `TUKIT_DB_USER`, ...) mas la convencion
       de nombre de base `tukit_<servicio>`. Es la via de desarrollo local:
       una sola configuracion de host/credenciales sirve para las cinco bases.

    El nombre de la base NUNCA se pasa como literal desde el servicio: o viene
    entero en la variable del punto 1, o se deriva del argumento `servicio`
    aqui, en la libreria. El `.py` del servicio nunca contiene el string.
    """
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
