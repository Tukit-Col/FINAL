from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class Notificacion(Base):
    __tablename__ = "notificacion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    canal: Mapped[str] = mapped_column(String(16), nullable=False, default="correo")
    plantilla: Mapped[str] = mapped_column(String(64), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evento_origen: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evento_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    asunto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detalle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destino_dominio: Mapped[str | None] = mapped_column(String(120), nullable=True)

    __table_args__ = (
        Index("ix_notificacion_usuario", "usuario_id"),
        Index("ix_notificacion_estado", "estado"),
        Index(
            "uq_notificacion_evento_enviada",
            "evento_origen",
            "evento_id",
            unique=True,
            postgresql_where=text("estado = 'enviada'"),
            sqlite_where=text("estado = 'enviada'"),
        ),
    )


class PreferenciaNotificacion(Base):
    __tablename__ = "preferencia_notificacion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    acepta_correo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    acepta_wa_link: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_preferencia_usuario", "usuario_id"),)
