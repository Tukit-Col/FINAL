from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Inventario(Base):

    __tablename__ = "inventario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    disponible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reservado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("disponible >= 0", name="inventario_disponible_no_negativo"),
        CheckConstraint("reservado >= 0", name="inventario_reservado_no_negativo"),
        Index("ix_inventario_producto", "producto_canonico_id"),
    )


class ReservaInventario(Base):

    __tablename__ = "reserva_inventario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="activa")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="reserva_cantidad_positiva"),
        Index("ix_reserva_pedido", "pedido_id"),
        Index("ix_reserva_producto", "producto_canonico_id"),
    )
