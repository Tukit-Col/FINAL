from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoResolucion, PerfilKit, Texto

_PERFILES = ", ".join(f"'{p.value}'" for p in PerfilKit)
_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoResolucion)


class Kit(Base):
    __tablename__ = "kit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )
    matricula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    perfil: Mapped[str] = mapped_column(String(16), nullable=False)

    total_cop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    objetivos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    recomendado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    razon_recomendacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dentro_de_presupuesto: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    pesos_usados_cifrados: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    consolidaciones: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("trabajo_id", "perfil", name="uq_kit_trabajo_perfil"),
        CheckConstraint(f"perfil IN ({_PERFILES})", name="kit_perfil_valido"),
        CheckConstraint("total_cop >= 0", name="kit_total_no_negativo"),
        Index("ix_kit_trabajo", "trabajo_id"),
    )


class LineaKit(Base):
    __tablename__ = "linea_kit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("kit.id", ondelete="CASCADE"), nullable=False
    )
    item_crudo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_crudo.id", ondelete="CASCADE"), nullable=False
    )
    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    hijo_referencia: Mapped[str] = mapped_column(String(64), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)

    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(24), nullable=False, default="util")
    estado_resolucion: Mapped[str] = mapped_column(String(24), nullable=False)

    cantidad_pedida: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default="unidad")
    unidades_por_empaque: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unidades_a_comprar: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nombre_producto: Mapped[str | None] = mapped_column(String(512), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nivel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    personaje: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confianza: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    precio_unitario_cop: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subtotal_cop: Mapped[int | None] = mapped_column(Integer, nullable=True)

    informativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    instruccion_colegio: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_externa: Mapped[str | None] = mapped_column(Text, nullable=True)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)

    no_consolidable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    motivo_no_consolidable: Mapped[str | None] = mapped_column(Text, nullable=True)

    alternativas: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)
    sustitutos: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("kit_id", "hijo_referencia", "orden", name="uq_linea_kit_orden"),
        CheckConstraint(f"estado_resolucion IN ({_ESTADOS})", name="linea_estado_valido"),
        CheckConstraint("cantidad_pedida >= 0", name="linea_cantidad_no_negativa"),
        CheckConstraint("unidades_a_comprar >= 0", name="linea_unidades_no_negativas"),
        CheckConstraint("unidades_por_empaque > 0", name="linea_empaque_positivo"),
        CheckConstraint(
            "NOT informativa OR (precio_unitario_cop IS NULL AND subtotal_cop IS NULL)",
            name="linea_informativa_sin_precio",
        ),
        Index("ix_linea_kit", "kit_id", "hijo_referencia", "orden"),
    )
