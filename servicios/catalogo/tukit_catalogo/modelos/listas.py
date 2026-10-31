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

    # Cuando un administrador dio por buena esta version. Es la puerta que
    # decide si el catalogo puede salir a buscar afuera.
    #
    # Se separa de `publicada_por` a proposito, aunque a veces coincidan en el
    # tiempo. Publicar es decir "esta es la lista del colegio"; revisar es
    # decir "ya miramos que tenemos para responderla". Solo una version SIN
    # revisar habilita buscar productos en una tienda o darlos de alta a mano,
    # y una vez revisada no se vuelve a abrir: si se pudiera, cada corrida
    # volveria a consultar tiendas por listas que ya estan resueltas, y el
    # trabajo del administrador dejaria de acumularse.
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
    """Un renglon de la lista, ya resuelto a concepto.

    `concepto_id` admite nulo a proposito: un renglon que el sistema no supo
    normalizar debe quedar visible como no resuelto en vez de desaparecer o
    de forzarse al concepto mas parecido. El corpus tiene 3.610 renglones y la
    cobertura de conceptos no es total.
    """

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

    # Restringida al MISMO vocabulario que `producto_canonico.unidad_base`, y
    # no a texto libre. Es la otra mitad de la division de empaque: con una
    # sola punta restringida, "1 resma" contra un producto que cuenta hojas da
    # un numero sin sentido y nada lo detecta. Admite nulo porque muchos
    # renglones no dicen unidad ("2 cuadernos"), y ahi contar por pieza es lo
    # correcto; lo que no se admite es una unidad escrita de cualquier forma.
    unidad: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Nulo significa "lo que diga el concepto", NO `util`. El concepto es la
    # necesidad abstracta que comparten los 17 colegios; el tipo de un renglon
    # es de ese renglon. "Diccionario: el disponible en casa" no vuelve el
    # diccionario incomprable para los diecisiete, solo para ese colegio.
    tipo_item: Mapped[str | None] = mapped_column(String(24), nullable=True)

    modo_adquisicion: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ModoAdquisicion.MERCADO_ABIERTO.value
    )

    # Lo que el colegio dijo textualmente sobre este renglon, y a donde manda
    # si el pago es por fuera. Son lo que hace util a una linea informativa:
    # sin ellos, "esto no te lo vendemos" deja al acudiente peor que antes.
    instruccion_colegio: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_externa: Mapped[str | None] = mapped_column(Text, nullable=True)

    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)

    confianza_normalizacion: Mapped[float | None] = mapped_column(nullable=True)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Los avisos de este renglon que el revisor ya decidio que no aplican
    # (`repetido:61`, `revisar:forma`, `sin_producto`), para que no vuelvan.
    avisos_descartados: Mapped[list[str]] = mapped_column(
        Texto, nullable=False, default=list, server_default=text("'[]'")
    )

    def tipo_efectivo(self, concepto: Concepto | None) -> str | None:
        """El tipo del renglon si lo declaro, y si no el de su concepto.

        Recibe el concepto en vez de navegarlo: ningun modelo de este servicio
        declara `relationship`, para que toda lectura de otra tabla sea una
        consulta visible y no una carga perezosa que aparece sola en medio del
        camino caliente.
        """
        if self.tipo_item is not None:
            return self.tipo_item
        return concepto.tipo_item if concepto is not None else None

    @property
    def surtible(self) -> bool:
        """Si Tukit puede ponerlo en el carrito o solo informarlo."""
        return self.modo_adquisicion in MODOS_SURTIBLES

    __table_args__ = (
        UniqueConstraint("version_id", "orden", name="uq_item_version_orden"),
        CheckConstraint("cantidad > 0", name="item_cantidad_positiva"),
        Index("ix_item_concepto", "concepto_id"),
        CheckConstraint(f"tipo_item IS NULL OR tipo_item IN ({_TIPOS_ITEM})", name="item_tipo_item_valido"),
        CheckConstraint(f"unidad IS NULL OR unidad IN ({_UNIDADES_BASE})", name="item_unidad_valida"),
        CheckConstraint(f"modo_adquisicion IN ({_MODOS})", name="item_modo_adquisicion_valido"),
        # Lo que Tukit no puede surtir tiene que decir como se consigue. Es la
        # misma regla que `tarea_importacion`: un aviso que nadie puede
        # atender es ruido, no un aviso.
        CheckConstraint(
            f"modo_adquisicion IN ({_MODOS_SURTIBLES}) OR instruccion_colegio IS NOT NULL",
            name="item_no_surtible_explica_como_conseguirlo",
        ),
        # Un renglon sin concepto SIEMPRE requiere revision. Sin esta regla,
        # un renglon que nadie resolvio puede quedarse callado y salir del
        # kit sin que nadie se entere.
        CheckConstraint(
            "concepto_id IS NOT NULL OR requiere_revision", name="item_sin_concepto_va_a_revision"
        ),
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

    # La EVIDENCIA de la importacion, para la revision con documento a la vista.
    #
    # Un administrador que cura una lista importada necesita ver contra que la
    # curo: el PDF original y lo que la percepcion leyo de cada pagina. Sin eso
    # la revision es a ciegas —aceptar o rechazar renglones sin poder cotejarlos
    # con la fuente— y la promesa de que la lista es fiel al documento del
    # colegio queda sin forma de verificarse. Se guarda en la tarea y no en la
    # version porque es un hecho del PROCESO de importacion (que entro, que se
    # leyo), no del contenido publicado; la version ya tiene su texto redactado.
    documento: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # La percepcion cruda por pagina: [{"pagina": int, "crudo": str}, ...].
    percepcion_cruda: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    # La version que esta importacion produjo, para poder ir de una a la otra.
    # SET NULL y no CASCADE: borrar la version no debe borrar el rastro de que
    # se importo, solo desatar el vinculo.
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("version_lista_oficial.id", ondelete="SET NULL"), nullable=True
    )
    # El destino declarado por quien importo, redundante con la lista pero util
    # para diagnosticar una importacion que fallo ANTES de resolver la lista.
    colegio_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    grado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    anio_lectivo: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # El acudiente que ORIGINO la tarea, por identificador y nunca por correo.
    #
    # Una sugerencia de lista de un padre (origen='sugerencia_padre') debe poder
    # rastrearse hasta quien la envio —para pedirle el original si hace falta—
    # pero el correo y el telefono son PII que vive SOLO en Identidad. Aqui se
    # guarda unicamente el `usuario_id` que Identidad ya emite al resolver un
    # contacto: la traza existe sin duplicar el dato sensible en Catalogo. Es
    # nullable porque las importaciones de administrador (onboarding) no tienen
    # un acudiente detras.
    contacto_referencia: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    # Las PREFERENCIAS que el acudiente declaro al subir (paso 3 del formulario:
    # pesos, disposicion a pagar de mas, personaje por hijo). Se guardan aqui, y
    # no se pierden, porque el kit del padre NO se arma al subir —la lista entra
    # sin revisar— sino cuando un administrador la aprueba: en ese momento un
    # trabajo de ruta rapida las lee para optimizar los tres kits a la medida de
    # lo que el padre pidio. Sin esto, el kit aprobado saldria con los pesos por
    # omision y no con los del acudiente. Es dato de negocio, no PII: no lleva
    # correo ni telefono. Nullable porque el onboarding del colegio no trae padre
    # ni preferencias.
    preferencias: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    # Los DATOS del colegio cuando la lista la subio un acudiente para un colegio
    # que TODAVIA NO EXISTE en Tukit: lo eligio del directorio de Bogota (trae
    # DANE) o lo escribio a mano. Es un objeto JSON con nombre, dane y los campos
    # que el revisor completa antes de aprobar (logo, direccion, contacto...).
    #
    # Vive aqui, y no en una tabla de colegios de Catalogo, porque el colegio no
    # es de Catalogo: nace en Identidad cuando un administrador APRUEBA la version
    # (el `cerrar` emite un evento y un poller de Identidad hace el upsert). Hasta
    # entonces esto es lo unico que Tukit sabe del colegio, y es lo que la cola
    # muestra en vez de un UUID crudo. Nullable porque un colegio aliado ya
    # conocido (o el onboarding de administrador) no trae datos que crear.
    colegio_datos: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    # La clave con que inteligencia reintenta una importacion (ADR 0040): una
    # subida que encontro el catalogo caido se importa despues, y si un intento
    # entro pero su respuesta se perdio, el siguiente trae la misma clave y
    # recibe esta tarea en vez de crear otra version. Unica, y nullable porque
    # el onboarding de administrador y las tareas de antes no la traen.
    clave_idempotencia: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    # Cuando el acudiente cancelo esta subida desde "Mis solicitudes". Retirar
    # borra `contacto_referencia`, y sin contacto no se distingue de una tarea
    # que nunca lo tuvo (onboarding): esta marca es la que saca de la cola de
    # verificacion una lista que ya nadie espera (H-07). Nullable: casi
    # ninguna tarea se retira.
    retirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # NO hay `caso_id` aqui, y la ausencia es deliberada.
    #
    # La version anterior de esta tabla lo tenia, apuntando a `operacion.caso`.
    # Eso metia una arista de Catalogo hacia Operacion en un grafo de
    # dependencias donde todas las demas van hacia Identidad y Catalogo, o sea
    # que **cerraba un ciclo**. Un grafo aciclico es lo que da un orden de
    # arranque y de restauracion bien definido; con el ciclo, ni levantar el
    # sistema desde cero ni restaurar un respaldo tienen orden correcto.
    #
    # La direccion correcta es la inversa: Catalogo escribe el fallo en su
    # bandeja de salida, Operacion lo consume y abre el Caso apuntando de
    # vuelta con su referencia polimorfica `caso.entidad_id`. Asi la arista va
    # de Operacion hacia Catalogo, que es el sentido permitido, y de paso
    # Catalogo deja de depender de que Operacion este arriba para registrar
    # que algo fallo.

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
        # Una tarea fallida sin diagnostico es una tarea que nadie puede
        # atender. Ya no se admite el Caso como alternativa al mensaje: el
        # Caso lo abre Operacion, asi que Catalogo no puede contar con el
        # para satisfacer su propia invariante.
        CheckConstraint("estado <> 'fallida' OR error IS NOT NULL", name="tarea_fallida_tiene_diagnostico"),
        Index("ix_tarea_pendiente", "estado", "actualizada_en"),
        Index("uq_tarea_clave_idempotencia", "clave_idempotencia", unique=True),
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
            sqlite_where=text("publicado_en IS NULL"),
        ),
    )
