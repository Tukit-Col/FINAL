"""La cola por donde el catalogo crece: candidatos esperando a una persona.

Decisiones:
- El catalogo no se puede escribir entero antes de saber que van a pedir los colegios; cada lista
  nueva lo hace crecer: lista nueva, renglon sin producto, busqueda en tiendas, `PropuestaProducto`,
  revision humana, y si se aprueba nace el producto canonico con su oferta y precio.
- Es una tabla y no una carga con puntaje bajo porque un candidato rechazado tiene que poder
  quedarse rechazado: sin este registro la siguiente corrida lo vuelve a proponer.
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Nivel, Texto

_ESTADOS = ("pendiente", "aprobada", "rechazada")


class PropuestaProducto(Base):
    __tablename__ = "propuesta_producto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    concepto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), nullable=True
    )
    concepto_sugerido: Mapped[str | None] = mapped_column(String(128), nullable=True)

    texto_origen: Mapped[str] = mapped_column(Text, nullable=False)

    version_lista_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("version_lista_oficial.id", ondelete="CASCADE"), nullable=True
    )
    item_lista_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_lista_oficial.id", ondelete="SET NULL"), nullable=True
    )

    origen: Mapped[str] = mapped_column(String(16), nullable=False, default="scraper")

    tienda_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tienda.id", ondelete="CASCADE"), nullable=False
    )
    referencia_externa: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    nombre: Mapped[str] = mapped_column(String(512), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ean: Mapped[str | None] = mapped_column(String(14), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    disponible: Mapped[bool] = mapped_column(nullable=False, default=True)

    especificaciones: Mapped[dict] = mapped_column(Texto, nullable=False, default=dict)

    nivel_sugerido: Mapped[str | None] = mapped_column(String(16), nullable=True)
    puntaje: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.4)

    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("producto_canonico.id", ondelete="SET NULL"), nullable=True
    )

    propuesta_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelta_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tienda_id", "referencia_externa", name="uq_propuesta_referencia"),
        CheckConstraint(
            f"estado IN ({', '.join(repr(e) for e in _ESTADOS)})", name="propuesta_estado_valido"
        ),
        CheckConstraint("origen IN ('scraper', 'manual')", name="propuesta_origen_valido"),
        CheckConstraint(
            f"nivel_sugerido IS NULL OR nivel_sugerido IN ({', '.join(repr(n.value) for n in Nivel)})",
            name="propuesta_nivel_valido",
        ),
        CheckConstraint(
            "concepto_id IS NOT NULL OR concepto_sugerido IS NOT NULL",
            name="propuesta_tiene_destino",
        ),
        CheckConstraint("precio_centavos > 0", name="propuesta_precio_positivo"),
        CheckConstraint(
            "estado <> 'aprobada' OR producto_canonico_id IS NOT NULL",
            name="propuesta_aprobada_tiene_producto",
        ),
        Index("ix_propuesta_pendiente", "estado", "propuesta_en"),
    )
