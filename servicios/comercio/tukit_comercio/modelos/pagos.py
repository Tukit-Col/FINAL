"""El pago y la idempotencia del webhook de la pasarela.

SG-03, y hay que decirlo aqui donde se lee: **nunca se guarda dato de tarjeta**.
Lo unico que Wompi devuelve y lo unico que se persiste es el id de la
transaccion y su estado (§9 del contrato). El PSE no pasa datos de tarjeta de
todas formas, pero la regla es del sistema, no del medio.

`evento_pasarela_procesado` es lo que hace idempotente el webhook: Wompi puede
reintentar la misma notificacion varias veces, y aplicarla dos veces
transicionaria el pedido dos veces o avisaria dos veces al acudiente. La unica
insercion del id del evento actua de candado: el segundo intento choca con el
unique y se responde 200 sin re-aplicar.
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
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoPago, MetodoPago

_ESTADOS_PAGO = ", ".join(f"'{e.value}'" for e in EstadoPago)
_METODOS_PAGO = ", ".join(f"'{e.value}'" for e in MetodoPago)


class Pago(Base):
    """Un intento de pago contra la pasarela. Solo id de transaccion y estado.

    Uno por pedido en el flujo normal; si un intento se rechaza y el acudiente
    reintenta, se crea otro. `referencia_wompi` es la referencia que viaja a la
    pasarela y por la que el webhook lo encuentra.
    """

    __tablename__ = "pago"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    # La referencia que se manda a Wompi y por la que el webhook cruza. Unica:
    # es el ancla de la transaccion.
    referencia_wompi: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # El id de transaccion que Wompi asigna, cuando lo asigna. No hay dato de
    # tarjeta, aqui ni en ninguna otra columna.
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
    """El candado de idempotencia del webhook: un id de evento, procesado una vez.

    La unica insercion del `evento_id` de Wompi es lo que garantiza que una
    notificacion repetida no vuelva a mover el pedido. Ver el docstring del
    modulo.
    """

    __tablename__ = "evento_pasarela_procesado"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # El id que Wompi pone en el evento. Unico: es la clave del candado.
    evento_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    procesado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_evento_pasarela", "evento_id"),)
