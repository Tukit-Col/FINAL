from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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

from .base import MODOS_SURTIBLES, Base, ModoAdquisicion, Texto, TipoItem, UnidadBase
from .catalogo import Concepto

_TIPOS_ITEM = ", ".join(f"'{t.value}'" for t in TipoItem)
_UNIDADES_BASE = ", ".join(f"'{u.value}'" for u in UnidadBase)
_MODOS = ", ".join(f"'{m.value}'" for m in ModoAdquisicion)
_MODOS_SURTIBLES = ", ".join(f"'{m.value}'" for m in sorted(MODOS_SURTIBLES))


class ListaOficial(Base):

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

    __tablename__ = "version_lista_oficial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lista_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lista_oficial.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)

    contenido_redactado: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_origen: Mapped[str | None] = mapped_column(String(64), nullable=True)

    publicada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    publicada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    revisada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revisada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("lista_id", "numero", name="uq_version_lista_numero"),
        CheckConstraint("numero > 0", name="version_numero_positivo"),
        Index(
            "uq_version_lista_vigente",
            "lista_id",
            unique=True,
            postgresql_where=text("vigente"),
            sqlite_where=text("vigente"),
        ),
    )


class ItemListaOficial(Base):

    __tablename__ = "item_lista_oficial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("version_lista_oficial.id", ondelete="CASCADE"), nullable=False
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_original: Mapped[str] = mapped_column(Text, nullable=False)

    concepto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="SET NULL"), nullable=True
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    unidad: Mapped[str | None] = mapped_column(String(16), nullable=True)

    tipo_item: Mapped[str | None] = mapped_column(String(24), nullable=True)

    modo_adquisicion: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ModoAdquisicion.MERCADO_ABIERTO.value
    )

    instruccion_colegio: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_externa: Mapped[str | None] = mapped_column(Text, nullable=True)

    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    confianza_normalizacion: Mapped[float | None] = mapped_column(nullable=True)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    avisos_descartados: Mapped[list[str]] = mapped_column(
        Texto, nullable=False, default=list, server_default=text("'[]'")
    )

    def tipo_efectivo(self, concepto: Concepto | None) -> str | None:
        if self.tipo_item is not None:
            return self.tipo_item
        return concepto.tipo_item if concepto is not None else None

    @property
    def surtible(self) -> bool:
        return self.modo_adquisicion in MODOS_SURTIBLES

    __table_args__ = (
        UniqueConstraint("version_id", "orden", name="uq_item_version_orden"),
        CheckConstraint("cantidad > 0", name="item_cantidad_positiva"),
        Index("ix_item_concepto", "concepto_id"),
        CheckConstraint(f"tipo_item IS NULL OR tipo_item IN ({_TIPOS_ITEM})", name="item_tipo_item_valido"),
        CheckConstraint(f"unidad IS NULL OR unidad IN ({_UNIDADES_BASE})", name="item_unidad_valida"),
        CheckConstraint(f"modo_adquisicion IN ({_MODOS})", name="item_modo_adquisicion_valido"),
        CheckConstraint(
            f"modo_adquisicion IN ({_MODOS_SURTIBLES}) OR instruccion_colegio IS NOT NULL",
            name="item_no_surtible_explica_como_conseguirlo",
        ),
        CheckConstraint(
            "concepto_id IS NOT NULL OR requiere_revision", name="item_sin_concepto_va_a_revision"
        ),
    )


class TareaImportacion(Base):

    __tablename__ = "tarea_importacion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lista_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lista_oficial.id", ondelete="SET NULL"), nullable=True
    )
    origen: Mapped[str] = mapped_column(String(32), nullable=False)
    estado: Mapped[str] = mapped_column(String(24), nullable=False, default="pendiente")
    etapa_actual: Mapped[str | None] = mapped_column(String(32), nullable=True)
    etapa_completada: Mapped[str | None] = mapped_column(String(32), nullable=True)

    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    documento: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    percepcion_cruda: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("version_lista_oficial.id", ondelete="SET NULL"), nullable=True
    )
    colegio_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    grado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    anio_lectivo: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    contacto_referencia: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    preferencias: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    colegio_datos: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    referencias: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    clave_idempotencia: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    retirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'en_curso', 'completada', 'fallida', 'requiere_revision')",
            name="tarea_estado_valido",
        ),
        CheckConstraint("intentos >= 0", name="tarea_intentos_no_negativos"),
        CheckConstraint("estado <> 'fallida' OR error IS NOT NULL", name="tarea_fallida_tiene_diagnostico"),
        Index("ix_tarea_pendiente", "estado", "actualizada_en"),
        Index("uq_tarea_clave_idempotencia", "clave_idempotencia", unique=True),
    )


class BandejaSalida(Base):

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
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )


class CorreccionLista(Base):

    __tablename__ = "correccion_lista"
    __table_args__ = (
        Index("ix_correccion_lista_version", "version_id"),
        Index("ix_correccion_lista_creado", "creado_en"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    campo: Mapped[str] = mapped_column(String(24), nullable=False)
    valor_antes: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    valor_despues: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    texto_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    aprendido: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    actor: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
