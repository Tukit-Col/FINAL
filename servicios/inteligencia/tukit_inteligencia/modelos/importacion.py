"""La lista que un acudiente subio y que todavia no llego al catalogo (ADR 0040).

`POST /v1/listas/subir` percibe el PDF de cada hijo y lo importa al catalogo.
Antes las dos cosas vivian solo dentro de la peticion: con el catalogo caido el
acudiente recibia un 500 y lo percibido se perdia, aunque la percepcion es la
etapa cara (un modelo por pagina). Ahora la subida deja aqui, en la misma
transaccion y antes de llamar al catalogo, lo que el catalogo necesita para
importar; si el catalogo no responde, la fila queda `pendiente` y el trabajador
la reintenta cuando vuelve, sin volver a percibir.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Texto


class ImportacionLista(Base):
    """Una importacion por subida y destino (colegio, grado, anio).

    Dos hijos del mismo destino comparten una fila, como comparten una
    version. La `clave_idempotencia` viaja al catalogo con cada intento: es lo
    que hace que dos reintentos, o un reintento despues de una respuesta que se
    perdio, den una sola version.
    """

    __tablename__ = "importacion_lista"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Una por peticion: agrupa los destinos de un mismo hogar.
    subida_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    clave_idempotencia: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # Las referencias de los hijos que apuntan a este destino, en orden.
    referencias: Mapped[list[str]] = mapped_column(Texto, nullable=False, default=list)
    # El `usuario_id` de Identidad, nunca el correo ni el telefono: es lo que
    # deja ver la pendiente en "Mis solicitudes".
    contacto_referencia: Mapped[str | None] = mapped_column(String(64), nullable=True)
    colegio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(64), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    # Lo percibido y lo que viaja con ello: `items`, `percepcion_cruda`,
    # `preferencias`, `colegio_datos` y `origen`. Con `documento`, el PDF, es
    # todo lo que pide `importar_lista`. Las dos se vacian al importar: desde
    # ahi la copia buena es la del catalogo.
    carga: Mapped[dict[str, Any] | None] = mapped_column(Texto, nullable=True)
    documento: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Desde cuando el trabajador puede tomarla. La subida la reserva mientras
    # la intenta, y cada caida la corre con espera exponencial.
    proximo_intento_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("clave_idempotencia", name="uq_importacion_clave"),
        CheckConstraint("estado IN ('pendiente', 'importada', 'fallida')", name="importacion_estado_valido"),
        # Igual que `trabajo_pipeline`: una fallida sin diagnostico no la
        # puede atender nadie.
        CheckConstraint(
            "estado <> 'fallida' OR error IS NOT NULL", name="importacion_fallida_tiene_diagnostico"
        ),
        # Lo que el trabajador busca en cada vuelta. Parcial porque las
        # importadas crecen sin fin y nadie las vuelve a tomar.
        Index(
            "ix_importacion_pendiente",
            "proximo_intento_en",
            postgresql_where=text("estado = 'pendiente'"),
            sqlite_where=text("estado = 'pendiente'"),
        ),
        Index("ix_importacion_contacto", "contacto_referencia", "creado_en"),
    )
