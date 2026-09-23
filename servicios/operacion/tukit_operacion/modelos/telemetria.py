"""Telemetria y auditoria: clickouts, registro de acciones y metricas diarias.

`evento_clickout` mide UI-08 (el padre sale a comprar a una tienda): referencia
al kit y al producto por identificador, ambos de otros dominios. `registro_
auditoria` es la traza de quien hizo que, que llega por la bandeja de salida de
los demas servicios. `metrica_diaria` es el snapshot para las series de tiempo
del panel de colegio, para no recomputar agregados historicos en cada carga.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class EventoClickout(Base):
    """Un padre que sale a una tienda desde un kit (UI-08). Mide la conversion."""

    __tablename__ = "evento_clickout"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Referencia logica a inteligencia.kit.
    kit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # Referencia logica a catalogo.producto_canonico.
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    tienda: Mapped[str | None] = mapped_column(String(128), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_clickout_kit", "kit_id"),
        Index("ix_clickout_producto", "producto_canonico_id"),
    )


class RegistroAuditoria(Base):
    """Una accion auditable, con su actor. Llega por la bandeja de salida.

    Referencia al actor sin poder bloquearlo ni borrarlo en cascada: es una
    referencia logica a identidad.usuario. La traza no se borra aunque el actor
    se anonimice; se conserva el id.
    """

    __tablename__ = "registro_auditoria"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Referencia logica a identidad.usuario. Nulo si la accion fue del sistema.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    accion: Mapped[str] = mapped_column(String(64), nullable=False)
    agregado_tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    agregado_id: Mapped[str] = mapped_column(String(128), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_auditoria_actor", "actor_id"),
        Index("ix_auditoria_agregado", "agregado_tipo", "agregado_id"),
    )


class MetricaDiaria(Base):
    """Un snapshot diario de una metrica, por dimension. Alimenta las series.

    `dimension` y `dimension_id` acotan la metrica (por ejemplo colegio + id);
    `metrica` es el nombre (kits_armados, cobertura_pct, ahorro_cop) y `valor`
    su medida entera del dia. La unica por (fecha, dimension, dimension_id,
    metrica) hace idempotente el recomputo.
    """

    __tablename__ = "metrica_diaria"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metrica: Mapped[str] = mapped_column(String(64), nullable=False)
    valor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("fecha", "dimension", "dimension_id", "metrica", name="uq_metrica_diaria"),
        Index("ix_metrica_dimension", "dimension", "dimension_id", "fecha"),
    )
