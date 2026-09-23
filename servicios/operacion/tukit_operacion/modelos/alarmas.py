"""Alarmas: un caso que se acerca a su vencimiento o lo paso.

Una alarma es una senal derivada de un caso, para que la bandeja pueda subir
lo que corre riesgo de incumplir el termino sin recalcular contra el reloj en
cada render. La dispara el barrido de vencimientos; se apaga cuando el caso se
resuelve.
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


class Alarma(Base):
    __tablename__ = "alarma"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("caso.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(32), nullable=False, default="vencimiento")
    dispara_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_alarma_caso", "caso_id", "activa"),)
