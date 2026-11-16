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

from sqlalchemy import func, insert, select

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
        evento_origen: str | None = None,
        evento_id: int | None = None,
        asunto: str | None = None,
        detalle: str | None = None,
        destino_dominio: str | None = None,
        omitida: bool = False,
    ) -> None:
        """Guarda una notificacion por id, sin contacto. `estado`/`enviada_en`
        salen de si el envio salio: enviada+sello, o fallida+sin sello; `omitida`
        es el envio que no se intento a proposito (destino no enviable). El
        evento de bandeja que la origina, si lo hay, queda en `evento_origen` y
        `evento_id` (ADR 0042). `asunto`, `detalle` y `destino_dominio` alimentan
        el panel de correos enviados; el dominio, nunca la direccion."""
        estado = "omitida" if omitida else ("enviada" if exito else "fallida")
        await self.conexion.execute(
            insert(NOTIFICACION).values(
                id=uuid.uuid4(),
                usuario_id=uuid.UUID(usuario_id),
                canal=canal,
                plantilla=plantilla,
                datos=datos,  # variables de negocio, sin contacto
                estado=estado,
                creado_en=ahora,
                enviada_en=ahora if exito else None,
                evento_origen=evento_origen,
                evento_id=evento_id,
                asunto=asunto,
                detalle=detalle,
                destino_dominio=destino_dominio,
            )
        )

    async def ya_avisado(self, evento_origen: str, evento_id: int) -> bool:
        """Si el evento `evento_id` de la bandeja de `evento_origen` ya tiene un
        aviso `enviada`. Un `fallida` no cuenta: ese evento se vuelve a intentar."""
        encontrada = await self.conexion.scalar(
            select(NOTIFICACION.c.id)
            .where(
                NOTIFICACION.c.evento_origen == evento_origen,
                NOTIFICACION.c.evento_id == evento_id,
                NOTIFICACION.c.estado == "enviada",
            )
            .limit(1)
        )
        return encontrada is not None

    async def listar(
        self, *, estado: str | None = None, plantilla: str | None = None, tope: int = 500
    ) -> list[Any]:
        """Los avisos mas recientes primero, para el panel de correos enviados.
        `pedido` y `caso` viven dentro de `datos`: ese filtro lo aplica quien llama."""
        consulta = select(NOTIFICACION).order_by(NOTIFICACION.c.creado_en.desc()).limit(tope)
        if estado:
            consulta = consulta.where(NOTIFICACION.c.estado == estado)
        if plantilla:
            consulta = consulta.where(NOTIFICACION.c.plantilla == plantilla)
        return list(await self.conexion.execute(consulta))

    async def resumen_por_estado(self) -> dict[str, int]:
        """Cuantos avisos hay en cada estado (enviada, fallida, omitida)."""
        filas = await self.conexion.execute(
            select(NOTIFICACION.c.estado, func.count()).group_by(NOTIFICACION.c.estado)
        )
        return {estado: cantidad for estado, cantidad in filas}


def serializar_notificacion(fila: Any) -> dict[str, Any]:
    """Una fila de `notificacion` para el panel: sin contacto, solo el dominio."""
    datos = fila.datos or {}
    return {
        "id": str(fila.id),
        "usuario_id": str(fila.usuario_id),
        "canal": fila.canal,
        "plantilla": fila.plantilla,
        "estado": fila.estado,
        "asunto": fila.asunto,
        "detalle": fila.detalle,
        "destino_dominio": fila.destino_dominio,
        "pedido": datos.get("pedido"),
        "caso": datos.get("caso"),
        "creado_en": fila.creado_en.isoformat() if fila.creado_en else None,
        "enviada_en": fila.enviada_en.isoformat() if fila.enviada_en else None,
    }
