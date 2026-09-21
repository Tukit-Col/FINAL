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
    ForeignKey,
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


class Direccion(Base):
    """Libreta de direcciones del acudiente.

    No existia NINGUNA direccion de entrega en todo el sistema anterior, en un
    negocio que entrega a domicilio. Tampoco estaba en el esquema objetivo, asi
    que el hueco se arrastraba del modelo al diseno.

    Vive en Identidad y no en Comercio porque es dato personal de una familia
    con menores, y la supresion tiene que alcanzarla. Pero la direccion a la
    que SE ENTREGO un pedido no es esta fila: es una copia congelada en el
    envio, en Comercio. Si el envio apuntara aqui con una llave foranea,
    corregir un numero de apartamento reescribiria el historial de entregas y
    dejaria sin sustento cualquier reclamo. Es el mismo razonamiento por el
    que el precio se congela en la linea del pedido. Ver ADR 0015.

    La division de columnas es minimizacion, no capricho. Repartir una ruta
    necesita saber la zona, no el apartamento: `ciudad` y `localidad` quedan en
    claro porque de ellas depende la asignacion de zona, y la parte que
    identifica el hogar va cifrada.
    """

    __tablename__ = "direccion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    etiqueta: Mapped[str] = mapped_column(String(64), nullable=False, default="casa")

    ciudad: Mapped[str] = mapped_column(String(128), nullable=False)
    localidad: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Calle, numero, apartamento y punto de referencia. Cifrado en la
    # aplicacion: es lo que localiza fisicamente a un hogar con menores.
    linea_cifrada: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Telefono de contacto para la entrega, tambien cifrado.
    contacto_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    predeterminada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Baja logica y no borrado: un envio en curso sigue necesitando que la
    # direccion exista mientras se entrega.
    archivada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_direccion_predeterminada",
            "usuario_id",
            unique=True,
            postgresql_where=text("predeterminada AND archivada_en IS NULL"),
            sqlite_where=text("predeterminada AND archivada_en IS NULL"),
        ),
        Index("ix_direccion_usuario", "usuario_id", "archivada_en"),
    )

    @property
    def activa(self) -> bool:
        return self.archivada_en is None


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
