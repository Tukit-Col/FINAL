from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoMatricula

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoMatricula)


class Colegio(Base):
    __tablename__ = "colegio"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    nit: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    dane: Mapped[str | None] = mapped_column(String(12), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitio_web: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contacto_nombre: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contacto_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contacto_telefono: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(512), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Sede(Base):
    __tablename__ = "sede"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colegio.id", ondelete="RESTRICT"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_sede_colegio", "colegio_id"),)


class Estudiante(Base):

    __tablename__ = "estudiante"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    documento_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_estudiante_documento",
            "documento_hash",
            unique=True,
            postgresql_where=text("documento_hash IS NOT NULL"),
            sqlite_where=text("documento_hash IS NOT NULL"),
        ),
    )


class Matricula(Base):

    __tablename__ = "matricula"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estudiante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("estudiante.id", ondelete="RESTRICT"), nullable=False
    )
    sede_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sede.id", ondelete="RESTRICT"), nullable=False
    )
    colegio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colegio.id", ondelete="RESTRICT"), nullable=False
    )
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default=EstadoMatricula.ACTIVA.value)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("estudiante_id", "sede_id", "grado", "anio_lectivo", name="matricula_unica"),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="matricula_estado_valido"),
        CheckConstraint("anio_lectivo BETWEEN 2020 AND 2100", name="matricula_anio_plausible"),
        CheckConstraint("(estado = 'activa') = (cerrado_en IS NULL)", name="matricula_cierre_coherente"),
        Index("ix_matricula_sede", "sede_id"),
        Index("ix_matricula_colegio", "colegio_id"),
    )


class AcudienteMatricula(Base):

    __tablename__ = "acudiente_matricula"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True
    )
    matricula_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("matricula.id", ondelete="CASCADE"), primary_key=True
    )
    parentesco: Mapped[str] = mapped_column(String(32), nullable=False, default="acudiente")
    es_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    apodo_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="acudiente_vigencia_coherente"
        ),
        Index(
            "uq_matricula_principal",
            "matricula_id",
            unique=True,
            postgresql_where=text("es_principal AND vigente_hasta IS NULL"),
            sqlite_where=text("es_principal AND vigente_hasta IS NULL"),
        ),
        Index("ix_acudiente_matricula_usuario", "usuario_id", "vigente_hasta"),
    )

    @property
    def vigente(self) -> bool:
        return self.vigente_hasta is None
