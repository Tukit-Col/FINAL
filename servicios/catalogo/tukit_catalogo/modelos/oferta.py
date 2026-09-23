"""Quien vende cada producto y a que precio publico observado.

Esta capa es la que el modelo anterior no tenia separada, y su ausencia
producia el peor efecto del esquema viejo: `precio`, `stock`, `proveedor` y
`url` eran columnas del producto, de modo que un producto solo podia tener un
precio y un vendedor. Comparar precio entre tiendas, que es el nucleo de la
propuesta de valor, era literalmente inexpresable.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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

from .base import UMBRAL_REVISION_MANUAL, Base, FuentePrecio, MetodoVinculacion

_METODOS = ", ".join(f"'{m.value}'" for m in MetodoVinculacion)
_FUENTES = ", ".join(f"'{f.value}'" for f in FuentePrecio)


class Tienda(Base):
    """Quien vende. Reemplaza la columna `proveedor` de texto libre, cuyo
    valor por omision era la cadena `"manual"`."""

    __tablename__ = "tienda"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(256), nullable=False)
    tipo: Mapped[str] = mapped_column(String(32), nullable=False, default="minorista")
    url_base: Mapped[str | None] = mapped_column(Text, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('minorista', 'mayorista', 'editorial', 'propia')", name="tienda_tipo_valido"
        ),
    )


class CorridaScraper(Base):
    """Una ejecucion de la ingesta. Da procedencia a cada precio observado.

    El perfilado encontro que la semilla del catalogo anterior NO era
    reproducible: 1.164 de 7.475 URL no tenian origen en ningun fichero
    versionado y el script generador no estaba en el repositorio. Esta tabla
    existe para que eso no vuelva a pasar: todo precio apunta a la corrida que
    lo vio.
    """

    __tablename__ = "corrida_scraper"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tienda_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tienda.id", ondelete="CASCADE"), nullable=False
    )
    iniciada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    terminada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="en_curso")
    productos_vistos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('en_curso', 'completada', 'fallida', 'parcial')", name="corrida_estado_valido"
        ),
        Index("ix_corrida_tienda", "tienda_id", "iniciada_en"),
    )


class OfertaTienda(Base):
    """Que una tienda concreta ofrece un producto concreto."""

    __tablename__ = "oferta_tienda"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_canonico_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("producto_canonico.id", ondelete="CASCADE"), nullable=False
    )
    tienda_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tienda.id", ondelete="CASCADE"), nullable=False
    )
    referencia_externa: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    metodo_vinculacion: Mapped[str] = mapped_column(String(16), nullable=False)
    confianza_vinculacion: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1.000)

    # De TRES valores a proposito. `None` significa "no se", no "no hay".
    # La fuente mayorista no reporta stock, y forzar `False` haria que el
    # optimizador descarte ofertas legitimas por una observacion que nunca se
    # hizo. Un booleano que admite nulo y se lee como si/no/no-se es la
    # representacion honesta de una observacion que puede faltar.
    disponible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Apaga un mapeo puntual sin borrar el registro curado.
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    visto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("producto_canonico_id", "tienda_id", name="uq_oferta_producto_tienda"),
        UniqueConstraint("tienda_id", "referencia_externa", name="uq_oferta_referencia"),
        CheckConstraint(f"metodo_vinculacion IN ({_METODOS})", name="oferta_metodo_valido"),
        CheckConstraint(
            "confianza_vinculacion >= 0 AND confianza_vinculacion <= 1", name="oferta_confianza_en_rango"
        ),
        # Cola de revision manual. Vincular por atributos no es un caso
        # degradado: es el camino normal del canal mayorista, donde el EAN
        # valido es del 0,00 %. Este indice es el que hace operativa la
        # revision en vez de dejarla como intencion.
        Index(
            "ix_oferta_revision_manual",
            "confianza_vinculacion",
            postgresql_where=text(
                f"metodo_vinculacion = 'atributos' AND confianza_vinculacion < {UMBRAL_REVISION_MANUAL}"
            ),
            sqlite_where=text(
                f"metodo_vinculacion = 'atributos' AND confianza_vinculacion < {UMBRAL_REVISION_MANUAL}"
            ),
        ),
        Index("ix_oferta_producto", "producto_canonico_id", postgresql_where=text("activo")),
    )

    @property
    def requiere_revision(self) -> bool:
        return (
            self.metodo_vinculacion == MetodoVinculacion.ATRIBUTOS.value
            and float(self.confianza_vinculacion) < UMBRAL_REVISION_MANUAL
        )


class PrecioOferta(Base):
    """Un tramo de precio con vigencia, no una columna que se sobreescribe.

    El precio publico observado y el costo contractual que un mayorista le
    cobra a Tukit NO son el mismo dato y no se unifican: viven en servicios
    distintos porque estan en lados opuestos de la asimetria de recuperacion.
    Este se reconstruye raspando; el otro no se puede perder.
    """

    __tablename__ = "precio_oferta"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oferta_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("oferta_tienda.id", ondelete="CASCADE"), nullable=False
    )
    # En centavos y entero: un precio en punto flotante acumula error al
    # sumarse sobre los 30 o 40 renglones de un kit.
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="COP")
    fuente: Mapped[str] = mapped_column(String(16), nullable=False)

    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    corrida_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("corrida_scraper.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("valor_centavos >= 0", name="precio_no_negativo"),
        CheckConstraint("moneda IN ('COP')", name="precio_moneda_valida"),
        CheckConstraint(f"fuente IN ({_FUENTES})", name="precio_fuente_valida"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="precio_vigencia_coherente"
        ),
        # En Postgres esto va acompanado de una restriccion de exclusion sobre
        # el rango temporal, que es lo que impide dos precios solapados para
        # la misma oferta. SQLAlchemy no la expresa de forma portable, asi que
        # vive en la migracion:
        #   EXCLUDE USING gist (oferta_id WITH =,
        #                       tstzrange(vigente_desde, vigente_hasta) WITH &&)
        # Sin ella, "el precio de hoy" es una consulta ambigua, que es
        # exactamente lo que les pasaba a las dos tablas de precio anteriores.
        Index(
            "uq_precio_vigente_por_oferta",
            "oferta_id",
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
            sqlite_where=text("vigente_hasta IS NULL"),
        ),
        Index("ix_precio_oferta_historial", "oferta_id", "vigente_desde"),
    )

    @property
    def vigente(self) -> bool:
        return self.vigente_hasta is None
