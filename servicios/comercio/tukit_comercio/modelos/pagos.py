from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoPago, MetodoPago

_ESTADOS_PAGO = ", ".join(f"'{e.value}'" for e in EstadoPago)
_METODOS_PAGO = ", ".join(f"'{e.value}'" for e in MetodoPago)


class Pago(Base):

    __tablename__ = "pago"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    referencia_wompi: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    transaccion_wompi: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metodo: Mapped[str] = mapped_column(String(16), nullable=False, default=MetodoPago.PSE.value)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default=EstadoPago.INICIADO.value)
    monto: Mapped[int] = mapped_column(BigInteger, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS_PAGO})", name="pago_estado_valido"),
        CheckConstraint(f"metodo IN ({_METODOS_PAGO})", name="pago_metodo_valido"),
        CheckConstraint("monto >= 0", name="pago_monto_no_negativo"),
        Index("ix_pago_pedido", "pedido_id"),
        Index("ix_pago_referencia", "referencia_wompi"),
    )


class EventoPasarelaProcesado(Base):

    __tablename__ = "evento_pasarela_procesado"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    procesado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_evento_pasarela", "evento_id"),)
