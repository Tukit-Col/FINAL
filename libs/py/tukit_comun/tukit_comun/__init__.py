"""Libreria compartida del monorepo.

Aqui vive lo que TODOS los servicios necesitan y nadie debe copiar: el acceso
a base de datos, la lectura de configuracion y las utilidades transversales.

La regla de oro (funcion de aptitud `test_ningun_servicio_importa_otro_servicio`):
un servicio solo puede importar de aqui, nunca de otro servicio. Por eso el
motor de base de datos vive en la libreria y no en cada servicio: cada uno le
pasa el nombre de SU base, leido de su entorno, y la libreria no conoce ninguna
base por nombre. Asi se respeta tambien la regla 3 (ningun servicio nombra la
base de otro), porque el nombre nunca se escribe en el codigo del servicio.
"""

from __future__ import annotations

from .bd import MotorServicio, crear_motor, sesion_de_prueba
from .config import ConfigBD, url_desde_entorno
from .identificadores import derivar

__all__ = [
    "ConfigBD",
    "MotorServicio",
    "crear_motor",
    "derivar",
    "sesion_de_prueba",
    "url_desde_entorno",
]
