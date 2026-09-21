"""Listas oficiales de utiles publicadas por el colegio, y su importacion.

Vienen de MS-Instituciones, que se disuelve. La tenencia se va a Identidad y
la lista oficial se queda aqui, porque una lista de utiles es vocabulario de
catalogo y no un hecho institucional: lo que el colegio pide son conceptos.

Un defecto que se corrige al traerlas: el servicio anterior guardaba el texto
crudo de la lista SIN redactar los nombres de menores, pese a que el mismo
sistema ya tenia la funcion de redaccion y la aplicaba en la vista previa. La
columna que persiste el texto aqui es `contenido_redactado`, y el nombre no es
decorativo.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

from .base import Base, Texto


class ListaOficial(Base):
    """La lista de utiles de un colegio para un grado y un ano lectivo."""

    __tablename__ = "lista_oficial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sede_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    grado: Mapped[str] = mapped_column(String(32), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("colegio_id", "sede_id", "grado", "anio_lectivo", name="uq_lista_oficial"),
        Index("ix_lista_colegio", "colegio_id", "anio_lectivo"),
    )


class VersionListaOficial(Base):
    """Cada publicacion de una lista. Versionada, no sobreescrita.

    El colegio corrige su lista despues de publicarla, y un acudiente que ya
    compro necesita saber contra que version compro. Sobreescribir hace que
    esa pregunta no tenga respuesta.
    """

    __tablename__ = "version_lista_oficial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lista_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lista_oficial.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)

    # Redactado en la PERSISTENCIA, no solo en la vista previa. Esa
    # distincion es la diferencia entre cumplir la promesa que el texto de
    # autorizacion le hace al acudiente y solo aparentarlo en pantalla.
    contenido_redactado: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_origen: Mapped[str | None] = mapped_column(String(64), nullable=True)

    publicada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("lista_id", "numero", name="uq_version_lista_numero"),
        CheckConstraint("numero > 0", name="version_numero_positivo"),
        Index(
            "uq_version_lista_vigente",
            "lista_id",
            unique=True,
            postgresql_where=text("vigente"),
            sqlite_where=text("vigente")),
    )


class ItemListaOficial(Base):
    """Un renglon de la lista, ya resuelto a concepto.

    `concepto_id` admite nulo a proposito: un renglon que el sistema no supo
    normalizar debe quedar visible como no resuelto en vez de desaparecer o
    de forzarse al concepto mas parecido. El corpus tiene 3.610 renglones y la
    cobertura de conceptos no es total.
    """

    __tablename__ = "item_lista_oficial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("version_lista_oficial.id", ondelete="CASCADE"),
        nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_original: Mapped[str] = mapped_column(Text, nullable=False)

    concepto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="SET NULL"), nullable=True
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unidad: Mapped[str | None] = mapped_column(String(32), nullable=True)
    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    confianza_normalizacion: Mapped[float | None] = mapped_column(nullable=True)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("version_id", "orden", name="uq_item_version_orden"),
        CheckConstraint("cantidad > 0", name="item_cantidad_positiva"),
        Index("ix_item_concepto", "concepto_id"),
        # Un renglon sin concepto SIEMPRE requiere revision. Sin esta regla,
        # un renglon que nadie resolvio puede quedarse callado y salir del
        # kit sin que nadie se entere.
        CheckConstraint(
            "concepto_id IS NOT NULL OR requiere_revision",
            name="item_sin_concepto_va_a_revision"),
    )


class TareaImportacion(Base):
    """El estado de una importacion de lista, por etapas reanudables.

    Existe por la misma razon que el pipeline deja de ser sincronico: una
    importacion que falla en la etapa de normalizacion no debe volver a pagar
    la percepcion, que es la etapa cara.
    """

    __tablename__ = "tarea_importacion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lista_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lista_oficial.id", ondelete="SET NULL"), nullable=True
    )
    origen: Mapped[str] = mapped_column(String(32), nullable=False)
    estado: Mapped[str] = mapped_column(String(24), nullable=False, default="pendiente")
    etapa_actual: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Ultima etapa buena: el punto desde el que se reanuda.
    etapa_completada: Mapped[str | None] = mapped_column(String(32), nullable=True)

    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    caso_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'en_curso', 'completada', 'fallida', 'requiere_revision')",
            name="tarea_estado_valido"),
        CheckConstraint("intentos >= 0", name="tarea_intentos_no_negativos"),
        # Una tarea fallida sin diagnostico es una tarea que nadie puede
        # atender. Se exige o el mensaje o el Caso abierto.
        CheckConstraint(
            "estado <> 'fallida' OR error IS NOT NULL OR caso_id IS NOT NULL",
            name="tarea_fallida_tiene_diagnostico"),
        Index("ix_tarea_pendiente", "estado", "actualizada_en"),
    )


class BandejaSalida(Base):
    """Bandeja de salida transaccional de Catalogo.

    Igual que en Identidad: el evento se escribe en la MISMA transaccion que
    el cambio que lo origina, y un repartidor aparte lo publica. Lo que el
    sistema anterior tenia era solo la mitad de escritura; el repartidor no
    existia pese a que la documentacion decia lo contrario.
    """

    __tablename__ = "bandeja_salida"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(128), nullable=False)
    agregado_tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    agregado_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    carga: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index(
            "ix_bandeja_salida_pendiente",
            "creado_en",
            postgresql_where=text("publicado_en IS NULL"),
            sqlite_where=text("publicado_en IS NULL")),
    )
