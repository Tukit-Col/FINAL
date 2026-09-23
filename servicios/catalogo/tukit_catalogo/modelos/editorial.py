"""Ediciones de texto escolar y el ciclo de aprobacion entre editorial y colegio.

Por que esto entra en v1 y no en v2. El lienzo de valor de colegios dejo ver
un encaje invertido: los tres dolores mejor documentados del colegio no tenian
aliviador, y el modulo que si los atenderia estaba diferido. Los tres son:

  1. La ventana de tres dias entre que la editorial publica y que el colegio
     tiene que decidir.
  2. Evaluar textos le cuesta al colegio mas trabajo que toda la papeleria
     junta, y la papeleria era lo unico que el producto atendia.
  3. La oferta editorial no cubre el Bachillerato Internacional, que es justo
     donde el colegio tiene menos alternativas.

El esquema nunca difirio esto: las cuatro tablas ya estaban en las 17 de
Catalogo. Lo diferido era la funcionalidad. Lo que se trae a v1 es el minimo
que ataca los tres: representar la edicion vigente por colegio y curso, recibir
propuestas de cambio con su ventana explicita, y dejar que el colegio fije su
politica de una vez en vez de decidir cada temporada bajo presion.
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
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EdicionLibro(Base):
    """Una edicion concreta de un texto escolar.

    Un texto no es un producto de papeleria con otro nombre: su identidad es
    la edicion, y dos ediciones del mismo titulo NO son sustituibles aunque
    compartan ISBN de obra, porque cambian la paginacion y los ejercicios. Esa
    es la razon de que el texto tenga tabla propia en vez de ser un producto
    canonico con un atributo.
    """

    __tablename__ = "edicion_libro"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isbn13: Mapped[str] = mapped_column(String(13), nullable=False, unique=True)
    titulo: Mapped[str] = mapped_column(String(512), nullable=False)
    editorial: Mapped[str] = mapped_column(String(256), nullable=False)
    anio_edicion: Mapped[int] = mapped_column(Integer, nullable=False)
    numero_edicion: Mapped[str | None] = mapped_column(String(32), nullable=True)

    area: Mapped[str] = mapped_column(String(64), nullable=False)
    grado_sugerido: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Marca explicita del programa. Existe porque la cobertura de
    # Bachillerato Internacional es uno de los tres dolores documentados: sin
    # esta columna el sistema no puede siquiera REPORTAR que no cubre algo, y
    # una carencia que no se puede nombrar no se puede cerrar.
    programa: Mapped[str] = mapped_column(String(32), nullable=False, default="nacional")

    # Un texto se reemplaza; no se agota. Cuando la editorial descontinua una
    # edicion, el colegio necesita saberlo ANTES de la ventana de decision.
    descontinuada_en: Mapped[date | None] = mapped_column(Date, nullable=True)
    reemplazada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="SET NULL"), nullable=True
    )

    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("producto_canonico.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "programa IN ('nacional', 'bachillerato_internacional', 'cambridge', 'otro')",
            name="edicion_programa_valido",
        ),
        CheckConstraint("anio_edicion >= 1980", name="edicion_anio_plausible"),
        CheckConstraint(
            "reemplazada_por_id IS NULL OR reemplazada_por_id <> id",
            name="edicion_no_se_reemplaza_a_si_misma",
        ),
        Index("ix_edicion_area_programa", "area", "programa"),
    )


class ConfiguracionColegioEditorial(Base):
    """La politica del colegio frente a los cambios de edicion.

    Esta tabla es el aliviador directo del dolor de la ventana de tres dias.
    La idea es invertir el momento de la decision: en vez de que el colegio
    decida bajo presion cada vez que llega una propuesta, fija una vez su
    regla y el sistema aplica esa regla automaticamente, dejando para revision
    humana solo lo que la regla no cubre.
    """

    __tablename__ = "configuracion_colegio_editorial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Cruza a identidad.colegio. Declarada en el manifiesto.
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)

    # Cuantos dias necesita el colegio para decidir. El valor por omision no
    # es un numero redondo elegido al azar: son los tres dias observados,
    # explicitados para que el sistema pueda avisar cuando NO se cumplen.
    dias_ventana_decision: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Que hacer cuando nadie responde dentro de la ventana. Que el silencio
    # signifique "conservar la edicion vigente" y no "aceptar la nueva" es una
    # decision de negocio y no un detalle: el colegio que no alcanzo a
    # revisar no queda comprometido con un cambio que no evaluo.
    politica_silencio: Mapped[str] = mapped_column(String(32), nullable=False, default="conservar_vigente")
    exige_aprobacion_humana: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    programa_predeterminado: Mapped[str] = mapped_column(String(32), nullable=False, default="nacional")
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("dias_ventana_decision > 0", name="config_ventana_positiva"),
        CheckConstraint(
            "politica_silencio IN ('conservar_vigente', 'aceptar_propuesta', 'escalar')",
            name="config_politica_silencio_valida",
        ),
    )


class VersionVigente(Base):
    """Que edicion usa hoy un colegio para un area y un grado.

    Es la respuesta a la pregunta que el colegio hace todos los anios y que
    hoy vive en un correo: cual pedimos este ano.
    """

    __tablename__ = "version_vigente"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    edicion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="RESTRICT"), nullable=False
    )
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    # Historico y no sobreescritura, por la misma razon que en el resto del
    # sistema: saber que edicion se uso en 2025 es lo que permite explicarle a
    # un acudiente por que el libro de su hijo mayor no le sirve al menor.
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="version_vigencia_coherente"
        ),
        Index(
            "uq_version_vigente_actual",
            "colegio_id",
            "area",
            "grado",
            "anio_lectivo",
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
            sqlite_where=text("vigente_hasta IS NULL"),
        ),
    )


class PropuestaVersion(Base):
    """Una editorial propone cambiar la edicion de un colegio.

    El aliviador del segundo dolor, que evaluar textos cueste mas que toda la
    papeleria. La propuesta llega estructurada y con la comparacion hecha, en
    vez de como un catalogo en PDF que alguien tiene que leer entero.
    """

    __tablename__ = "propuesta_version"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    edicion_propuesta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="CASCADE"), nullable=False
    )
    edicion_actual_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("edicion_libro.id", ondelete="SET NULL"), nullable=True
    )
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    delta_precio_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estado: Mapped[str] = mapped_column(String(24), nullable=False, default="pendiente")
    recibida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Se calcula al recibir, a partir de la ventana configurada por el
    # colegio. Materializarla en columna en vez de derivarla al vuelo permite
    # consultar "que se me vence manana" con un indice, que es la consulta que
    # hace util toda esta tabla.
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelta_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'aceptada', 'rechazada', 'vencida')", name="propuesta_estado_valido"
        ),
        CheckConstraint("vence_en > recibida_en", name="propuesta_ventana_coherente"),
        # Una propuesta resuelta necesita saber quien la resolvio, salvo que
        # se haya vencido, que es el unico desenlace sin persona detras.
        CheckConstraint(
            "(estado IN ('pendiente', 'vencida')) OR (resuelta_en IS NOT NULL AND resuelta_por IS NOT NULL)",
            name="propuesta_resuelta_tiene_responsable",
        ),
        CheckConstraint(
            "edicion_actual_id IS NULL OR edicion_actual_id <> edicion_propuesta_id",
            name="propuesta_cambia_de_edicion",
        ),
        Index(
            "ix_propuesta_por_vencer",
            "vence_en",
            postgresql_where=text("estado = 'pendiente'"),
            sqlite_where=text("estado = 'pendiente'"),
        ),
        UniqueConstraint(
            "colegio_id",
            "area",
            "grado",
            "anio_lectivo",
            "edicion_propuesta_id",
            name="uq_propuesta_sin_duplicar",
        ),
    )
