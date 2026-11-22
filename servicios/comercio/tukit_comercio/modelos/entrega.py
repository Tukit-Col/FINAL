from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ZonaEntrega(Base):

    __tablename__ = "zona_entrega"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(128), nullable=False)
    localidad: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_zona_ciudad", "ciudad"),)


class RutaReparto(Base):

    __tablename__ = "ruta_reparto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zona_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("zona_entrega.id", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transportadora: Mapped[str | None] = mapped_column(String(128), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_ruta_zona_fecha", "zona_id", "fecha"),)


class Envio(Base):

    __tablename__ = "envio"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    destinatario: Mapped[str] = mapped_column(String(256), nullable=False)
    direccion: Mapped[str] = mapped_column(String(512), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(128), nullable=False)

    telefono: Mapped[str | None] = mapped_column(String(32), nullable=True)
    departamento: Mapped[str | None] = mapped_column(String(128), nullable=True)
    documento_destinatario: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indicaciones: Mapped[str | None] = mapped_column(String(512), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitud: Mapped[float | None] = mapped_column(Float, nullable=True)

    zona_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("zona_entrega.id", ondelete="SET NULL"), nullable=True
    )
    ruta_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ruta_reparto.id", ondelete="SET NULL"), nullable=True
    )

    transportadora: Mapped[str | None] = mapped_column(String(128), nullable=True)
    guia: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repartidor_nombre: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repartidor_celular: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entrega_estimada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entregado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_envio_pedido", "pedido_id"),)
