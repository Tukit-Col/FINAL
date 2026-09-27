"""Tenencia: la matricula como ancla, y el estudiante como entidad propia.

Tukit es B2B2C y no crece por trafico sino por inquilinos: crece agregando
colegios. El modelo anterior no reflejaba eso. `institucion_id` aparecia cero
veces en MS-Comercio y en MS-Cuentas, asi que los pedidos y los usuarios no
sabian a que colegio pertenecian, y en MS-Busqueda existia pero lo mandaba el
cliente en el cuerpo sin validar, que es peor que no tenerlo.

La solucion obvia, `colegio_id` en el usuario, es incorrecta: un acudiente
puede tener hijos en colegios distintos. La tenencia no esta en la persona,
esta en la matricula.

Ver ADR 0013.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoMatricula

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoMatricula)


class Colegio(Base):
    __tablename__ = "colegio"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    nit: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # El perfil institucional que el padre reconoce en la tarjeta de partner y
    # que el administrador completa. Son datos de la INSTITUCION, no del menor:
    # no les toca el cifrado del Anexo M que sí protege al estudiante en este
    # mismo modelo, así que viajan en claro por la superficie pública. Todos
    # nulables: los colegios sembrados nacen sin perfil y se completa después.
    # `Text`, no `String(n)`: el logo puede llegar como URL corta o como data-URI
    # (`data:image/...;base64,...`) que el revisor pega/sube, y eso desborda
    # cualquier limite razonable. Es dato institucional publico, sin PII.
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitio_web: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contacto_nombre: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contacto_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contacto_telefono: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(512), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Sede(Base):
    __tablename__ = "sede"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colegio.id", ondelete="RESTRICT"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_sede_colegio", "colegio_id"),)


class Estudiante(Base):
    """La primera vez que el sistema tiene una entidad para el menor de edad.

    Las cinco columnas son `menor` sin excepcion, incluida `creado_en`. Una
    marca de tiempo de sistema normalmente seria `interno`, pero aqui no: la
    existencia de la fila ya declara que hay un menor cuyo dato se trata, asi
    que cualquier atributo suyo singulariza a ese menor.
    """

    __tablename__ = "estudiante"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Cifrado en la aplicacion, no solo en reposo. El texto de autorizacion que
    # firma el acudiente promete que Tukit no guarda el nombre de su hijo en
    # claro, y esa promesa se cumple aqui o no se cumple.
    nombre_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Huella y no el documento: sirve para detectar que dos acudientes
    # matricularon al mismo estudiante, y no sirve para nada mas.
    documento_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_estudiante_documento",
            "documento_hash",
            unique=True,
            postgresql_where=text("documento_hash IS NOT NULL"),
            sqlite_where=text("documento_hash IS NOT NULL"),
        ),
    )


class Matricula(Base):
    """Estudiante x sede x grado x anio lectivo. El ancla de tenencia.

    Su identificador viaja a los otros cuatro servicios como referencia
    logica, y es lo que permite responder "de que colegio es este pedido" sin
    reconstruir la relacion a mano en cada consulta.
    """

    __tablename__ = "matricula"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estudiante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("estudiante.id", ondelete="RESTRICT"), nullable=False
    )
    sede_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sede.id", ondelete="RESTRICT"), nullable=False
    )
    # Desnormalizado a proposito: se deduce de `sede`, pero sin el, resolver el
    # ambito de colegio de cada matricula exige una union en el camino caliente
    # de toda verificacion de permiso.
    colegio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("colegio.id", ondelete="RESTRICT"), nullable=False
    )
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default=EstadoMatricula.ACTIVA.value)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Sin esta columna la politica de retencion del Anexo M no es ejecutable:
    # dice que a los doce meses del cierre se destruye la llave de la
    # matricula, y no habria desde donde contar los doce meses.
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("estudiante_id", "sede_id", "grado", "anio_lectivo", name="matricula_unica"),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="matricula_estado_valido"),
        CheckConstraint("anio_lectivo BETWEEN 2020 AND 2100", name="matricula_anio_plausible"),
        CheckConstraint("(estado = 'activa') = (cerrado_en IS NULL)", name="matricula_cierre_coherente"),
        Index("ix_matricula_sede", "sede_id"),
        Index("ix_matricula_colegio", "colegio_id"),
    )


class AcudienteMatricula(Base):
    """Vinculo N:M entre acudientes y matriculas, con historial.

    Las dos direcciones importan: un estudiante puede tener madre, padre y un
    tercer acudiente autorizado, y un acudiente puede tener hijos en colegios
    distintos. La segunda es la que invalida poner `colegio_id` en el usuario.

    `vigente_hasta` es lo que permite distinguir "se fue" de "nunca estuvo",
    que es lo que necesita la regla de supresion del Anexo M: suprimir a un
    acudiente elimina SU vinculo, y solo dispara la destruccion de la llave de
    la matricula cuando desaparece el ultimo acudiente vinculado. Sin esa
    distincion, suprimir a un padre le borra los datos al otro.
    """

    __tablename__ = "acudiente_matricula"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True
    )
    matricula_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("matricula.id", ondelete="CASCADE"), primary_key=True
    )
    parentesco: Mapped[str] = mapped_column(String(32), nullable=False, default="acudiente")
    es_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Como el acudiente llama a su hijo. Ley 1581 / Anexo M: el sistema nunca
    # guarda el nombre del menor en claro; el padre lo refiere por un apodo, y
    # hasta el apodo va cifrado porque singulariza al menor. Nulable: los
    # vinculos sembrados por prueba pueden no tenerlo.
    apodo_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="acudiente_vigencia_coherente"
        ),
        Index(
            "uq_matricula_principal",
            "matricula_id",
            unique=True,
            postgresql_where=text("es_principal AND vigente_hasta IS NULL"),
            sqlite_where=text("es_principal AND vigente_hasta IS NULL"),
        ),
        Index("ix_acudiente_matricula_usuario", "usuario_id", "vigente_hasta"),
    )

    @property
    def vigente(self) -> bool:
        return self.vigente_hasta is None
