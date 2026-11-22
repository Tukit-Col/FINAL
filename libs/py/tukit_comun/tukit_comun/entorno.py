"""En que entorno corre el proceso y las reglas que eso impone.

Decisiones:
- `TUKIT_ENTORNO=produccion` es la unica senal de produccion. Cualquier otro
  valor (o ninguno) es desarrollo: el sistema arranca con avisos y llaves de
  desarrollo para que probar en local no exija configurar nada.
- En produccion faltar una llave no es un aviso, es un error de arranque. Un
  aviso en consola nadie lo lee en un servidor, y el costo es real: sin
  `TUKIT_LLAVE_SESION` los tokens se firman con una llave que esta en el
  codigo publico (cualquiera podria fabricar una sesion de admin), y sin
  `TUKIT_LLAVE_CIFRADO` los datos de los menores se guardan en claro.
"""

from __future__ import annotations

import os

VARIABLE_ENTORNO = "TUKIT_ENTORNO"
PRODUCCION = "produccion"

__all__ = ["PRODUCCION", "VARIABLE_ENTORNO", "ConfiguracionInsegura", "en_produccion", "exigir_en_produccion"]


class ConfiguracionInsegura(RuntimeError):
    """El proceso iba a arrancar en produccion con una configuracion que no protege los datos."""


def en_produccion() -> bool:
    return os.environ.get(VARIABLE_ENTORNO, "").strip().lower() == PRODUCCION


def exigir_en_produccion(condicion: bool, mensaje: str) -> None:
    """En produccion, si la condicion no se cumple, no se arranca. En desarrollo no hace nada."""
    if not condicion and en_produccion():
        raise ConfiguracionInsegura(f"{VARIABLE_ENTORNO}={PRODUCCION}: {mensaje}")
