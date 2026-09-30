"""El SQL de `notificacion` en la propia base de Operacion, tras un nombre.

Salio, verbatim, del `_registrar_notificacion` del repartidor: un insert por
identificador que NO copia el contacto (correo/celular), solo el `usuario_id` y
las variables de negocio (Ley 1581). El worker abre la sesion y le pasa la
conexion; este repo no decide negocio ni conoce la bandeja de origen (ADR 0019).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import insert

from ..modelos import Base

NOTIFICACION = Base.metadata.tables["notificacion"]


class RepoNotificaciones:
    """Las notificaciones de Operacion, atadas a una conexion de una unidad de
    trabajo. Se construye dentro del `async with motor.sesion()` del worker."""

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def registrar(
        self,
        *,
        usuario_id: str,
        canal: str,
        plantilla: str,
        datos: dict[str, object],
        exito: bool,
        ahora: datetime,
    ) -> None:
        """Guarda una notificacion por id, sin contacto. `estado`/`enviada_en`
        salen de si el envio salio: enviada+sello, o fallida+sin sello."""
        await self.conexion.execute(
            insert(NOTIFICACION).values(
                id=uuid.uuid4(),
                usuario_id=uuid.UUID(usuario_id),
                canal=canal,
                plantilla=plantilla,
                datos=datos,  # variables de negocio, sin contacto
                estado="enviada" if exito else "fallida",
                creado_en=ahora,
                enviada_en=ahora if exito else None,
            )
        )
