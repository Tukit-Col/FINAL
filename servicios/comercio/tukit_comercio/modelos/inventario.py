"""Existencias y reservas. El stock es de Comercio; el producto es de Catalogo.

Esta separacion es la que el sistema anterior no tenia: el catalogo (que
productos existen y a que precio publico) y el inventario (cuantos hay y
cuantos estan comprometidos) son datos distintos, en lados opuestos de la
asimetria de recuperacion. Uno se reconstruye scrapeando; el otro, no.
"""

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
    """Existencias de un producto canonico. Una fila por producto.

    `disponible` es lo libre; `reservado` es lo comprometido por reservas de
    checkout que aun no se despachan. El CHECK impide que lo reservado supere lo
    fisico contando ambos.
    """

    __tablename__ = "inventario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Referencia logica a catalogo.producto_canonico.
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
    """Un compromiso de stock nacido de un checkout, con su cantidad congelada.

    Se crea al aceptar la orden y se libera si el pedido se cancela o expira. El
    `estado` distingue una reserva viva de una ya consumida (despachada) o
    liberada.
    """

    __tablename__ = "reserva_inventario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    # Referencia logica a catalogo.producto_canonico.
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
