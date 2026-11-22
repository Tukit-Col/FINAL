from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, insert, select, update
from tukit_comun.bandeja import con_correlacion
from tukit_comun.http import iso as _iso

from ..modelos import Base, EstadoCaso, OrigenCaso, Prioridad

CASO = Base.metadata.tables["caso"]
METRICA = Base.metadata.tables["metrica_diaria"]
EVENTO = Base.metadata.tables["evento_caso"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
AUDITORIA = Base.metadata.tables["registro_auditoria"]


def serializar_detalle_caso(fila: Any) -> dict[str, Any]:
    return serializar_caso(fila) | {
        "descripcion": fila.descripcion,
        "usuario_id": str(fila.usuario_id) if fila.usuario_id is not None else None,
        "resuelto_en": _iso(fila.resuelto_en),
    }


TIPO_COMENTARIO_ACUDIENTE = "comentario_acudiente"
TIPO_RESPUESTA_EQUIPO = "respuesta"


def serializar_caso(fila: Any) -> dict[str, Any]:
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

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def resumen(self, ahora: datetime) -> dict[str, Any]:
        inactivos = tuple(e.value for e in EstadoCaso.inactivos())
        fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
        hace_una_semana = ahora - timedelta(days=7)

        abiertos = await self.conexion.scalar(select(func.count()).where(CASO.c.estado.notin_(inactivos)))
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
        sin_asignar = await self.conexion.scalar(
            select(func.count()).where(CASO.c.estado.notin_(inactivos), CASO.c.asignado_a_id.is_(None))
        )
        vencidos = await self.conexion.scalar(
            select(func.count()).where(
                CASO.c.estado.notin_(inactivos), CASO.c.vence_en.is_not(None), CASO.c.vence_en < ahora
            )
        )
        resueltos_semana = await self.conexion.scalar(
            select(func.count()).where(CASO.c.resuelto_en.is_not(None), CASO.c.resuelto_en >= hace_una_semana)
        )
        return {
            "abiertos": int(abiertos or 0),
            "urgentes": int(urgentes or 0),
            "vencen_hoy": int(vencen_hoy or 0),
            "resueltos_semana": int(resueltos_semana or 0),
            "sin_asignar": int(sin_asignar or 0),
            "vencidos": int(vencidos or 0),
        }

    async def listar_casos(self) -> list[Any]:
        return list(await self.conexion.execute(select(CASO)))

    async def obtener(self, caso_id: uuid.UUID) -> Any:
        return (await self.conexion.execute(select(CASO).where(CASO.c.id == caso_id))).one_or_none()

    async def serie_metricas(
        self, *, dimension: str | None, dimension_id: str | None, desde: date | None
    ) -> list[Any]:
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
        pedido_id: uuid.UUID | None = None,
    ) -> None:
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
                pedido_id=pedido_id,
                abierto_en=abierto_en,
                vence_en=vence_en,
            )
        )

    async def eventos_de(self, caso_id: uuid.UUID) -> list[dict[str, Any]]:
        filas = await self.conexion.execute(
            select(EVENTO).where(EVENTO.c.caso_id == caso_id).order_by(EVENTO.c.creado_en.asc(), EVENTO.c.id.asc())
        )
        return [
            {
                "tipo": f.tipo,
                "datos": dict(f.datos or {}),
                "actor_id": str(f.actor_id) if f.actor_id is not None else None,
                "creado_en": _iso(f.creado_en),
            }
            for f in filas
        ]

    async def registrar_evento(
        self, *, caso_id: uuid.UUID, tipo: str, datos: dict[str, Any], actor_id: uuid.UUID, ahora: datetime
    ) -> None:
        await self.conexion.execute(
            insert(EVENTO).values(
                id=uuid.uuid4(), caso_id=caso_id, tipo=tipo, datos=datos, actor_id=actor_id, creado_en=ahora
            )
        )

    async def cambiar_estado(
        self, *, caso_id: uuid.UUID, desde: str, hacia: str, resuelto_en: datetime | None
    ) -> bool:
        resultado = await self.conexion.execute(
            update(CASO)
            .where(CASO.c.id == caso_id, CASO.c.estado == desde)
            .values(estado=hacia, resuelto_en=resuelto_en)
        )
        return bool(resultado.rowcount == 1)

    async def asignar(self, *, caso_id: uuid.UUID, desde: uuid.UUID | None, hacia: uuid.UUID | None) -> bool:
        actual = CASO.c.asignado_a_id.is_(None) if desde is None else CASO.c.asignado_a_id == desde
        resultado = await self.conexion.execute(
            update(CASO).where(CASO.c.id == caso_id, actual).values(asignado_a_id=hacia)
        )
        return bool(resultado.rowcount == 1)

    async def cambiar_prioridad(self, *, caso_id: uuid.UUID, desde: str, hacia: str) -> bool:
        resultado = await self.conexion.execute(
            update(CASO).where(CASO.c.id == caso_id, CASO.c.prioridad == desde).values(prioridad=hacia)
        )
        return bool(resultado.rowcount == 1)

    async def vincular_pedido(self, *, caso_id: uuid.UUID, pedido_id: uuid.UUID) -> None:
        await self.conexion.execute(update(CASO).where(CASO.c.id == caso_id).values(pedido_id=pedido_id))

    async def encolar_respuesta(self, *, caso_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        await self.conexion.execute(
            insert(BANDEJA).values(
                tipo="caso_respuesta",
                agregado_tipo="caso",
                agregado_id=caso_id,
                carga=con_correlacion({"caso_id": str(caso_id), "usuario_id": str(usuario_id)}),
            )
        )

    async def auditar(
        self, *, actor_id: uuid.UUID, accion: str, caso_id: uuid.UUID, datos: dict[str, Any], ahora: datetime
    ) -> None:
        await self.conexion.execute(
            insert(AUDITORIA).values(
                id=uuid.uuid4(),
                actor_id=actor_id,
                accion=accion,
                agregado_tipo="caso",
                agregado_id=str(caso_id),
                datos=datos,
                creado_en=ahora,
            )
        )

    async def listar_de_usuario(self, usuario_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(CASO).where(CASO.c.usuario_id == usuario_id).order_by(CASO.c.abierto_en.desc())
            )
        )

    async def comentarios_de(self, caso_id: uuid.UUID) -> list[dict[str, Any]]:
        filas = await self.conexion.execute(
            select(EVENTO)
            .where(EVENTO.c.caso_id == caso_id, EVENTO.c.tipo.in_([TIPO_COMENTARIO_ACUDIENTE, TIPO_RESPUESTA_EQUIPO]))
            .order_by(EVENTO.c.creado_en)
        )
        return [
            {
                "texto": (f.datos or {}).get("texto", ""),
                "creado_en": _iso(f.creado_en),
                "autor": "acudiente" if f.tipo == TIPO_COMENTARIO_ACUDIENTE else "equipo",
            }
            for f in filas
        ]

    async def agregar_comentario(self, caso_id: uuid.UUID, usuario_id: uuid.UUID, texto: str) -> None:
        await self.conexion.execute(
            insert(EVENTO).values(
                id=uuid.uuid4(),
                caso_id=caso_id,
                tipo=TIPO_COMENTARIO_ACUDIENTE,
                datos={"texto": texto},
                actor_id=usuario_id,
                creado_en=datetime.now(UTC),
            )
        )
