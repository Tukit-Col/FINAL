from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoResolucion, Texto

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoResolucion)


class ItemCrudo(Base):
    __tablename__ = "item_crudo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )

    matricula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    hijo_referencia: Mapped[str] = mapped_column(String(64), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)

    texto: Mapped[str] = mapped_column(Text, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default="unidad")
    unidades_por_empaque: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tipo_item: Mapped[str] = mapped_column(String(24), nullable=False, default="util")
    modo_adquisicion: Mapped[str] = mapped_column(String(32), nullable=False, default="mercado_abierto")

    instruccion_colegio: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_externa: Mapped[str | None] = mapped_column(Text, nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)

    confianza_extraccion: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("trabajo_id", "hijo_referencia", "orden", name="uq_item_crudo_orden"),
        CheckConstraint("cantidad >= 0", name="item_crudo_cantidad_no_negativa"),
        CheckConstraint(
            "unidades_por_empaque IS NULL OR unidades_por_empaque > 0",
            name="item_crudo_empaque_positivo",
        ),
        Index("ix_item_crudo_trabajo", "trabajo_id", "hijo_referencia", "orden"),
    )


class CandidatoItem(Base):
    __tablename__ = "candidato_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_crudo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_crudo.id", ondelete="CASCADE"), nullable=False
    )
    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre: Mapped[str] = mapped_column(String(512), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nivel: Mapped[str] = mapped_column(String(16), nullable=False)
    personaje: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default="unidad")
    unidades_por_empaque: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    precio_cop: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confianza: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.000)
    cumple_atributos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("item_crudo_id", "sku", name="uq_candidato_item_sku"),
        CheckConstraint("confianza >= 0 AND confianza <= 1", name="candidato_confianza_en_rango"),
        CheckConstraint("precio_cop IS NULL OR precio_cop >= 0", name="candidato_precio_no_negativo"),
        CheckConstraint("unidades_por_empaque > 0", name="candidato_empaque_positivo"),
        Index("ix_candidato_item", "item_crudo_id", "orden"),
    )


class ResolucionItem(Base):
    __tablename__ = "resolucion_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_crudo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_crudo.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    estado: Mapped[str] = mapped_column(String(24), nullable=False)
    concepto_codigo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    concepto_nombre: Mapped[str | None] = mapped_column(String(256), nullable=True)
    parecido: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.000)

    candidato_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidato_item.id", ondelete="SET NULL"), nullable=True
    )

    atributos_impuestos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    decidido_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    decidido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="resolucion_estado_valido"),
        CheckConstraint("parecido >= 0 AND parecido <= 1", name="resolucion_parecido_en_rango"),
        CheckConstraint(
            "estado <> 'RESUELTO_AUTO' OR candidato_item_id IS NOT NULL",
            name="resolucion_resuelta_tiene_candidato",
        ),
        Index("ix_resolucion_estado", "estado"),
    )


class TransicionResolucion(Base):
    __tablename__ = "transicion_resolucion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resolucion_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resolucion_item.id", ondelete="CASCADE"), nullable=False
    )
    estado_anterior: Mapped[str | None] = mapped_column(String(24), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(24), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    decidida_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    ocurrida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"estado_nuevo IN ({_ESTADOS})", name="transicion_estado_nuevo_valido"),
        CheckConstraint(
            f"estado_anterior IS NULL OR estado_anterior IN ({_ESTADOS})",
            name="transicion_estado_anterior_valido",
        ),
        Index("ix_transicion_resolucion", "resolucion_item_id", "ocurrida_en"),
    )
