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
    """El caso para el back-office: lo de `serializar_caso` mas el cuerpo de la
    PQRS y el `usuario_id` del titular (con el que el admin resuelve su correo
    contra Identidad; el contacto nunca se guardo aqui)."""
    return serializar_caso(fila) | {
        "descripcion": fila.descripcion,
        "usuario_id": str(fila.usuario_id) if fila.usuario_id is not None else None,
        "resuelto_en": _iso(fila.resuelto_en),
    }


# Los eventos de un caso son mas que mensajes (asignaciones, notas internas);
# los del acudiente llevan este tipo y son los unicos que vuelven a su pantalla.
TIPO_COMENTARIO_ACUDIENTE = "comentario_acudiente"
# La respuesta del equipo (back-office, `responder_caso`): el acudiente la lee aqui.
TIPO_RESPUESTA_EQUIPO = "respuesta"


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
        pedido_id: uuid.UUID | None = None,
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
                pedido_id=pedido_id,
                abierto_en=abierto_en,
                vence_en=vence_en,
            )
        )

    # -- back-office: conversacion, estado y respuesta ----------------------

    async def eventos_de(self, caso_id: uuid.UUID) -> list[dict[str, Any]]:
        """La historia del caso (respuestas y cambios de estado) en orden cronologico."""
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
        """Mueve el caso solo si SIGUE en `desde`: si otro operador lo movio entre
        la lectura y la escritura, devuelve `False` y no pisa su cambio."""
        resultado = await self.conexion.execute(
            update(CASO)
            .where(CASO.c.id == caso_id, CASO.c.estado == desde)
            .values(estado=hacia, resuelto_en=resuelto_en)
        )
        return bool(resultado.rowcount == 1)

    async def asignar(self, *, caso_id: uuid.UUID, desde: uuid.UUID | None, hacia: uuid.UUID | None) -> bool:
        """Cambia el dueno solo si SIGUE siendo `desde` (patron de `cambiar_estado`)."""
        actual = CASO.c.asignado_a_id.is_(None) if desde is None else CASO.c.asignado_a_id == desde
        resultado = await self.conexion.execute(
            update(CASO).where(CASO.c.id == caso_id, actual).values(asignado_a_id=hacia)
        )
        return bool(resultado.rowcount == 1)

    async def cambiar_prioridad(self, *, caso_id: uuid.UUID, desde: str, hacia: str) -> bool:
        """Cambia la prioridad solo si SIGUE siendo `desde`."""
        resultado = await self.conexion.execute(
            update(CASO).where(CASO.c.id == caso_id, CASO.c.prioridad == desde).values(prioridad=hacia)
        )
        return bool(resultado.rowcount == 1)

    async def vincular_pedido(self, *, caso_id: uuid.UUID, pedido_id: uuid.UUID) -> None:
        await self.conexion.execute(update(CASO).where(CASO.c.id == caso_id).values(pedido_id=pedido_id))

    async def encolar_respuesta(self, *, caso_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        """Outbox: el aviso al acudiente de que su caso tiene respuesta, en la
        MISMA transaccion que la respuesta. El texto NO viaja en la carga: el
        repartidor entrega un aviso por plantilla y el acudiente lee la respuesta
        dentro de Tukit."""
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
        """Una fila en `registro_auditoria`: quien hizo que sobre el caso. Sin el
        texto de la respuesta, que ya vive en la historia del caso."""
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

    # -- lo que el acudiente ve de SUS casos ---------------------------------

    async def listar_de_usuario(self, usuario_id: uuid.UUID) -> list[Any]:
        """Los casos cuyo titular es `usuario_id`, los mas recientes primero."""
        return list(
            await self.conexion.execute(
                select(CASO).where(CASO.c.usuario_id == usuario_id).order_by(CASO.c.abierto_en.desc())
            )
        )

    async def comentarios_de(self, caso_id: uuid.UUID) -> list[dict[str, Any]]:
        """La conversacion que el acudiente ve de su caso, en orden cronologico:
        sus mensajes y las respuestas del equipo (`autor` = "acudiente" | "equipo").

        Los demas eventos (cambio de estado, vinculo con un pedido) son del
        back-office y no salen por esta puerta; tampoco el `actor_id` del staff."""
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
                # Con hora de la app (microsegundos), como `registrar_evento`: la
                # conversacion acudiente+equipo se ordena por `creado_en`.
                creado_en=datetime.now(UTC),
            )
        )
