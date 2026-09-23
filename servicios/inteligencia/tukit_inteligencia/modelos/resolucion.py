"""Del renglon crudo a la decision, con los candidatos que la sostienen.

Las cuatro tablas de aqui son el rastro de por que se eligio un producto y no
otro. El sistema anterior guardaba el resultado en un JSON llamado
`kits_optimizados.items` con `producto_id` adentro, de modo que para Postgres
era texto: no habia forma de saber que candidatos se consideraron, ni con que
puntaje, ni quien decidio cuando decidio una persona.

Guardar los candidatos cuesta filas y vale la pena por dos usos concretos. La
cola de Admin necesita mostrar las opciones para que alguien elija (AD-04), y
cuando el emparejamiento se equivoca hay que poder mirar que vio el sistema:
pedir `punzon punta metalica` devuelve correctores de punta fina, y eso solo
se diagnostica viendo los candidatos, no el ganador.
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
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoResolucion, Texto

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoResolucion)


class ItemCrudo(Base):
    """Un renglon de la lista tal como entro, ya parseado a demanda.

    Es la frontera entre lo que el colegio escribio y lo que el sistema
    entendio, y se guarda entera porque es lo unico que permite responder
    "el kit dice esto porque la lista decia aquello".

    `cantidad` puede ser cero y no es un error: "el disponible en casa" es
    una instruccion de no comprar, y cero es el numero honesto. `None` no
    serviria, porque habria que distinguirlo de "no supe leerlo".
    """

    __tablename__ = "item_crudo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )

    # Ancla de tenencia. Se valida contra Identidad al crear, no por llave
    # foranea: la matricula vive en otra base. Admite nulo porque el acudiente
    # puede pedir kits antes de que exista una matricula formal, que es el
    # caso de quien sube la lista sin estar registrado en el colegio.
    matricula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    # La referencia que el acudiente le puso a cada hijo ("hijo-1"). No es un
    # identificador de nadie: es lo que permite devolver las lineas agrupadas
    # sin que el frontend tenga que conocer a los menores.
    hijo_referencia: Mapped[str] = mapped_column(String(64), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)

    texto: Mapped[str] = mapped_column(Text, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default="unidad")
    unidades_por_empaque: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tipo_item: Mapped[str] = mapped_column(String(24), nullable=False, default="util")
    modo_adquisicion: Mapped[str] = mapped_column(String(32), nullable=False, default="mercado_abierto")

    instruccion_colegio: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_externa: Mapped[str | None] = mapped_column(Text, nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Confianza de EXTRACCION, no de emparejamiento. Es la que dispara PE-04:
    # por debajo del umbral configurable, el renglon va a revision de Admin
    # aunque el catalogo le haya encontrado producto. Son dos dudas distintas
    # y mezclarlas hace que una lectura borrosa pase por un match seguro.
    confianza_extraccion: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("trabajo_id", "hijo_referencia", "orden", name="uq_item_crudo_orden"),
        CheckConstraint("cantidad >= 0", name="item_crudo_cantidad_no_negativa"),
        CheckConstraint(
            "unidades_por_empaque IS NULL OR unidades_por_empaque > 0",
            name="item_crudo_empaque_positivo",
        ),
        Index("ix_item_crudo_trabajo", "trabajo_id", "hijo_referencia", "orden"),
    )


class CandidatoItem(Base):
    """Un producto que el catalogo ofrecio para un renglon.

    Los campos del producto se COPIAN en vez de leerse por la referencia, y
    eso no es desnormalizar por comodidad: el producto vive en otra base y
    este servicio no puede consultarla (invariante 3). Leerlos exigiria una
    llamada HTTP por candidato al pintar la cola de Admin.

    Ademas la copia es lo correcto en el tiempo: `precio_cop` es el precio que
    se vio cuando se armo el kit, y eso es lo que hay que poder mostrar
    despues aunque la tienda lo haya cambiado. El precio que de verdad se
    cobra se vuelve a leer antes de confirmar la orden (UI-05, SC-05).
    """

    __tablename__ = "candidato_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_crudo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_crudo.id", ondelete="CASCADE"), nullable=False
    )
    # El catalogo vive en otra base; la referencia es logica y esta declarada
    # en el manifiesto. Admite nulo porque un candidato puede venir de una
    # fuente que todavia no tiene producto canonico dado de alta.
    producto_canonico_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre: Mapped[str] = mapped_column(String(512), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nivel: Mapped[str] = mapped_column(String(16), nullable=False)
    personaje: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default="unidad")
    unidades_por_empaque: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    # Pesos enteros, no centavos y no flotante. Es la unidad del contrato y
    # la del cliente; convertir una sola vez, en el borde, evita que cada
    # consumidor tenga que acordarse de dividir. Nulo es "no se conoce".
    precio_cop: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confianza: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.000)
    cumple_atributos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("item_crudo_id", "sku", name="uq_candidato_item_sku"),
        CheckConstraint("confianza >= 0 AND confianza <= 1", name="candidato_confianza_en_rango"),
        CheckConstraint("precio_cop IS NULL OR precio_cop >= 0", name="candidato_precio_no_negativo"),
        CheckConstraint("unidades_por_empaque > 0", name="candidato_empaque_positivo"),
        Index("ix_candidato_item", "item_crudo_id", "orden"),
    )


class ResolucionItem(Base):
    """La decision sobre un renglon: que estado quedo y con que producto.

    `concepto_codigo` guarda el CODIGO (`C003`) y no el identificador del
    concepto, a diferencia de `producto_canonico_id` en la tabla de arriba.
    La asimetria es deliberada: el codigo es el nombre publico y estable con
    el que el catalogo se refiere a sus conceptos, viaja en su API y se puede
    leer en un volcado sin cruzar bases. El identificador del producto si hace
    falta porque es con lo que Comercio arma la linea del pedido.
    """

    __tablename__ = "resolucion_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_crudo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_crudo.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    estado: Mapped[str] = mapped_column(String(24), nullable=False)
    concepto_codigo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    concepto_nombre: Mapped[str | None] = mapped_column(String(256), nullable=True)
    parecido: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.000)

    candidato_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidato_item.id", ondelete="SET NULL"), nullable=True
    )

    # Los atributos que el renglon IMPUSO, que es distinto de los que
    # describe. Se guardan porque son la explicacion de una abstencion: "pides
    # block tamano oficio y ninguno de los 5 productos lo declara".
    atributos_impuestos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nulo mientras la decision sea automatica. En cuanto una persona valida o
    # marca sin coincidencia (AD-04), aqui queda quien fue. Cruza a
    # `identidad.usuario` y esta declarado en el manifiesto.
    decidido_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    decidido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="resolucion_estado_valido"),
        CheckConstraint("parecido >= 0 AND parecido <= 1", name="resolucion_parecido_en_rango"),
        # Un estado resuelto sin producto elegido es una contradiccion que
        # aguas abajo se convierte en una linea de kit sin nada que comprar.
        CheckConstraint(
            "estado <> 'RESUELTO_AUTO' OR candidato_item_id IS NOT NULL",
            name="resolucion_resuelta_tiene_candidato",
        ),
        Index("ix_resolucion_estado", "estado"),
    )


class TransicionResolucion(Base):
    """El historial de una resolucion: quien la cambio, cuando y por que.

    Es lo que convierte la cola de Admin en un control con dueno en vez de en
    una pantalla. AD-25 y AD-26 piden que toda transicion quede registrada, y
    sin esta tabla "el sistema dijo X y ahora dice Y" no tiene explicacion.
    """

    __tablename__ = "transicion_resolucion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resolucion_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resolucion_item.id", ondelete="CASCADE"), nullable=False
    )
    estado_anterior: Mapped[str | None] = mapped_column(String(24), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(24), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nulo cuando la transicion la hizo el pipeline. Que se pueda distinguir
    # de una decision humana es el punto entero de la tabla.
    decidida_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    ocurrida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"estado_nuevo IN ({_ESTADOS})", name="transicion_estado_nuevo_valido"),
        CheckConstraint(
            f"estado_anterior IS NULL OR estado_anterior IN ({_ESTADOS})",
            name="transicion_estado_anterior_valido",
        ),
        Index("ix_transicion_resolucion", "resolucion_item_id", "ocurrida_en"),
    )
