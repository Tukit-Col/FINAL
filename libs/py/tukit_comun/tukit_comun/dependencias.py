"""Inyeccion de repositorios por peticion, para FastAPI (ADR 0019).

Los handlers de los cinco servicios repiten el mismo baile:

    async with request.app.state.motor.sesion() as db:
        repo = RepoX(await db.connection())
        ...

`repo_dep(motor, RepoX)` lo convierte en una dependencia (`Depends`) que abre la
sesion, construye el repo atado a su conexion y lo entrega al handler. El
commit/rollback lo sigue haciendo `MotorServicio.sesion()` (ver `bd.py`): como
la dependencia usa `yield`, si el handler revienta FastAPI relanza la excepcion
dentro del generador, el `async with` la ve y hace rollback; si termina bien,
hace commit. No se anade politica nueva, solo se deja de copiar el baile.

El motor se pasa como argumento (no se lee de `app.state` aqui) para no acoplar
la libreria a un nombre de atributo; cada servicio hace
`repo_dep(app.state.motor, RepoX)` una vez y reusa el `Depends`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from .bd import MotorServicio


def repo_dep[R](motor: MotorServicio, construir: Callable[[Any], R]) -> Callable[[], AsyncIterator[R]]:
    """Devuelve una dependencia de FastAPI que entrega un repo por peticion.

    Args:
        motor: El `MotorServicio` del servicio, que gobierna la sesion.
        construir: Fabrica del repo; recibe la conexion de la sesion y devuelve
            el repositorio (p. ej. la clase `RepoPedidos`).

    Returns:
        Un generador async apto para `Depends`, que hace `yield` del repo y deja
        el commit/rollback en manos de `MotorServicio.sesion()`.
    """

    async def dependencia() -> AsyncIterator[R]:
        async with motor.sesion() as db:
            yield construir(await db.connection())

    return dependencia
