from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class BandejaSalida(Base):
    __tablename__ = "bandeja_salida"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tipo: Mapped[str] = mapped_column(String(128), nullable=False)
    agregado_tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    agregado_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    carga: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        Index(
            "ix_bandeja_salida_pendiente",
            "creado_en",
            postgresql_where=text("publicado_en IS NULL"),
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )
