"""El SQL de Operacion contra su propia base, detras de nombres de metodo.

Todo lo que aqui vive salio, verbatim, de los manejadores de `api.py`: los
conteos de la bandeja, la lectura de un caso, el alta de una PQRS y la serie de
metricas congeladas. El router abre la sesion y la unidad de trabajo (`async
with motor.sesion()`), construye un `RepoCasos` atado a esa conexion y le pide
cada paso; el repo no decide nada de negocio —eso es de `dominio/`— ni conoce
HTTP. No hay un Protocol de repositorio: es una sola implementacion, que las
pruebas ejercen contra SQLite real, no un doble (ADR 0019).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, insert, select
from tukit_comun.http import iso as _iso

from ..modelos import Base, EstadoCaso, OrigenCaso, Prioridad

CASO = Base.metadata.tables["caso"]
METRICA = Base.metadata.tables["metrica_diaria"]


def serializar_caso(fila: Any) -> dict[str, Any]:
    """Una fila de `caso` en la forma del contrato de lectura.

    No expone el contacto (correo/celular) porque no vive en `caso`: se resolvio
    a `usuario_id` al abrir y no se guardo (deuda del manifiesto, Ley 1581).
    """
    return {
        "caso_id": str(fila.id),
        "origen": fila.origen,
        "categoria": fila.categoria,
        "estado": fila.estado,
        "prioridad": fila.prioridad,
        "asunto": fila.asunto,
        "abierto_en": _iso(fila.abierto_en),
        "vence_en": _iso(fila.vence_en),
        "trabajo_id": str(fila.trabajo_id) if fila.trabajo_id is not None else None,
        "pedido_id": str(fila.pedido_id) if fila.pedido_id is not None else None,
        "asignado_a": str(fila.asignado_a_id) if fila.asignado_a_id is not None else None,
    }


class RepoCasos:
    """El repositorio de casos y metricas, atado a una conexion de una unidad de
    trabajo. Se construye dentro del `async with motor.sesion()` del router, con
    la conexion ya abierta; no abre ni cierra la sesion: eso es del router.
    """

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    # -- lectura: bandeja --------------------------------------------------

    async def resumen(self, ahora: datetime) -> dict[str, Any]:
        """El consolidado de las tarjetas de la bandeja, sin recontar por pantalla."""
        inactivos = tuple(e.value for e in EstadoCaso.inactivos())
        fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
        hace_una_semana = ahora - timedelta(days=7)

        abiertos = await self.conexion.scalar(
            select(func.count()).where(CASO.c.estado.notin_(inactivos))
        )
        urgentes = await self.conexion.scalar(
            select(func.count()).where(
                CASO.c.estado.notin_(inactivos), CASO.c.prioridad == Prioridad.URGENTE.value
            )
        )
        vencen_hoy = await self.conexion.scalar(
            select(func.count()).where(
                CASO.c.estado.notin_(inactivos),
                CASO.c.vence_en.is_not(None),
                CASO.c.vence_en <= fin_dia,
            )
        )
        resueltos_semana = await self.conexion.scalar(
            select(func.count()).where(
                CASO.c.resuelto_en.is_not(None), CASO.c.resuelto_en >= hace_una_semana
            )
        )
        return {
            "abiertos": int(abiertos or 0),
            "urgentes": int(urgentes or 0),
            "vencen_hoy": int(vencen_hoy or 0),
            "resueltos_semana": int(resueltos_semana or 0),
        }

    async def listar_casos(self) -> list[Any]:
        """Todas las filas de `caso`. El orden de la bandeja lo pone el dominio."""
        return list(await self.conexion.execute(select(CASO)))

    async def obtener(self, caso_id: uuid.UUID) -> Any:
        return (await self.conexion.execute(select(CASO).where(CASO.c.id == caso_id))).one_or_none()

    # -- lectura: metricas -------------------------------------------------

    async def serie_metricas(
        self, *, dimension: str | None, dimension_id: str | None, desde: date | None
    ) -> list[Any]:
        """Las filas crudas de `metrica_diaria`, ordenadas por fecha.

        `desde` llega ya parseada a `date` por el router (la validacion de la
        forma ISO y su 422 son de la superficie). Sin filtros devuelve toda la
        traza; el frontend la agrupa por metrica en series.
        """
        consulta = select(
            METRICA.c.fecha,
            METRICA.c.dimension,
            METRICA.c.dimension_id,
            METRICA.c.metrica,
            METRICA.c.valor,
        ).order_by(METRICA.c.fecha, METRICA.c.dimension, METRICA.c.metrica)
        if dimension:
            consulta = consulta.where(METRICA.c.dimension == dimension)
        if dimension_id:
            consulta = consulta.where(METRICA.c.dimension_id == dimension_id)
        if desde:
            consulta = consulta.where(METRICA.c.fecha >= desde)
        return list(await self.conexion.execute(consulta))

    # -- escritura: alta de PQRS ------------------------------------------

    async def insertar_caso(
        self,
        *,
        caso_id: uuid.UUID,
        categoria: str,
        prioridad: str,
        asunto: str,
        descripcion: str,
        usuario_id: uuid.UUID | None,
        trabajo_id: uuid.UUID | None,
        abierto_en: datetime,
        vence_en: datetime | None,
    ) -> None:
        """Abre un caso de origen ACUDIENTE. El contacto ya se resolvio a
        `usuario_id` fuera de aqui y no se guarda."""
        await self.conexion.execute(
            insert(CASO).values(
                id=caso_id,
                origen=OrigenCaso.ACUDIENTE.value,
                categoria=categoria,
                estado=EstadoCaso.ABIERTO.value,
                prioridad=prioridad,
                asunto=asunto,
                descripcion=descripcion,
                usuario_id=usuario_id,
                trabajo_id=trabajo_id,
                abierto_en=abierto_en,
                vence_en=vence_en,
            )
        )
