"""El trabajo y sus etapas: el estado que hace consultable y reanudable al pipeline.

El recurso central del contrato no es "el kit" sino **el trabajo**, y la razon
es doble. El pipeline tarda minutos (OP-03 pide precision por encima de
velocidad) y ademas el flujo exige una pausa humana antes de que el acudiente
vea nada (AD-03 a AD-06). Nada de eso cabe en una peticion sincronica.

Que el estado viva en la base y no en memoria del proceso es lo que convierte
una promesa en una propiedad. Con el estado en memoria, reiniciar el servicio
pierde todos los trabajos en vuelo y el acudiente se queda esperando un correo
que no va a llegar; con el estado aqui, un trabajo se puede consultar desde
otro proceso, reanudar desde la ultima etapa buena y auditar despues.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, EstadoEtapa, EstadoTrabajo, Texto

_ESTADOS = ", ".join(f"'{e.value}'" for e in EstadoTrabajo)
_ESTADOS_ETAPA = ", ".join(f"'{e.value}'" for e in EstadoEtapa)

# El orden en que el pipeline las recorre. Se declara aqui y no en el
# orquestador porque tambien la usa la lectura: el frontend pinta las cuatro
# desde el primer momento, con las que faltan en `pendiente`, para que la
# espera tenga forma en vez de ser una barra girando.
ETAPAS = ("percepcion", "normalizacion", "resolucion", "optimizacion")


class TrabajoPipeline(Base):
    """Una peticion de kits, por HOGAR y no por hijo.

    La decision de que sea por hogar es lo que hace posible la consolidacion
    entre hermanos y el reparto de empaques: si cada hijo se pidiera aparte,
    el optimizador no podria ver que dos ninos necesitan un borrador cada uno
    y que una caja de diez sale mejor.
    """

    __tablename__ = "trabajo_pipeline"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Quien pidio el kit, y por tanto a quien hay que avisarle. Va por
    # IDENTIFICADOR y no copiando el correo ni el celular: es la misma deuda
    # que el manifiesto documenta en `operacion.notificacion`, donde el
    # servicio anterior persistia el correo real del acudiente y el derecho al
    # olvido no lo alcanzaba. Admite nulo porque el contacto se registra en
    # Identidad y ese servicio puede estar caido; el trabajo no se tumba por
    # eso, se queda sin destinatario y la degradacion se reporta.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    estado: Mapped[str] = mapped_column(String(24), nullable=False, default=EstadoTrabajo.ENCOLADO.value)
    origen: Mapped[str] = mapped_column(String(24), nullable=False, default="colegio_grado")

    # Los hijos con su colegio y su grado, como los mando el acudiente. Es
    # JSON y no una tabla porque no se consulta por ninguno de sus campos: es
    # la entrada del trabajo, se lee entera o no se lee.
    hijos: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    # Cifradas por el puerto de `tukit_comun.cifrado`. Los pesos son datos
    # personales DERIVADOS de la encuesta socioeconomica, que en Identidad ya
    # esta cifrada; dejarlos en claro aqui es exactamente lo que el manifiesto
    # advierte al portar este servicio. El presupuesto del hogar viaja en el
    # mismo bloque y por la misma razon.
    preferencias_cifradas: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    estimado_segundos: Mapped[int] = mapped_column(Integer, nullable=False, default=180)

    # Lo que la seccion 8 del contrato obliga a reportar en vez de esconder.
    degradaciones: Mapped[list[dict[str, Any]]] = mapped_column(Texto, nullable=False, default=list)

    # Los productos que el acudiente cambio en sus kits ya publicados:
    # `{perfil: {item_id: producto}}`, con el producto congelado al elegirlo.
    # Viven aqui y no en `linea_kit` porque esas lineas pueden ser el kit
    # canonico del grado, el que reciben los demas acudientes por la ruta
    # rapida: el cambio de un papa no puede alterar el kit de otro. `ver` los
    # aplica al leer, y el pago lee `ver`.
    cambios: Mapped[dict[str, Any]] = mapped_column(
        Texto, nullable=False, default=dict, server_default=text("'{}'")
    )

    error: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quien de Admin Tukit aprobo o devolvio, y con que nota. AD-25 y AD-26
    # piden que toda transicion quede con quien y cuando; el registro completo
    # va a `operacion.registro_auditoria` por la bandeja de salida, y esto es
    # la copia local que permite responder `GET /v1/admin/trabajos/{id}` sin
    # tener que preguntarle a otro servicio.
    revisado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nota_revision: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"estado IN ({_ESTADOS})", name="trabajo_estado_valido"),
        CheckConstraint(
            "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', "
            "'lista_verificada', 'parent_apply', 'canonico_lista')",
            name="trabajo_origen_valido",
        ),
        CheckConstraint("estimado_segundos > 0", name="trabajo_estimado_positivo"),
        # Un trabajo fallido sin diagnostico es un trabajo que nadie puede
        # atender, y ademas no se puede reintentar a ciegas. Es la misma regla
        # que `catalogo.tarea_importacion`.
        CheckConstraint("estado <> 'fallido' OR error IS NOT NULL", name="trabajo_fallido_tiene_diagnostico"),
        # La cola de Admin, ordenada por antiguedad. Parcial porque la cola es
        # lo unico que se consulta en caliente y el historial crece sin fin.
        Index(
            "ix_trabajo_en_cola",
            "creado_en",
            postgresql_where=text("estado = 'espera_revision'"),
            sqlite_where=text("estado = 'espera_revision'"),
        ),
        Index("ix_trabajo_usuario", "usuario_id", "creado_en"),
    )


class EtapaTrabajo(Base):
    """Una etapa del pipeline, con lo que tardo y como le fue.

    Es lo que responde `etapas` en `GET /v1/trabajos/{id}`, y tambien lo que
    permite reanudar sin volver a pagar la etapa cara: la percepcion llama a
    un modelo por pagina y repetirla porque la resolucion fallo es gasto puro.
    Es la misma razon por la que `catalogo.tarea_importacion` guarda
    `etapa_completada`.
    """

    __tablename__ = "etapa_trabajo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(32), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default=EstadoEtapa.PENDIENTE.value)
    # Milisegundos y entero. El contrato lo expone como `ms` y el perfilado
    # razona en esa unidad; guardarlo en segundos con decimales perderia la
    # diferencia entre 137 microsegundos y 1.673 milisegundos, que es
    # justamente la que motivo cachear el grafo de sustituibilidad.
    ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalle: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    iniciada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("trabajo_id", "nombre", name="uq_etapa_trabajo"),
        CheckConstraint(f"estado IN ({_ESTADOS_ETAPA})", name="etapa_estado_valido"),
        CheckConstraint("ms IS NULL OR ms >= 0", name="etapa_ms_no_negativo"),
        Index("ix_etapa_trabajo", "trabajo_id"),
    )


class BandejaSalida(Base):
    """Bandeja de salida transaccional de Inteligencia.

    Igual que en Identidad y en Catalogo: el evento se escribe en la MISMA
    transaccion que el cambio que lo origina. Aqui el evento que importa es
    `kits_publicados`, que es lo que `operacion` tiene que consumir para
    avisarle al acudiente.

    Hoy **no hay repartidor**, y conviene decirlo aqui y no solo en un informe:
    la mitad transaccional esta y la mitad de entrega no. Es exactamente la
    deuda que el manifiesto documenta del sistema anterior, con la diferencia
    de que esta vez esta anotada donde se va a leer. Mientras no exista, un
    trabajo publicado deja su evento escrito y nadie lo recoge.
    """

    __tablename__ = "bandeja_salida"

    # `BigInteger` en Postgres y `Integer` en SQLite, y la variante no es
    # cosmetica: SQLite solo autoincrementa una columna declarada exactamente
    # `INTEGER PRIMARY KEY`, asi que un `BIGINT` ahi deja de generar valores y
    # el primer insert revienta con "NOT NULL constraint failed". La bandeja
    # crece sin limite en produccion y necesita los 64 bits; las pruebas de
    # dominio corren contra SQLite y necesitan que el insert funcione.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
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


class KitCanonico(Base):
    """El puntero al kit bendito de un (colegio, grado, anio): la cache canonica.

    Publicar un trabajo de onboarding no es solo un estado terminal: deja tres
    kits que una persona validó, y esos son la respuesta reutilizable para todo
    acudiente de ese (colegio, grado). Esta tabla es el puntero —una fila por
    (colegio, grado, anio)— al `trabajo_pipeline` publicado que los tiene. Es un
    puntero y no una copia de los kits: la fuente sigue siendo el trabajo (sus
    KIT/LINEA), y así no hay dos verdades que sincronizar.

    Publicar de nuevo para el mismo grado REEMPLAZA el puntero (upsert por la
    llave única): una sola cache bendita por grado, sin ambigüedad. El trabajo
    apuntado no se puede borrar (guardia en `eliminar`), porque es la cache.
    """

    __tablename__ = "kit_canonico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colegio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    grado: Mapped[str] = mapped_column(String(64), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)

    # El trabajo publicado cuyos kits son la cache. Si ese trabajo se borrara
    # (no puede: la guardia lo impide), la fila se iria con el —el puntero no
    # sobrevive a su fuente—.
    trabajo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajo_pipeline.id", ondelete="CASCADE"), nullable=False
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("colegio_id", "grado", "anio_lectivo", name="uq_kit_canonico_grado"),)


def puede_pasar(actual: str, siguiente: str) -> bool:
    """Si la transicion de estado esta permitida.

    Se consulta antes de escribir para poder devolver `409` con un mensaje
    que diga desde donde y hacia donde, que es lo que el contrato promete para
    "revisar un trabajo ya publicado".
    """
    try:
        desde = EstadoTrabajo(actual)
        hacia = EstadoTrabajo(siguiente)
    except ValueError:
        return False
    from .base import TRANSICIONES

    return hacia in TRANSICIONES[desde]


__all__ = [
    "ETAPAS",
    "BandejaSalida",
    "EtapaTrabajo",
    "KitCanonico",
    "TrabajoPipeline",
    "puede_pasar",
]
