"""El pedido, sus lineas y las devoluciones. El corazon de "todo lo que toca dinero".

Dos decisiones de congelacion gobiernan este archivo, y las dos son ADRs:

- **Precio congelado (ADR 0012, R-PRECIO).** `linea_pedido.precio_unitario` se
  escribe al confirmar y no se vuelve a leer de Catalogo. Un pedido es un
  acuerdo economico: si el precio publico cambia manana, el total que el
  acudiente aprobo no puede moverse.
- **Nombre de colegio y conteo de hijos congelados en el pedido.** El panel de
  logistica pinta "2 hijos, Colegio San Jose" sin abrir una consulta a
  Identidad por cada fila. Copiar esos dos datos al confirmar mantiene la
  superficie de lectura dentro de una sola base, que es lo que permite que
  Comercio responda aunque Identidad este caida.

`Dinero` es entero en pesos COP. `null` no aplica a un total ni a un precio de
linea confirmado: son cantidades acordadas, no desconocidas.
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
    """Una compra, por HOGAR y no por hijo: dos hermanos caben en un solo pago.

    Nace del trabajo del pipeline que el acudiente aprobo (`trabajo_id`), pero
    admite nulo porque un pedido tambien puede entrar por otra via el dia que
    exista. `total` se congela con la suma de las lineas al confirmar.
    """

    __tablename__ = "pedido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Quien compra. La supresion del titular NO borra el pedido: es obligacion
    # contable. Referencia logica a identidad.usuario (declarada en el
    # manifiesto), nunca llave foranea fisica: viven en bases distintas.
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    # De que trabajo publicado salio, para cruzar el back-office de logistica
    # con la cola de revision. Referencia logica a inteligencia.trabajo_pipeline.
    trabajo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    estado: Mapped[str] = mapped_column(
        String(24), nullable=False, default=EstadoPedido.PENDIENTE_PAGO.value
    )

    # Entero en pesos COP. Congelado al confirmar (ADR 0012).
    total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Copias congeladas para que la lectura no cruce a Identidad: cuantos hijos
    # cubre el pedido y los nombres de colegio a mostrar en la tarjeta.
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
    """Un renglon del pedido: un producto, una cantidad, un precio congelado.

    `matricula_id` va en la LINEA y no en el pedido a proposito: es lo que deja
    que dos hermanos (dos matriculas) quepan en un solo pago. El precio se
    copia aqui al confirmar y no se relee (ADR 0012). El nombre tambien se
    copia para que la lectura no dependa de Catalogo.
    """

    __tablename__ = "linea_pedido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )

    # Para que estudiante es este renglon. Referencia logica a
    # identidad.matricula. Nulo admitido para un renglon que no sea por hijo.
    matricula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Que producto. Referencia logica a catalogo.producto_canonico.
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Congelado en la reserva (ADR 0012): entero en pesos COP.
    precio_unitario: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="linea_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="linea_precio_no_negativo"),
        Index("ix_linea_pedido", "pedido_id"),
    )


class Devolucion(Base):
    """Un retracto o una devolucion (FU-04). Referencia al titular por id.

    La supresion del titular no la borra, por la misma razon contable que el
    pedido. El motivo va en texto libre; el estado del reembolso lo lleva el
    `Pago` asociado, no aqui.
    """

    __tablename__ = "devolucion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False
    )
    # Referencia logica a identidad.usuario.
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
