"""Adaptador de salida a la propia base de Operacion: el SQL, tras un nombre.

No hay un Protocol de repositorio: es una sola implementacion (`RepoCasos`) que
las pruebas ejercen contra SQLite real, no un doble. El router la construye
dentro de su unidad de trabajo y le pide cada consulta; ella no decide negocio
ni conoce HTTP (ADR 0019).
"""

from .casos import RepoCasos
from .notificaciones import RepoNotificaciones

__all__ = ["RepoCasos", "RepoNotificaciones"]
