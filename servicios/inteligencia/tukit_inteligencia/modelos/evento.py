from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EventoProcesado(Base):

    __tablename__ = "evento_procesado"

    origen: Mapped[str] = mapped_column(String(32), primary_key=True)
    evento_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
