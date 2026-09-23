"""Los tres kits y sus lineas. Lo que el acudiente ve.

Un kit es un punto del frente de Pareto, no una consulta distinta: los tres
salen de la misma corrida con ponderaciones distintas, y por eso comparten
trabajo y se diferencian por `perfil`.

La linea es la tabla que reemplaza al JSON `kits_optimizados.items` del
sistema anterior. Ese JSON escondia una referencia a producto que para
Postgres era texto, y escondia tambien el error de unidades: no distinguia
cuantas cosas pidio el colegio de cuantos paquetes hay que comprar, y de ahi
salia sumar doce cajas cuando la lista pedia doce lapices. Aqui son tres
columnas distintas y la aritmetica es visible.
"""

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
    """Un kit completo para un perfil.

    `pesos_usados_cifrados` es la columna que el manifiesto senala al portar
    este servicio: los pesos son derivados de la encuesta socioeconomica, que
    en Identidad esta cifrada, y aqui vivian en claro. Peor aun, el proceso de
    derecho al olvido documentaba la decision de NO borrar el kit alegando que
    "no tiene ninguna columna con datos personales", lo cual es cierto para
    las columnas que su autor tenia en mente y falso para esta.
    """

    __tablename__ = "kit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )
    # Un kit es para un estudiante en un grado y un anio, no para una cuenta.
    # Cruza a `identidad.matricula` y esta declarado. Nulo mientras el hogar
    # todavia no tenga matricula formal.
    matricula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    perfil: Mapped[str] = mapped_column(String(16), nullable=False)

    # El total incluye SOLO las lineas con `informativa = false`. Prometer lo
    # que no se puede entregar es el modo de falla mas caro del negocio, y
    # FU-06 congela el precio al confirmar: una linea que Tukit no controla no
    # puede entrar al total.
    total_cop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Los tres ejes del frente: costo, fidelidad a lo que pidio el colegio y
    # disponibilidad. Van en JSON porque son la salida del optimizador y se
    # leen juntos; ninguna consulta filtra por uno solo.
    objetivos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    recomendado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    razon_recomendacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dentro_de_presupuesto: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    pesos_usados_cifrados: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Lo que se ahorro juntando la demanda de dos hermanos. Es la razon de que
    # el trabajo sea por hogar y no por hijo, asi que se guarda explicada y no
    # solo como un numero: "una caja de diez sale mas barata que dos
    # borradores sueltos" es lo que el acudiente necesita leer.
    consolidaciones: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("trabajo_id", "perfil", name="uq_kit_trabajo_perfil"),
        CheckConstraint(f"perfil IN ({_PERFILES})", name="kit_perfil_valido"),
        CheckConstraint("total_cop >= 0", name="kit_total_no_negativo"),
        Index("ix_kit_trabajo", "trabajo_id"),
    )


class LineaKit(Base):
    """Un renglon del kit, con la aritmetica de unidades a la vista.

    Tres numeros que el sistema anterior colapsaba en uno:

      `cantidad_pedida`      cuantas cosas pide el colegio, en unidad base
      `unidades_por_empaque` de a cuantas viene el producto elegido
      `unidades_a_comprar`   techo(pedida / por_empaque)

    Separarlos es lo que impide volver a sumar doce cajas cuando la lista
    pedia doce lapices, y es tambien lo que permite explicarle al acudiente
    por que su carrito dice "1" donde la lista decia "12".
    """

    __tablename__ = "linea_kit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("kit.id", ondelete="CASCADE"), nullable=False
    )
    item_crudo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("item_crudo.id", ondelete="CASCADE"), nullable=False
    )
    # Reemplaza el `producto_id` que vivia dentro del JSON de items y que para
    # Postgres era texto. Referencia logica a Catalogo, declarada en el
    # manifiesto. Nulo en las lineas que no son un producto: una licencia
    # digital, un "el disponible en casa" o un hueco de catalogo.
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

    # Se muestra, no se cobra. La linea aparece en el kit con la instruccion
    # textual del colegio y queda fuera del carrito, del total y del conteo de
    # cobertura. Se muestra en vez de ocultarse porque el acudiente necesita
    # saber que esos items existen y como conseguirlos: una lista incompleta
    # reproduce el dolor que vino a evitar, aunque el carrito se vea limpio.
    informativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    instruccion_colegio: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_externa: Mapped[str | None] = mapped_column(Text, nullable=True)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)

    # La regla inversa de la consolidacion: los borradores se juntan y los
    # textos nunca, porque dos ediciones del mismo titulo no son sustituibles.
    # Se guarda el motivo y no solo la bandera, para que el kit lo explique.
    no_consolidable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    motivo_no_consolidable: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hasta dos productos mas del mismo concepto, en otros niveles. Van en
    # JSON porque son para pintar, no para consultar: nadie busca kits por su
    # segunda alternativa.
    alternativas: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)
    sustitutos: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("kit_id", "hijo_referencia", "orden", name="uq_linea_kit_orden"),
        CheckConstraint(f"estado_resolucion IN ({_ESTADOS})", name="linea_estado_valido"),
        CheckConstraint("cantidad_pedida >= 0", name="linea_cantidad_no_negativa"),
        CheckConstraint("unidades_a_comprar >= 0", name="linea_unidades_no_negativas"),
        CheckConstraint("unidades_por_empaque > 0", name="linea_empaque_positivo"),
        # Una linea informativa no lleva precio NI subtotal. La restriccion
        # esta en la base y no solo en el codigo porque es la que sostiene la
        # promesa de que el total no incluye lo que Tukit no puede entregar.
        CheckConstraint(
            "NOT informativa OR (precio_unitario_cop IS NULL AND subtotal_cop IS NULL)",
            name="linea_informativa_sin_precio",
        ),
        Index("ix_linea_kit", "kit_id", "hijo_referencia", "orden"),
    )
