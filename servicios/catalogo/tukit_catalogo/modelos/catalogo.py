"""Las tres capas del catalogo: concepto, producto canonico y agrupacion.

La capa de concepto es la que faltaba. El sistema anterior normalizaba el
texto de la lista escolar directamente contra productos de tienda, de modo que
"cuaderno cuadriculado 100 hojas" competia contra referencias comerciales
concretas y la variabilidad terminologica colombiana no tenia donde vivir.

Aqui el concepto es la necesidad abstracta que el colegio pide, el producto
canonico es la cosa identificable independiente de quien la venda, y la oferta
de tienda (en `oferta.py`) es quien la vende y a que precio.
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Embedding, ListaTexto, Nivel, Texto

_NIVELES = ", ".join(f"'{n.value}'" for n in Nivel)


class Concepto(Base):
    """La necesidad abstracta que el colegio pide.

    99 conceptos derivados de las 3.610 lineas del corpus de 17 colegios, de
    los cuales 25 cubren el 81 % de los renglones de una lista tipica.
    """

    __tablename__ = "concepto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nombre_canonico: Mapped[str] = mapped_column(String(256), nullable=False)

    # La columna que hace ejecutable el requisito de variabilidad
    # terminologica colombiana: `esfero` = `boligrafo`, `marcadores` =
    # `plumones`. Ese diccionario de equivalencias no tenia donde vivir.
    sinonimos: Mapped[list[str]] = mapped_column(ListaTexto, nullable=False, default=list)

    categoria: Mapped[str] = mapped_column(String(64), nullable=False)
    atributos_requeridos: Mapped[list[str]] = mapped_column(
        ListaTexto, nullable=False, default=list
    )
    admite_personaje: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # `interno` y no `publico`: es una agregacion sobre las listas de 17
    # colegios concretos, o sea que revela que pide el mercado atendido.
    frecuencia_demanda: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("frecuencia_demanda >= 0", name="concepto_demanda_no_negativa"),
        Index("ix_concepto_categoria", "categoria"),
    )


class GrupoVariante(Base):
    """Agrupa productos casi identicos para elegir uno por omision.

    La propiedad que hay que conservar del comportamiento anterior es que
    agrupar NUNCA borra ni oculta nada del catalogo ni de la busqueda: solo
    cambia cual candidato se ofrece primero. Por eso `representante_id` admite
    nulo y por eso el grupo no tiene bandera de activo.
    """

    __tablename__ = "grupo_variante"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    representante_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("producto_canonico.id", ondelete="SET NULL"),
        nullable=True)
    criterio: Mapped[str] = mapped_column(String(32), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "criterio IN ('ean', 'nombre_normalizado', 'manual')",
            name="grupo_criterio_valido"),
    )


class ProductoCanonico(Base):
    """El producto identificable, independiente de quien lo venda.

    Unifica las dos tablas `productos_catalogo` que vivian en servicios
    distintos. Conviene enunciar bien el defecto que esta fusion resuelve,
    porque de como se enuncie depende la direccion de la migracion: no habia
    "dos maestros vivos" sino UN maestro en Comercio con una replica con
    perdida declarada, MAS un segundo escritor no coordinado en Busqueda. Se
    promueve la copia de Busqueda, que es la que tiene los embeddings y las
    puntuaciones, y se retira la de Comercio, que es la que tenia el stock.

    Cinco columnas de las tablas anteriores NO sobreviven, y esa es la parte
    importante: `precio`, `stock`, `proveedor`, `disponible` y `url_producto`
    son propiedades de la relacion entre un producto y una tienda, no del
    producto. Sacarlas es una correccion de tercera forma normal.
    """

    __tablename__ = "producto_canonico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concepto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="RESTRICT"), nullable=False
    )

    # Nula cuando la fuente no la trae, que es el caso normal y no la
    # excepcion: el mayorista no publica ninguno.
    ean: Mapped[str | None] = mapped_column(String(14), nullable=True, unique=True)
    sku_interno: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    nombre: Mapped[str] = mapped_column(String(512), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)

    nivel: Mapped[str] = mapped_column(String(16), nullable=False, default=Nivel.CONFIABLE.value)
    # Variante con personaje, para la experiencia de personalizacion del nino.
    # Solo tiene sentido si el concepto lo admite.
    personaje: Mapped[str | None] = mapped_column(String(64), nullable=True)

    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    ruta_categoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    es_propio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    grupo_variante_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupo_variante.id", ondelete="SET NULL"), nullable=True
    )
    es_representante_canonico: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # La columna que hace de esta la tabla hibrida: atributos relacionales y
    # representacion vectorial en la misma fila, con indice HNSW.
    embedding: Mapped[list[float] | None] = mapped_column(Embedding, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    texto_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    quality_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.700)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # La regla del catalogo curado: un producto que nadie curo no existe. Por
    # eso no admite nulo, aunque cruce a otro servicio.
    curado_por: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    curado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"nivel IN ({_NIVELES})", name="producto_nivel_valido"),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="producto_calidad_en_rango"),
        Index("ix_producto_concepto", "concepto_id", postgresql_where=text("activo")),
        Index("ix_producto_nivel", "concepto_id", "nivel"),
        Index("ix_producto_grupo", "grupo_variante_id"),
    )


class ConceptoRutaCategoria(Base):
    """Ruta de categoria de un concepto en la taxonomia de una tienda.

    Es N:M porque un mismo concepto vive en rutas distintas en tiendas
    distintas, y esa es justo la traduccion que hay que hacer para raspar.
    """

    __tablename__ = "concepto_ruta_categoria"

    concepto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), primary_key=True
    )
    tienda_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tienda.id", ondelete="CASCADE"), primary_key=True
    )
    ruta: Mapped[str] = mapped_column(String(512), primary_key=True)
    es_hoja: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("concepto_id", "tienda_id", "ruta", name="uq_concepto_ruta"),
    )
