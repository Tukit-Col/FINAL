"""La cola por donde el catalogo crece: candidatos esperando a una persona.

Es la respuesta a una pregunta que el catalogo no podia contestar: que pasa
cuando llega una lista nueva y pide algo que no tenemos. Hoy el renglon
simplemente no encuentra producto y el kit sale incompleto, sin que nadie se
entere de que hubo que buscarlo.

Aserrin de colores, pompones, chaquiras, una biblia de una edicion concreta.
Son cosas que un colegio pide una vez y que no tiene sentido tener curadas de
antemano: el catalogo no se puede escribir entero antes de saber que van a
pedir. Lo que si se puede es que cada lista nueva lo haga crecer.

El ciclo entero es:

    lista nueva -> renglon sin producto -> se busca en las tiendas
                -> PropuestaProducto (aqui) -> la revisa una persona
                -> aprobada: nace el producto canonico con su oferta y precio

Por que una tabla y no cargar los candidatos directamente con puntaje bajo,
que es lo que se hizo la primera vez: porque un candidato rechazado tiene que
poder quedarse rechazado. Sin este registro, la siguiente corrida vuelve a
proponer el mismo lapiz corrector para `punzon`, y la persona que ya dijo que
no tiene que volver a decirlo cada semana. El valor del trabajo humano esta
en que se acumule.

La propuesta guarda tambien `texto_origen`, el renglon literal del colegio
que la disparo. Sin el, quien revisa ve `Lapiz Corrector Punta Fina x3` y no
tiene como saber que el colegio habia pedido un punzon.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Nivel, Texto

_ESTADOS = ("pendiente", "aprobada", "rechazada")


class PropuestaProducto(Base):
    """Un candidato de tienda esperando que alguien diga si sirve."""

    __tablename__ = "propuesta_producto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # El concepto al que responderia. Puede venir vacio: cuando la lista pide
    # algo que el catalogo no tiene ni como concepto, la propuesta llega con
    # `concepto_sugerido` en texto y es la persona quien decide si nace un
    # concepto nuevo o si aquello era un sinonimo de uno que ya existia.
    concepto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), nullable=True
    )
    concepto_sugerido: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # El renglon literal del colegio que disparo la busqueda. Sin el, quien
    # revisa ve el nombre del candidato y no tiene contra que compararlo.
    texto_origen: Mapped[str] = mapped_column(Text, nullable=False)

    # De que revision de que lista salio. No es trazabilidad decorativa: es
    # lo que ata cada propuesta a una version SIN REVISAR, que es la unica
    # situacion en que el catalogo tiene permiso para salir a una tienda.
    # Sin este vinculo, cualquiera podria encolar busquedas contra listas ya
    # cerradas y el gasto no tendria dueño.
    version_lista_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("version_lista_oficial.id", ondelete="CASCADE"), nullable=True
    )
    item_lista_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_lista_oficial.id", ondelete="SET NULL"), nullable=True
    )

    # Como llego el candidato: lo trajo el scraper o lo escribio una persona.
    # Importa para los libros, que casi siempre se dan de alta a mano porque
    # lo que los identifica es el ISBN de una edicion concreta y eso no sale
    # de una busqueda por texto.
    origen: Mapped[str] = mapped_column(String(16), nullable=False, default="scraper")

    # La tienda es obligatoria incluso cuando el alta la escribe una persona.
    # Un producto del que no se sabe quien lo vende no se puede comprar, y un
    # catalogo de cosas que no se pueden comprar no le sirve a nadie. Para un
    # libro dado de alta a mano, el ISBN hace de `referencia_externa`.
    tienda_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tienda.id", ondelete="CASCADE"), nullable=False
    )
    referencia_externa: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    nombre: Mapped[str] = mapped_column(String(512), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ean: Mapped[str | None] = mapped_column(String(14), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    disponible: Mapped[bool] = mapped_column(nullable=False, default=True)

    # La ficha cruda de la tienda, tal como vino. Se guarda entera aunque el
    # catalogo solo use cuatro campos: cuando la persona duda, lo que resuelve
    # la duda suele ser un campo que nadie habia pensado mapear.
    # `Texto` y no `JSONB` a secas: es JSONB en Postgres y JSON en SQLite,
    # que es donde corren las pruebas. Un JSONB crudo aqui no falla al
    # escribirlo sino al crear el esquema, y se lleva por delante el
    # `create_all` de TODO el metadata, asi que el sintoma aparece lejos
    # de la causa: pruebas de tablas que no tienen nada que ver.
    especificaciones: Mapped[dict] = mapped_column(Texto, nullable=False, default=dict)

    nivel_sugerido: Mapped[str | None] = mapped_column(String(16), nullable=True)
    puntaje: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.4)

    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    # Por que se rechazo. Es lo que impide que la siguiente corrida vuelva a
    # proponer lo mismo y que la persona tenga que decir que no dos veces.
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Con que quedo, si se aprobo.
    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("producto_canonico.id", ondelete="SET NULL"), nullable=True
    )

    propuesta_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelta_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        # El mismo articulo de la misma tienda se propone una sola vez. Es lo
        # que hace que rechazar sirva de algo: sin esta llave, cada corrida
        # crearia una fila nueva y la decision anterior no se encontraria.
        UniqueConstraint("tienda_id", "referencia_externa", name="uq_propuesta_referencia"),
        CheckConstraint(
            f"estado IN ({', '.join(repr(e) for e in _ESTADOS)})", name="propuesta_estado_valido"
        ),
        CheckConstraint("origen IN ('scraper', 'manual')", name="propuesta_origen_valido"),
        CheckConstraint(
            f"nivel_sugerido IS NULL OR nivel_sugerido IN ({', '.join(repr(n.value) for n in Nivel)})",
            name="propuesta_nivel_valido",
        ),
        # Una propuesta tiene que decir a que responde, de un modo o del otro.
        CheckConstraint(
            "concepto_id IS NOT NULL OR concepto_sugerido IS NOT NULL",
            name="propuesta_tiene_destino",
        ),
        # Un precio de cero es lo que devuelve la tienda cuando el articulo no
        # se vende en linea, y se propagaria al total del kit como si fuera
        # gratis.
        CheckConstraint("precio_centavos > 0", name="propuesta_precio_positivo"),
        # Aprobada sin producto es una aprobacion que no creo nada.
        CheckConstraint(
            "estado <> 'aprobada' OR producto_canonico_id IS NOT NULL",
            name="propuesta_aprobada_tiene_producto",
        ),
        # La consulta que hace la pantalla de revision: lo pendiente primero y
        # lo mas demandado arriba.
        Index("ix_propuesta_pendiente", "estado", "propuesta_en"),
    )
