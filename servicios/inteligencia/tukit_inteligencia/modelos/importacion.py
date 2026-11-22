from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class ImportacionLista(Base):

    __tablename__ = "importacion_lista"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subida_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    clave_idempotencia: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    referencias: Mapped[list[str]] = mapped_column(Texto, nullable=False, default=list)
    contacto_referencia: Mapped[str | None] = mapped_column(String(64), nullable=True)
    colegio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(64), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    carga: Mapped[dict[str, Any] | None] = mapped_column(Texto, nullable=True)
    documento: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proximo_intento_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("clave_idempotencia", name="uq_importacion_clave"),
        CheckConstraint("estado IN ('pendiente', 'importada', 'fallida')", name="importacion_estado_valido"),
        CheckConstraint(
            "estado <> 'fallida' OR error IS NOT NULL", name="importacion_fallida_tiene_diagnostico"
        ),
        Index(
            "ix_importacion_pendiente",
            "proximo_intento_en",
            postgresql_where=text("estado = 'pendiente'"),
            sqlite_where=text("estado = 'pendiente'"),
        ),
        Index("ix_importacion_contacto", "contacto_referencia", "creado_en"),
    )
