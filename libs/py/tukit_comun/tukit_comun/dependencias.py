from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from .bd import MotorServicio


def repo_dep[R](motor: MotorServicio, construir: Callable[[Any], R]) -> Callable[[], AsyncIterator[R]]:

    async def dependencia() -> AsyncIterator[R]:
        async with motor.sesion() as db:
            yield construir(await db.connection())

    return dependencia
