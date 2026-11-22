"""El pedido, sus lineas, su historial de estados y las devoluciones.

Decisiones:
- Precio congelado: `linea_pedido.precio_unitario` se escribe al confirmar y no se vuelve a leer de
  Catalogo; un pedido es un acuerdo economico y el total aprobado no puede moverse.
- Nombre del colegio y cantidad de hijos se congelan en el pedido, para que el panel de logistica
  responda con una sola base aunque Identidad este caida.
- `Dinero` es un entero en pesos COP; un total o un precio de linea confirmado nunca es nulo.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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

from .base import Base, EstadoPedido, Texto

_ESTADOS_PEDIDO = ", ".join(f"'{e.value}'" for e in EstadoPedido)


class Pedido(Base):
    __tablename__ = "pedido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    trabajo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    estado: Mapped[str] = mapped_column(String(24), nullable=False, default=EstadoPedido.PENDIENTE_PAGO.value)

    total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    hijos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    colegios: Mapped[list[str]] = mapped_column(Texto, nullable=False, default=list)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS_PEDIDO})", name="pedido_estado_valido"),
        CheckConstraint("total >= 0", name="pedido_total_no_negativo"),
        CheckConstraint("hijos >= 0", name="pedido_hijos_no_negativo"),
        Index("ix_pedido_usuario", "usuario_id", "creado_en"),
        Index("ix_pedido_estado", "estado"),
        Index("ix_pedido_trabajo", "trabajo_id"),
    )


class LineaPedido(Base):
    __tablename__ = "linea_pedido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )

    matricula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    precio_unitario: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="linea_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="linea_precio_no_negativo"),
        Index("ix_linea_pedido", "pedido_id"),
    )


class Devolucion(Base):
    __tablename__ = "devolucion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    motivo: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    monto: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("monto >= 0", name="devolucion_monto_no_negativo"),
        Index("ix_devolucion_pedido", "pedido_id"),
    )


class HistorialPedido(Base):
    __tablename__ = "historial_pedido"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    estado_desde: Mapped[str] = mapped_column(String(24), nullable=False)
    estado_hacia: Mapped[str] = mapped_column(String(24), nullable=False)

    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_correo: Mapped[str | None] = mapped_column(String(320), nullable=True)

    nota: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tipo_incidencia: Mapped[str | None] = mapped_column(String(32), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"estado_desde IN ({_ESTADOS_PEDIDO})", name="historial_estado_desde_valido"),
        CheckConstraint(f"estado_hacia IN ({_ESTADOS_PEDIDO})", name="historial_estado_hacia_valido"),
        Index("ix_historial_pedido", "pedido_id", "id"),
    )
