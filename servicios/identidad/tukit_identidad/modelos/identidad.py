"""Usuario y la bandeja de salida local."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correo: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    clave_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    nombre_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Lo que arregla la revocacion de sesion. Hoy la cadena `jti` solo existe
    # en MS-Cuentas: `deps.py` valida firma, tipo y expiracion y nada mas, asi
    # que inhabilitar una cuenta no surte efecto en los otros seis servicios
    # hasta que el token expire, y el de un acudiente dura 30 dias.
    #
    # Con esto, el token lleva la version con la que se emitio y cualquier
    # servicio la compara contra la vigente. Revocar es incrementar el numero:
    # no requiere que los demas servicios consulten una lista de revocacion en
    # cada peticion, que es lo que haria inviable el control.
    version_permisos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    anonimizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BandejaSalida(Base):
    """Bandeja de salida local. Una por base, y eso es deliberado.

    El evento se escribe en la MISMA transaccion que el cambio que lo origina.
    Si viviera en otra base, volveria a ser una escritura a dos sistemas sin
    garantia, que es exactamente el problema que el patron resuelve.

    OJO con la deuda que se hereda: en `Tukit-Auditoria`, `registrar_evento`
    solo hacia `session.add` y NO existia ningun repartidor que publicara,
    pese a que el docstring decia "outbox real". La mitad transaccional estaba
    bien y la mitad de entrega no existia. El repartidor va en `libs/` y tiene
    que estar andando antes de que los Casos se apoyen en esto.
    """

    __tablename__ = "bandeja_salida"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tipo_evento: Mapped[str] = mapped_column(String(128), nullable=False)
    clave_agregado: Mapped[str] = mapped_column(String(128), nullable=False)
    carga: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        # El repartidor solo mira lo no publicado; el indice parcial evita que
        # el barrido crezca con el historial.
        Index(
            "ix_bandeja_pendiente",
            "creado_en",
            postgresql_where=text("publicado_en IS NULL"),
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )
