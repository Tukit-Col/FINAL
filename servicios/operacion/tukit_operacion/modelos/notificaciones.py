"""Notificaciones y preferencias. Por identificador, NUNCA copiando el contacto.

La deuda que este modelo evita esta documentada en el manifiesto: el servicio
anterior persistia el correo REAL del acudiente dentro del contenido de la
notificacion, y el proceso de derecho al olvido no lo borraba. Aqui la
notificacion referencia al destinatario por `usuario_id` y su contenido no
repite el dato de contacto. El correo o el celular se resuelven contra
Identidad EN EL MOMENTO de enviar, por el repartidor, y no se guardan.

Por eso este archivo no tiene ninguna columna `correo` ni `celular`, y la
prueba lo comprueba buscando que no aparezcan.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class Notificacion(Base):
    """Un aviso a un usuario. Contenido por plantilla + datos, sin dato de contacto.

    `canal` es `wa_link` o `correo`. `estado` sigue el envio (pendiente,
    enviada, fallida). `datos` lleva las variables de la plantilla (por ejemplo
    el turno o el numero de pedido), nunca el correo ni el celular.
    """

    __tablename__ = "notificacion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # El destinatario, por identificador. Referencia logica a identidad.usuario.
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    canal: Mapped[str] = mapped_column(String(16), nullable=False, default="correo")
    plantilla: Mapped[str] = mapped_column(String(64), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_notificacion_usuario", "usuario_id"),
        Index("ix_notificacion_estado", "estado"),
    )


class PreferenciaNotificacion(Base):
    """Que canales acepta un usuario. Una fila por usuario."""

    __tablename__ = "preferencia_notificacion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Referencia logica a identidad.usuario.
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    acepta_correo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    acepta_wa_link: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_preferencia_usuario", "usuario_id"),)
