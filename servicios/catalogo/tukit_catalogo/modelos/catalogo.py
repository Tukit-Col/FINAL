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
    """La necesidad abstracta que el colegio pide.

    99 conceptos derivados de las 3.610 lineas del corpus de 17 colegios, de
    los cuales 25 cubren el 81 % de los renglones de una lista tipica.

    Ojo con `tipo_item`: solo los conceptos `util` cuentan para la metrica de
    "catalogo sin huecos". Los demas o no pasan por el carrito (una licencia
    digital con pago externo), o dicen explicitamente que no hay que comprar
    (el diccionario que ya esta en casa), o todavia no se pueden resolver (los
    textos que el colegio anunciara durante el ano). Medirlos como huecos
    inflaria la carencia y empujaria a taparla con un producto inventado.
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

    # Que clase de renglon es. El valor por omision es el caso comun, de modo
    # que declarar el tipo solo cuesta trabajo cuando el item se sale de lo
    # comprable, que es cuando de verdad importa decirlo.
    tipo_item: Mapped[str] = mapped_column(String(24), nullable=False, default=TipoItem.UTIL.value)

    # Los atributos se parten en dos porque cumplen dos papeles distintos, y
    # tenerlos en un solo campo obligaba a elegir entre dos males.
    #
    # Medido contra las 4.719 lineas del corpus, de 155 pares
    # concepto-atributo declarados obligatorios solo 81 los pide alguna
    # lista. Usados todos como restriccion dura, un atributo que nadie pide y
    # que casi ningun producto declara descarta candidatos validos: pedir
    # `bata de laboratorio` no resolveria nada, porque ninguna bata del
    # catalogo dice su talla. Ignorados todos, se pierde `rayado`, que 353
    # lineas especifican y que decide si un cuaderno sirve o no.
    #
    # `discriminantes` filtra. Que este vacio es una afirmacion: este
    # concepto se resuelve por nombre y nivel, sin mas condiciones.
    atributos_discriminantes: Mapped[list[str]] = mapped_column(ListaTexto, nullable=False, default=list)
    # `descriptivos` se le muestra al acudiente para que sepa que esta
    # comprando, y no descarta a nadie.
    atributos_descriptivos: Mapped[list[str]] = mapped_column(ListaTexto, nullable=False, default=list)

    @validates("atributos_discriminantes", "atributos_descriptivos")
    def _sin_solapamiento(self, campo: str, valor: list[str] | None) -> list[str] | None:
        """Un atributo no puede filtrar y no filtrar a la vez.

        Si `rayado` estuviera en las dos listas, el comportamiento
        dependeria de cual lea primero el resolutor, y eso no es una regla
        sino un azar. La base lo impide tambien, con un CHECK; esto lo
        detiene antes, con el nombre del atributo en el mensaje, que es lo
        que necesita quien esta curando el catalogo.
        """
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

    # Dura todo el ano y sirve en todas las materias (tijeras, regla, colores):
    # si la lista lo pide en varias, se compra una vez por hijo. Lo que se gasta
    # (pegante, cinta, cuadernos) no lo es, aunque se repita.
    uno_por_estudiante: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # `interno` y no `publico`: es una agregacion sobre las listas de 17
    # colegios concretos, o sea que revela que pide el mercado atendido.
    frecuencia_demanda: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("frecuencia_demanda >= 0", name="concepto_demanda_no_negativa"),
        CheckConstraint(f"tipo_item IN ({_TIPOS_ITEM})", name="concepto_tipo_item_valido"),
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
    # `use_alter` rompe el ciclo con `producto_canonico.grupo_variante_id`, que
    # apunta de vuelta aqui. El ciclo es legitimo en el dominio: un grupo sabe
    # cual es su representante y un producto sabe a que grupo pertenece.
    #
    # Sin esto no hay ningun orden en que se puedan crear las dos tablas, y la
    # primera migracion falla al aplicarse diciendo que `producto_canonico` no
    # existe. `create_all` lo escondia porque difiere las llaves por su cuenta;
    # Alembic no, asi que el defecto solo aparecia al intentar versionar el
    # esquema. Con `use_alter`, esta llave se agrega con un ALTER despues de
    # que existan las dos tablas.
    #
    # La restriccion necesita nombre propio: un ALTER tiene que poder nombrar
    # lo que crea, y lo que no se llama de ninguna forma tampoco se puede
    # revertir.
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

    # Nula por DOS razones distintas, y conviene no confundirlas porque la
    # segunda es contraintuitiva y alguien la va a querer "arreglar".
    #
    # (1) La fuente no lo trae. Es el caso normal, no la excepcion: el canal
    #     mayorista publica 0,00 por ciento de EAN valido. Solo las tiendas
    #     VTEX lo traen.
    #
    # (2) El EAN existe pero NO identifica al producto. 146 referencias de
    #     una de las tiendas comparten codigo entre listados distintos: una
    #     misma carpeta con Moana, Frozen, Minnie y Stitch lleva un solo
    #     codigo de barras, y son cuatro productos distintos porque el nino
    #     elige uno. Donde eso pasa el EAN se anula a proposito y la
    #     identidad recae en la URL de la oferta.
    #
    # De ahi que solo 39 de 242 productos del catalogo curado lleven EAN. Esa
    # cobertura baja NO es un defecto de la ingesta que haya que subir: subirla
    # exigiria quitar la anulacion del caso (2), y eso volveria a fundir cuatro
    # productos en uno. La restriccion de unicidad de abajo es la que hizo
    # visible el problema, reventando en las pruebas.
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

    # Las dos columnas que sacan el tamano del empaque de `atributos`, donde
    # era indistinguible de una dimension fisica. Para "Bloc origami x 50
    # unidades (15 x 15 cm)", `atributos['cantidades_declaradas']` valia
    # `['15:cm', '15:x', '50:unidades', '50:x']`: el 50 es el empaque y el 15
    # es un lado, y NADA en el dato lo decia. De ahi salia el error de
    # carrito de sumar 12 cajas cuando la lista pedia 12 lapices.
    #
    # Con las dos separadas, el pipeline puede calcular
    # `unidades_a_comprar = techo(cantidad_pedida / unidades_por_empaque)`.
    # La regla no vive aqui, pero sin estas columnas no se podia ni enunciar.
    #
    # Los valores por omision son el caso comun (una unidad suelta), de forma
    # que solo el empaque excepcional cuesta declararlo.
    unidad_base: Mapped[str] = mapped_column(String(16), nullable=False, default=UnidadBase.UNIDAD.value)
    unidades_por_empaque: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    atributos: Mapped[dict[str, Any]] = mapped_column(Texto, nullable=False, default=dict)
    ruta_categoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    es_propio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    grupo_variante_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupo_variante.id", ondelete="SET NULL"), nullable=True
    )
    es_representante_canonico: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
        # `nivel` y `personaje` son ejes ORTOGONALES, y esta restriccion es lo
        # que lo impone. `Arquitectura/datos_fuente/tier_marcas.json` lista
        # `licencia` al lado de economica, confiable y premium como si fuera
        # un nivel mas, con `utilidad_por_tier['licencia'] = null`. Bajo esa
        # taxonomia un cuaderno de Spiderman pierde su nivel de calidad y el
        # optimizador se queda sin puntaje con que compararlo, que es por lo
        # que hoy no se puede ofrecer premium, economico y varios
        # personalizados a la vez. El personaje va en su propia columna.
        CheckConstraint(f"nivel IN ({_NIVELES})", name="producto_nivel_valido"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 1", name="producto_calidad_en_rango"),
        CheckConstraint(f"unidad_base IN ({_UNIDADES_BASE})", name="producto_unidad_base_valida"),
        # Un empaque de cero unidades es una division por cero esperando su
        # turno en la regla de compra.
        CheckConstraint("unidades_por_empaque > 0", name="producto_empaque_positivo"),
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

    # Sin `__table_args__`: la unicidad de (concepto, tienda, ruta) ya la
    # impone la llave primaria compuesta de arriba. Aqui hubo una restriccion
    # unica sobre esas mismas tres columnas, que no agregaba garantia y si
    # rompia el esquema: Postgres la fundia con la primaria al crear la tabla,
    # la superviviente se quedaba con el nombre `uq_concepto_ruta`, y la
    # comparacion contra los modelos reportaba para siempre una diferencia
    # imposible de cerrar.


class SustituibilidadConcepto(Base):
    """Que ofrecer cuando el catalogo no tiene lo que la lista pide.

    102 de las 297 celdas (concepto x nivel) estan vacias y 17 conceptos no
    tienen ni un producto, asi que "no lo tengo" es hoy la salida mas
    frecuente del pipeline y tambien la mas inutil. Esta tabla es lo que
    convierte esa disculpa en una oferta: "no tengo block oficio, pero el
    carta le sirve, y le digo por que".

    Reemplaza al grafo en memoria que el pipeline rearmaba entero por CADA
    item y que costaba el 95,3 % de su latencia: 1.673 ms construirlo contra
    0,137 ms consultarlo. De ahi que todo el diseno gire alrededor de que la
    respuesta sea una consulta con indice; si hubiera que recorrerla entera,
    el cambio solo moveria el costo de la memoria al disco.

    Dos propiedades que la hacen distinta de una similitud calculada:

    Es DIRIGIDA. Que un block de dibujo pase por uno de origami no implica lo
    contrario: el gramaje del origami no aguanta lo que el de dibujo si. Una
    relacion simetrica tendria que elegir un solo numero para dos preguntas
    con respuestas distintas, y por eso la sustitucion en los dos sentidos
    son dos filas con su propio grado.

    Es CURADA sobre los 99 conceptos, no inducida. `motivo` y `curado_por` no
    admiten nulo por eso mismo: una arista que no dice por que existe ni
    quien la puso no se puede revisar, y poder revisarla es lo unico que la
    separa de un coseno entre embeddings, que es justo lo que aqui no se
    quiere.
    """

    __tablename__ = "sustituibilidad_concepto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Llaves foraneas de verdad y no referencias logicas: los dos extremos son
    # conceptos de este mismo servicio.
    concepto_origen_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), nullable=False
    )
    concepto_sustituto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concepto.id", ondelete="CASCADE"), nullable=False
    )

    # Cuanto sirve el sustituto, por encima de 0 y hasta 1. Es lo que ordena
    # las alternativas cuando hay varias, que es el uso real: se ofrece la
    # mejor primero.
    grado: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)

    motivo: Mapped[str] = mapped_column(Text, nullable=False)

    # Cruza a identidad.usuario. Declarada en el manifiesto, por la misma
    # razon que `producto_canonico.curado_por`.
    curado_por: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    curado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("concepto_origen_id", "concepto_sustituto_id", name="uq_sustituibilidad_par"),
        # Una arista reflexiva no ofrece ninguna alternativa y encima ensucia
        # el orden con el concepto que justamente no se tiene.
        CheckConstraint("concepto_origen_id <> concepto_sustituto_id", name="sustituibilidad_no_reflexiva"),
        # Se excluye el cero a proposito: "no sustituye" es lo mismo que no
        # tener la fila, y admitirlo llenaria la tabla de aristas que solo
        # cuestan de leer y nunca se pueden ofrecer.
        CheckConstraint("grado > 0 AND grado <= 1", name="sustituibilidad_grado_en_rango"),
        # El indice que justifica la tabla. El par unico ya sirve para saber
        # si una arista existe; este es el que responde "cuales son y en que
        # orden" sin ordenar en memoria, que es la consulta del pipeline.
        Index("ix_sustituibilidad_origen", "concepto_origen_id", "grado"),
    )


# El mismo invariante que valida el modelo, impuesto por la base.
#
# Va como DDL condicionada al dialecto y no en `__table_args__` porque el
# operador de solapamiento de arreglos es de Postgres: escrito en
# `__table_args__`, SQLite ni siquiera podria CREAR la tabla, y las pruebas
# corren en SQLite. Ya paso una vez con un JSONB puesto a mano, y el sintoma
# fue noventa y cinco errores en pruebas de tablas sin relacion.
#
# El modelo lo valida para dar un mensaje util a quien cura; la base lo impone
# para el cargador, que escribe con Core y no pasa por los validadores del ORM.
event.listen(
    Concepto.__table__,
    "after_create",
    DDL(
        "ALTER TABLE concepto ADD CONSTRAINT concepto_atributos_sin_solapar "
        "CHECK (NOT (atributos_discriminantes && atributos_descriptivos))"
    ).execute_if(dialect="postgresql"),
)
