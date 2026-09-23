"""El caso y su historia. El recurso central de Operacion.

Un caso referencia a otros dominios por identificador y nunca por llave
foranea fisica: viven en bases distintas. `asignado_a_id` se llama con sufijo
`_id` a proposito, para que la prueba de fronteras lo detecte y exija que este
declarado en el manifiesto; si se llamara `asignado_a`, el detector no lo veria
y la referencia a `identidad.usuario` cruzaria en silencio.

`evento_caso` es la historia append-only: cada cambio de estado, cada nota,
cada asignacion deja una fila. No se edita ni se borra; es lo que permite
auditar como se gestiono un caso.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import CategoriaCaso, EstadoCaso, OrigenCaso, Prioridad, Texto
from .base import Base

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoCaso)
_CATEGORIAS = ", ".join(f"'{e.value}'" for e in CategoriaCaso)
_ORIGENES = ", ".join(f"'{e.value}'" for e in OrigenCaso)
_PRIORIDADES = ", ".join(f"'{e.value}'" for e in Prioridad)


class Caso(Base):
    """Un caso: una PQRS de una persona o una falla de la saga.

    Los tres identificadores cruzados (`usuario_id`, `trabajo_id`, `pedido_id`,
    `asignado_a_id`) son referencias logicas, declaradas en el manifiesto. Todos
    admiten nulo: un caso de sistema puede no tener titular, uno general puede
    no venir de un trabajo ni de un pedido, y uno recien abierto no esta
    asignado.
    """

    __tablename__ = "caso"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    origen: Mapped[str] = mapped_column(String(16), nullable=False)
    categoria: Mapped[str] = mapped_column(String(24), nullable=False)
    estado: Mapped[str] = mapped_column(String(24), nullable=False, default=EstadoCaso.ABIERTO.value)
    prioridad: Mapped[str] = mapped_column(String(16), nullable=False, default=Prioridad.MEDIA.value)
    asunto: Mapped[str] = mapped_column(String(256), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(4096), nullable=False, default="")

    # El titular del caso. Nulo cuando lo abre el sistema. Referencia logica a
    # identidad.usuario. El contacto (correo/celular) NO se guarda: se resolvio
    # a este id contra Identidad al abrir.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Referencia logica a inteligencia.trabajo_pipeline.
    trabajo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Referencia logica a comercio.pedido.
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # El operador que lo gestiona. Referencia logica a identidad.usuario. El
    # sufijo `_id` es lo que hace que la prueba de fronteras exija declararlo.
    asignado_a_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    abierto_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Termino legal o de negocio para responder. Nulo si la categoria no tiene.
    vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="caso_estado_valido"),
        CheckConstraint(f"categoria IN ({_CATEGORIAS})", name="caso_categoria_valida"),
        CheckConstraint(f"origen IN ({_ORIGENES})", name="caso_origen_valido"),
        CheckConstraint(f"prioridad IN ({_PRIORIDADES})", name="caso_prioridad_valida"),
        Index("ix_caso_estado", "estado"),
        Index("ix_caso_prioridad_vence", "prioridad", "vence_en"),
        Index("ix_caso_usuario", "usuario_id"),
        Index("ix_caso_asignado", "asignado_a_id"),
    )


class EventoCaso(Base):
    """Una entrada de la historia append-only de un caso.

    No se edita ni se borra. `tipo` distingue una nota de un cambio de estado o
    de una asignacion; `datos` guarda el detalle estructurado (de/hacia, texto).
    """

    __tablename__ = "evento_caso"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("caso.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    # Quien registro el evento. Referencia logica a identidad.usuario; nulo si
    # lo escribio el sistema.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_evento_caso", "caso_id", "creado_en"),)
