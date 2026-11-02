"""Bandeja de salida transaccional de Comercio.

El evento se escribe en la MISMA transaccion que el cambio que lo origina: un
`pedido_pagado` se inserta aqui dentro de la misma transaccion en la que el
webhook transiciona el pedido a `pagado`. Si viviera en otra base, volveria a
ser una escritura a dos sistemas sin garantia, que es el problema que el patron
resuelve.

La convencion de columnas es la de Inteligencia (`tipo, agregado_tipo,
agregado_id, carga, ...`), la misma que Identidad adopto en el ADR 0048,
a proposito: el repartidor de Operacion lee las bandejas de Inteligencia y de
Comercio con un solo parser. Dos formas obligarian a dos.

Hoy la mitad de entrega (el repartidor) es lo que Operacion aporta. Mientras
esta bandeja solo se escribe, un pedido pagado deja su evento y nadie lo
recoge; con el repartidor andando, ese evento se vuelve un aviso al acudiente.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class BandejaSalida(Base):
    __tablename__ = "bandeja_salida"

    # `BigInteger` en Postgres, `Integer` en SQLite: SQLite solo autoincrementa
    # una columna declarada exactamente `INTEGER PRIMARY KEY`. La bandeja crece
    # sin limite en produccion y necesita 64 bits; las pruebas corren en SQLite
    # y necesitan que el insert genere el id.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tipo: Mapped[str] = mapped_column(String(128), nullable=False)
    agregado_tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    agregado_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    carga: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        Index(
            "ix_bandeja_salida_pendiente",
            "creado_en",
            postgresql_where=text("publicado_en IS NULL"),
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )
