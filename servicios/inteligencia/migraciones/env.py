"""Entorno de Alembic de Inteligencia.

Tres lineas porque todo lo demas vive en `tukit_comun.migraciones`: el
arranque es identico para los cinco servicios y solo cambian el nombre y los
modelos. Ver el docstring de ese modulo.
"""

from tukit_comun.migraciones import correr
from tukit_inteligencia.modelos import Base

correr("inteligencia", Base)
