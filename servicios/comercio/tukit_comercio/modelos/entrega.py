"""Zonas, rutas y el envio con la direccion congelada (ADR 0015).

El envio guarda una COPIA congelada de la direccion, no una llave foranea a
`identidad.direccion`. Si apuntara alla, corregir un numero de apartamento
reescribiria el historial de entregas y dejaria sin sustento cualquier
reclamo. Es el mismo razonamiento del precio congelado. La libreta (dato
personal de una familia con menores) vive en Identidad y la supresion la
alcanza; la direccion a la que SE ENTREGO vive aqui, en claro, porque es un
hecho logistico ya ocurrido y no un dato de contacto reutilizable.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ZonaEntrega(Base):
    """Una zona de reparto: una ciudad y (opcional) una localidad.

    La asignacion de ruta necesita la zona, no el apartamento. Por eso la
    direccion de Identidad guarda `ciudad`/`localidad` en claro: de ellas
    depende esta asignacion.
    """

    __tablename__ = "zona_entrega"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(128), nullable=False)
    localidad: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_zona_ciudad", "ciudad"),)


class RutaReparto(Base):
    """Una ruta de un dia en una zona: el agrupamiento por el que salen los envios."""

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
    """El envio de un pedido, con la direccion congelada al despachar (ADR 0015).

    Uno a uno con el pedido. La direccion va en claro y en texto plano porque
    es la copia del hecho de entrega, decoplada de la libreta de Identidad. Los
    campos de seguimiento (`transportadora`, `guia`, fechas) coinciden uno a
    uno con el tipo `Envio` del contrato de lectura.
    """

    __tablename__ = "envio"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Copia congelada. Nada de esto apunta a identidad.direccion.
    destinatario: Mapped[str] = mapped_column(String(256), nullable=False)
    direccion: Mapped[str] = mapped_column(String(512), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(128), nullable=False)

    # Mas de la copia congelada del hecho de entrega. Nullable porque el
    # checkout legado (solo destinatario/direccion/ciudad) tiene que seguir
    # cerrando y las filas ya escritas no los tienen; el formulario nuevo si los
    # exige. Como el resto del envio, es copia y no llave a Identidad (ADR 0015).
    telefono: Mapped[str | None] = mapped_column(String(32), nullable=True)
    departamento: Mapped[str | None] = mapped_column(String(128), nullable=True)
    documento_destinatario: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indicaciones: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # La localidad de Bogota (nombre canonico, vacia fuera de Bogota) y el lugar
    # de Google Places que eligio el acudiente, para el enlace a Maps del
    # back-office. Nunca coordenadas: los terminos de Google no dejan guardarlas
    # (ADR 0039). Nullable por lo mismo que los de arriba.
    localidad: Mapped[str | None] = mapped_column(String(64), nullable=True)
    google_place_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    zona_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("zona_entrega.id", ondelete="SET NULL"), nullable=True
    )
    ruta_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ruta_reparto.id", ondelete="SET NULL"), nullable=True
    )

    transportadora: Mapped[str | None] = mapped_column(String(128), nullable=True)
    guia: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Reparto propio: el repartidor no tiene cuenta, es un dato que pone el
    # operador al despachar. `transportadora`/`guia` quedan para los envios
    # viejos. El celular es dato personal de un tercero: solo lo ve el staff.
    repartidor_nombre: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repartidor_celular: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entrega_estimada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entregado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_envio_pedido", "pedido_id"),)
