"""El apodo de un hijo cuya lista subida espera aprobacion (Ley 1581).

La subida de un PDF va al Catalogo, que NO guarda datos de menores. El apodo con
el que el acudiente rotula el kit se queda aqui, cifrado y ligado a la version
importada, hasta que el poller arma el kit al aprobarse la lista y lo copia al
trabajo. Entonces se borra. La supresion del titular lo borra tambien.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ApodoSubida(Base):
    __tablename__ = "apodo_subida"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # La version que el Catalogo creo para esa lista: es el `agregado_id` de
    # `lista_verificada`, la llave con que el poller la encuentra.
    version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    referencia: Mapped[str] = mapped_column(String(64), nullable=False)
    # El usuario_id opaco del acudiente, para la supresion.
    contacto_referencia: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    apodo_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
