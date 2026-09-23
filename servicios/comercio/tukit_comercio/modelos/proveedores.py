"""El lado mayorista: de quien Tukit se surte y a que precio contractual.

El `precio_proveedor` es el precio que un mayorista le cobra a Tukit, y NO se
unifica con `catalogo.precio_oferta` (el precio publico observado): son datos
distintos en lados opuestos de la asimetria de recuperacion. El publico se
reconstruye scrapeando; el contractual no se puede perder. Todos los
`producto_canonico_id` de aqui son referencias logicas a Catalogo.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class Proveedor(Base):
    """Un mayorista del que Tukit se surte."""

    __tablename__ = "proveedor"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    nit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contacto: Mapped[str | None] = mapped_column(String(256), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CondicionComercial(Base):
    """Los terminos con un proveedor: plazo de pago, descuento, minimo de compra."""

    __tablename__ = "condicion_comercial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proveedor.id", ondelete="CASCADE"), nullable=False
    )
    plazo_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    descuento_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimo_compra: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("plazo_dias >= 0", name="condicion_plazo_no_negativo"),
        Index("ix_condicion_proveedor", "proveedor_id"),
    )


class PrecioProveedor(Base):
    """El precio contractual que un proveedor le cobra a Tukit por un producto.

    NO se unifica con el precio publico de Catalogo. Ver el docstring del modulo.
    """

    __tablename__ = "precio_proveedor"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proveedor.id", ondelete="CASCADE"), nullable=False
    )
    # Referencia logica a catalogo.producto_canonico.
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    precio: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("precio >= 0", name="precio_proveedor_no_negativo"),
        Index("ix_precio_proveedor", "proveedor_id", "producto_canonico_id"),
    )


class InventarioProveedor(Base):
    """Cuanto stock declara un proveedor para un producto: lo que Tukit puede pedir."""

    __tablename__ = "inventario_proveedor"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proveedor.id", ondelete="CASCADE"), nullable=False
    )
    # Referencia logica a catalogo.producto_canonico.
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    disponible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("disponible >= 0", name="inventario_proveedor_no_negativo"),
        Index("ix_inventario_proveedor", "proveedor_id", "producto_canonico_id"),
    )


class PedidoMayorista(Base):
    """Una orden de compra de Tukit a un proveedor para reponer stock."""

    __tablename__ = "pedido_mayorista"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proveedor.id", ondelete="RESTRICT"), nullable=False
    )
    estado: Mapped[str] = mapped_column(String(24), nullable=False, default="borrador")
    total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recibido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("total >= 0", name="pedido_mayorista_total_no_negativo"),
        Index("ix_pedido_mayorista_proveedor", "proveedor_id"),
    )


class ItemPedidoMayorista(Base):
    """Un renglon de una orden de compra mayorista."""

    __tablename__ = "item_pedido_mayorista"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_mayorista_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido_mayorista.id", ondelete="CASCADE"), nullable=False
    )
    # Referencia logica a catalogo.producto_canonico.
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="item_mayorista_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="item_mayorista_precio_no_negativo"),
        Index("ix_item_mayorista_pedido", "pedido_mayorista_id"),
    )
