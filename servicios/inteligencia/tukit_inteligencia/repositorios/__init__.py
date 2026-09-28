"""Los adaptadores de salida de Inteligencia: aqui vive el SQL (ADR 0019).

`RepoTrabajos` reune las consultas por-transaccion del pipeline (estado, etapas,
escritura de kits, evento de outbox, cache canonica). Se construye atado a una
conexion, dentro del `async with motor.engine.begin()` de quien lo use: no abre
ni cierra la transaccion, para que el orquestador mantenga la invariante de que
el evento de outbox y el cambio de estado que lo dispara vivan en una sola.
"""

from __future__ import annotations

from .trabajos import RepoTrabajos

__all__ = ["RepoTrabajos"]
