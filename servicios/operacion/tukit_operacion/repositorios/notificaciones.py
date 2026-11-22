from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, insert, select

from ..modelos import Base

NOTIFICACION = Base.metadata.tables["notificacion"]


class RepoNotificaciones:

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
        estado = "omitida" if omitida else ("enviada" if exito else "fallida")
        await self.conexion.execute(
            insert(NOTIFICACION).values(
                id=uuid.uuid4(),
                usuario_id=uuid.UUID(usuario_id),
                canal=canal,
                plantilla=plantilla,
                datos=datos,
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
        consulta = select(NOTIFICACION).order_by(NOTIFICACION.c.creado_en.desc()).limit(tope)
        if estado:
            consulta = consulta.where(NOTIFICACION.c.estado == estado)
        if plantilla:
            consulta = consulta.where(NOTIFICACION.c.plantilla == plantilla)
        return list(await self.conexion.execute(consulta))

    async def resumen_por_estado(self) -> dict[str, int]:
        filas = await self.conexion.execute(
            select(NOTIFICACION.c.estado, func.count()).group_by(NOTIFICACION.c.estado)
        )
        return {estado: cantidad for estado, cantidad in filas}


def serializar_notificacion(fila: Any) -> dict[str, Any]:
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
