from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correo: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    clave_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    nombre_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    celular: Mapped[str | None] = mapped_column(String(32), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    version_permisos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    anonimizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Direccion(Base):

    __tablename__ = "direccion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    etiqueta: Mapped[str] = mapped_column(String(64), nullable=False, default="casa")

    ciudad: Mapped[str] = mapped_column(String(128), nullable=False)
    localidad: Mapped[str | None] = mapped_column(String(128), nullable=True)

    linea_cifrada: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    contacto_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    predeterminada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archivada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_direccion_predeterminada",
            "usuario_id",
            unique=True,
            postgresql_where=text("predeterminada AND archivada_en IS NULL"),
            sqlite_where=text("predeterminada AND archivada_en IS NULL"),
        ),
        Index("ix_direccion_usuario", "usuario_id", "archivada_en"),
    )

    @property
    def activa(self) -> bool:
        return self.archivada_en is None


class BandejaSalida(Base):

    __tablename__ = "bandeja_salida"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tipo: Mapped[str] = mapped_column(String(128), nullable=False)
    agregado_tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    agregado_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    carga: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        Index(
            "ix_bandeja_pendiente",
            "creado_en",
            postgresql_where=text("publicado_en IS NULL"),
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )
