"""El trabajo y sus etapas: el estado que hace consultable y reanudable al pipeline.

Decisiones:
- El recurso central es el trabajo y no el kit: el pipeline tarda minutos y el flujo exige una
  pausa humana, y nada de eso cabe en una peticion sincronica.
- El estado vive en la base y no en la memoria del proceso: un trabajo se consulta desde otro
  proceso, se reanuda desde la ultima etapa buena y se audita despues.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
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

from .base import Base, EstadoEtapa, EstadoTrabajo, Texto

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoTrabajo)
_ESTADOS_ETAPA = ", ".join(f"'{e.value}'" for e in EstadoEtapa)

ETAPAS = ("percepcion", "normalizacion", "resolucion", "optimizacion")


class TrabajoPipeline(Base):

    __tablename__ = "trabajo_pipeline"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    estado: Mapped[str] = mapped_column(String(24), nullable=False, default=EstadoTrabajo.ENCOLADO.value)
    origen: Mapped[str] = mapped_column(String(24), nullable=False, default="colegio_grado")

    hijos: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    preferencias_cifradas: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    estimado_segundos: Mapped[int] = mapped_column(Integer, nullable=False, default=180)

    degradaciones: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    cambios: Mapped[dict[str, Any]] = mapped_column(
        Texto, nullable=False, default=dict, server_default=text("'{}'")
    )

    error: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)

    revisado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nota_revision: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="trabajo_estado_valido"),
        CheckConstraint(
            "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', "
            "'lista_verificada', 'parent_apply', 'canonico_lista')",
            name="trabajo_origen_valido",
        ),
        CheckConstraint("estimado_segundos > 0", name="trabajo_estimado_positivo"),
        CheckConstraint("estado <> 'fallido' OR error IS NOT NULL", name="trabajo_fallido_tiene_diagnostico"),
        Index(
            "ix_trabajo_en_cola",
            "creado_en",
            postgresql_where=text("estado = 'espera_revision'"),
            sqlite_where=text("estado = 'espera_revision'"),
        ),
        Index("ix_trabajo_usuario", "usuario_id", "creado_en"),
    )


class EtapaTrabajo(Base):

    __tablename__ = "etapa_trabajo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(32), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default=EstadoEtapa.PENDIENTE.value)
    ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalle: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    iniciada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("trabajo_id", "nombre", name="uq_etapa_trabajo"),
        CheckConstraint(f"estado IN ({_ESTADOS_ETAPA})", name="etapa_estado_valido"),
        CheckConstraint("ms IS NULL OR ms >= 0", name="etapa_ms_no_negativo"),
        Index("ix_etapa_trabajo", "trabajo_id"),
    )


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
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index(
            "ix_bandeja_salida_pendiente",
            "creado_en",
            postgresql_where=text("publicado_en IS NULL"),
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )


class KitCanonico(Base):

    __tablename__ = "kit_canonico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(64), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("colegio_id", "grado", "anio_lectivo", name="uq_kit_canonico_grado"),)


def puede_pasar(actual: str, siguiente: str) -> bool:
    try:
        desde = EstadoTrabajo(actual)
        hacia = EstadoTrabajo(siguiente)
    except ValueError:
        return False
    from .base import TRANSICIONES

    return hacia in TRANSICIONES[desde]


__all__ = [
    "ETAPAS",
    "BandejaSalida",
    "EtapaTrabajo",
    "KitCanonico",
    "TrabajoPipeline",
    "puede_pasar",
]
