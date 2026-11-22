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
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EdicionLibro(Base):

    __tablename__ = "edicion_libro"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isbn13: Mapped[str] = mapped_column(String(13), nullable=False, unique=True)
    titulo: Mapped[str] = mapped_column(String(512), nullable=False)
    editorial: Mapped[str] = mapped_column(String(256), nullable=False)
    anio_edicion: Mapped[int] = mapped_column(Integer, nullable=False)
    numero_edicion: Mapped[str | None] = mapped_column(String(32), nullable=True)

    area: Mapped[str] = mapped_column(String(64), nullable=False)
    grado_sugerido: Mapped[str | None] = mapped_column(String(32), nullable=True)

    programa: Mapped[str] = mapped_column(String(32), nullable=False, default="nacional")

    descontinuada_en: Mapped[date | None] = mapped_column(Date, nullable=True)
    reemplazada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="SET NULL"), nullable=True
    )

    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("producto_canonico.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "programa IN ('nacional', 'bachillerato_internacional', 'cambridge', 'otro')",
            name="edicion_programa_valido",
        ),
        CheckConstraint("anio_edicion >= 1980", name="edicion_anio_plausible"),
        CheckConstraint(
            "reemplazada_por_id IS NULL OR reemplazada_por_id <> id",
            name="edicion_no_se_reemplaza_a_si_misma",
        ),
        Index("ix_edicion_area_programa", "area", "programa"),
    )


class ConfiguracionColegioEditorial(Base):

    __tablename__ = "configuracion_colegio_editorial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)

    dias_ventana_decision: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    politica_silencio: Mapped[str] = mapped_column(String(32), nullable=False, default="conservar_vigente")
    exige_aprobacion_humana: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    programa_predeterminado: Mapped[str] = mapped_column(String(32), nullable=False, default="nacional")
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("dias_ventana_decision > 0", name="config_ventana_positiva"),
        CheckConstraint(
            "politica_silencio IN ('conservar_vigente', 'aceptar_propuesta', 'escalar')",
            name="config_politica_silencio_valida",
        ),
    )


class VersionVigente(Base):

    __tablename__ = "version_vigente"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    edicion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="RESTRICT"), nullable=False
    )
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="version_vigencia_coherente"
        ),
        Index(
            "uq_version_vigente_actual",
            "colegio_id",
            "area",
            "grado",
            "anio_lectivo",
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
            sqlite_where=text("vigente_hasta IS NULL"),
        ),
    )


class PropuestaVersion(Base):

    __tablename__ = "propuesta_version"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    edicion_propuesta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="CASCADE"), nullable=False
    )
    edicion_actual_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="SET NULL"), nullable=True
    )
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    delta_precio_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estado: Mapped[str] = mapped_column(String(24), nullable=False, default="pendiente")
    recibida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelta_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'aceptada', 'rechazada', 'vencida')", name="propuesta_estado_valido"
        ),
        CheckConstraint("vence_en > recibida_en", name="propuesta_ventana_coherente"),
        CheckConstraint(
            "(estado IN ('pendiente', 'vencida')) OR (resuelta_en IS NOT NULL AND resuelta_por IS NOT NULL)",
            name="propuesta_resuelta_tiene_responsable",
        ),
        CheckConstraint(
            "edicion_actual_id IS NULL OR edicion_actual_id <> edicion_propuesta_id",
            name="propuesta_cambia_de_edicion",
        ),
        Index(
            "ix_propuesta_por_vencer",
            "vence_en",
            postgresql_where=text("estado = 'pendiente'"),
            sqlite_where=text("estado = 'pendiente'"),
        ),
        UniqueConstraint(
            "colegio_id",
            "area",
            "grado",
            "anio_lectivo",
            "edicion_propuesta_id",
            name="uq_propuesta_sin_duplicar",
        ),
    )
