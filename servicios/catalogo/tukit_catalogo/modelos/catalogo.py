from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import Base, Embedding, ListaTexto, Nivel, Texto, TipoItem, UnidadBase

_NIVELES = ", ".join(f"'{n.value}'" for n in Nivel)
_TIPOS_ITEM = ", ".join(f"'{t.value}'" for t in TipoItem)
_UNIDADES_BASE = ", ".join(f"'{u.value}'" for u in UnidadBase)


class Concepto(Base):
    __tablename__ = "concepto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nombre_canonico: Mapped[str] = mapped_column(String(256), nullable=False)

    sinonimos: Mapped[list[str]] = mapped_column(ListaTexto, nullable=False, default=list)

    categoria: Mapped[str] = mapped_column(String(64), nullable=False)

    tipo_item: Mapped[str] = mapped_column(String(24), nullable=False, default=TipoItem.UTIL.value)

    atributos_discriminantes: Mapped[list[str]] = mapped_column(ListaTexto, nullable=False, default=list)
    atributos_descriptivos: Mapped[list[str]] = mapped_column(ListaTexto, nullable=False, default=list)

    @validates("atributos_discriminantes", "atributos_descriptivos")
    def _sin_solapamiento(self, campo: str, valor: list[str] | None) -> list[str] | None:
        if valor:
            otro = (
                "atributos_descriptivos"
                if campo == "atributos_discriminantes"
                else "atributos_discriminantes"
            )
            repetidos = set(valor) & set(getattr(self, otro, None) or ())
            if repetidos:
                raise ValueError(
                    f"{', '.join(sorted(repetidos))} no puede estar en {campo} y en {otro} a la vez"
                )
        return valor

    admite_personaje: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    uno_por_estudiante: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    frecuencia_demanda: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("frecuencia_demanda >= 0", name="concepto_demanda_no_negativa"),
        CheckConstraint(f"tipo_item IN ({_TIPOS_ITEM})", name="concepto_tipo_item_valido"),
        Index("ix_concepto_categoria", "categoria"),
    )


class GrupoVariante(Base):
    __tablename__ = "grupo_variante"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    representante_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "producto_canonico.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_grupo_variante_representante",
        ),
        nullable=True,
    )
    criterio: Mapped[str] = mapped_column(String(32), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("criterio IN ('ean', 'nombre_normalizado', 'manual')", name="grupo_criterio_valido"),
    )


class ProductoCanonico(Base):
    __tablename__ = "producto_canonico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concepto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="RESTRICT"), nullable=False
    )

    ean: Mapped[str | None] = mapped_column(String(14), nullable=True, unique=True)
    sku_interno: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    nombre: Mapped[str] = mapped_column(String(512), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)

    nivel: Mapped[str] = mapped_column(String(16), nullable=False, default=Nivel.CONFIABLE.value)
    personaje: Mapped[str | None] = mapped_column(String(64), nullable=True)

    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default=UnidadBase.UNIDAD.value)
    unidades_por_empaque: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    ruta_categoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    es_propio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    grupo_variante_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupo_variante.id", ondelete="SET NULL"), nullable=True
    )
    es_representante_canonico: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    embedding: Mapped[list[float] | None] = mapped_column(Embedding, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    texto_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    quality_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.700)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    curado_por: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    curado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"nivel IN ({_NIVELES})", name="producto_nivel_valido"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 1", name="producto_calidad_en_rango"),
        CheckConstraint(f"unidad_base IN ({_UNIDADES_BASE})", name="producto_unidad_base_valida"),
        CheckConstraint("unidades_por_empaque > 0", name="producto_empaque_positivo"),
        Index("ix_producto_concepto", "concepto_id", postgresql_where=text("activo")),
        Index("ix_producto_nivel", "concepto_id", "nivel"),
        Index("ix_producto_grupo", "grupo_variante_id"),
    )


class ConceptoRutaCategoria(Base):
    __tablename__ = "concepto_ruta_categoria"

    concepto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), primary_key=True
    )
    tienda_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tienda.id", ondelete="CASCADE"), primary_key=True
    )
    ruta: Mapped[str] = mapped_column(String(512), primary_key=True)
    es_hoja: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SustituibilidadConcepto(Base):
    __tablename__ = "sustituibilidad_concepto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    concepto_origen_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), nullable=False
    )
    concepto_sustituto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), nullable=False
    )

    grado: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)

    motivo: Mapped[str] = mapped_column(Text, nullable=False)

    curado_por: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    curado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("concepto_origen_id", "concepto_sustituto_id", name="uq_sustituibilidad_par"),
        CheckConstraint("concepto_origen_id <> concepto_sustituto_id", name="sustituibilidad_no_reflexiva"),
        CheckConstraint("grado > 0 AND grado <= 1", name="sustituibilidad_grado_en_rango"),
        Index("ix_sustituibilidad_origen", "concepto_origen_id", "grado"),
    )


event.listen(
    Concepto.__table__,
    "after_create",
    DDL(
        "ALTER TABLE concepto ADD CONSTRAINT concepto_atributos_sin_solapar "
        "CHECK (NOT (atributos_discriminantes && atributos_descriptivos))"
    ).execute_if(dialect="postgresql"),
)
