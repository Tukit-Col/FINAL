"""Entorno de Alembic de Operacion.

Tres lineas porque todo lo demas vive en `tukit_comun.migraciones`: el
arranque es identico para los servicios y solo cambian el nombre y los modelos.
Ver el docstring de ese modulo.
"""

from tukit_comun.migraciones import correr
from tukit_operacion.modelos import Base

correr("operacion", Base)
