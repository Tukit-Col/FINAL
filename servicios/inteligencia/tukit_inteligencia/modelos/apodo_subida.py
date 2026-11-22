from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ApodoSubida(Base):
    __tablename__ = "apodo_subida"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    referencia: Mapped[str] = mapped_column(String(64), nullable=False)
    contacto_referencia: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    apodo_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
