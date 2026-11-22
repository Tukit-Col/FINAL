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

from .base import Base, CategoriaCaso, EstadoCaso, OrigenCaso, Prioridad, Texto

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoCaso)
_CATEGORIAS = ", ".join(f"'{e.value}'" for e in CategoriaCaso)
_ORIGENES = ", ".join(f"'{e.value}'" for e in OrigenCaso)
_PRIORIDADES = ", ".join(f"'{e.value}'" for e in Prioridad)


class Caso(Base):
    __tablename__ = "caso"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    origen: Mapped[str] = mapped_column(String(16), nullable=False)
    categoria: Mapped[str] = mapped_column(String(24), nullable=False)
    estado: Mapped[str] = mapped_column(String(24), nullable=False, default=EstadoCaso.ABIERTO.value)
    prioridad: Mapped[str] = mapped_column(String(16), nullable=False, default=Prioridad.MEDIA.value)
    asunto: Mapped[str] = mapped_column(String(256), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(4096), nullable=False, default="")

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    trabajo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    asignado_a_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    abierto_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
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
    __tablename__ = "evento_caso"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("caso.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_evento_caso", "caso_id", "creado_en"),)
