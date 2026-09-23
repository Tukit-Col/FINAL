"""La superficie de LECTURA del catalogo. Lo que el frontend navega.

El catalogo existia en la base y no lo exponia nadie: 100 conceptos, 261
productos y 268 precios que solo se podian ver con `psql` o con el HTML
estatico de `vista`. Este modulo es lo que convierte esa base en algo que una
pantalla puede pintar.

Por que FastAPI aqui y `http.server` en `admin`, que parece una
incoherencia y no lo es. `admin` es una pantalla de curaduria que corre UNA
persona en su maquina: no tiene clientes, no tiene contrato y no tiene que
documentarse. Esto lo consume otro equipo contra un contrato congelado, en
otro proceso y en otro origen, asi que necesita justo lo que un framework da y
`http.server` no: validacion de la entrada, el esquema OpenAPI que el frontend
lee para generar sus tipos, y CORS.

**Es de solo lectura, y a proposito.** Ni un `POST` que escriba catalogo. Lo
que escribe pasa por la cola de propuestas de `descubrir` y por la mano de una
persona, porque una busqueda por texto trae productos reales que no son lo
pedido. La unica ruta que no es `GET` es `POST /v1/catalogo/emparejar`, que
tampoco escribe: es `POST` porque recibe una lista de renglones en el cuerpo,
no porque cambie nada.

**El dinero sale en pesos enteros**, no en los centavos en que se guarda. Es
lo que fija la seccion 1.4 del contrato, y la conversion se hace aqui y una
sola vez para que ningun cliente tenga que acordarse de dividir.

    python -m tukit_catalogo.api            # localhost:8012
    python -m tukit_catalogo.api --puerto 9000
"""

from __future__ import annotations

import argparse
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Query
from sqlalchemy import Select, and_, func, or_, select
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app

from .modelos import Base

PUERTO_POR_OMISION = 8012

# Tope duro del tamano de pagina. No es una manía de rendimiento: sin el, un
# cliente puede pedir las 261 filas con sus ofertas y sus precios en una sola
# respuesta, y el dia que el catalogo tenga 26.000 la misma llamada tumba la
# pantalla sin que nada haya cambiado en el codigo del frontend.
POR_PAGINA_MAXIMO = 200
POR_PAGINA_POR_OMISION = 50

_ORDEN_NIVEL = ("economico", "confiable", "premium")

CONCEPTO = Base.metadata.tables["concepto"]
PRODUCTO = Base.metadata.tables["producto_canonico"]
TIENDA = Base.metadata.tables["tienda"]
OFERTA = Base.metadata.tables["oferta_tienda"]
PRECIO = Base.metadata.tables["precio_oferta"]
LISTA = Base.metadata.tables["lista_oficial"]
VERSION = Base.metadata.tables["version_lista_oficial"]
ITEM = Base.metadata.tables["item_lista_oficial"]


def pesos(centavos: int | None) -> int | None:
    """Centavos a pesos enteros. `None` es "no se conoce", no cero.

    La distincion es del contrato y no es cosmetica: un producto sin precio
    observado no se puede sumar a un total, y un cero lo sumaria sin ruido.
    """
    return None if centavos is None else int(centavos) // 100


def _precio_minimo_vigente() -> Any:
    """Subconsulta con el precio vigente mas bajo por producto.

    Sale de la OFERTA y no del producto, porque el precio es propiedad de la
    relacion entre un producto y una tienda: ese fue el defecto del esquema
    anterior, donde `precio` era columna del producto y comparar dos tiendas
    era inexpresable. Lo que se le muestra al acudiente es el menor vigente.
    """
    return (
        select(
            OFERTA.c.producto_canonico_id.label("pid"),
            func.min(PRECIO.c.valor_centavos).label("centavos"),
            func.count(func.distinct(OFERTA.c.tienda_id)).label("tiendas"),
        )
        .select_from(OFERTA.join(PRECIO, PRECIO.c.oferta_id == OFERTA.c.id))
        .where(OFERTA.c.activo.is_(True), PRECIO.c.vigente_hasta.is_(None))
        .group_by(OFERTA.c.producto_canonico_id)
        .subquery()
    )


def _paginar(consulta: Select, pagina: int, por_pagina: int) -> Select:
    return consulta.limit(por_pagina).offset((pagina - 1) * por_pagina)


async def _total(conexion: Any, consulta: Select) -> int:
    return int(await conexion.scalar(select(func.count()).select_from(consulta.subquery())) or 0)


def _sobre(pagina: int, por_pagina: int, total: int, clave: str, filas: list[Any]) -> dict[str, Any]:
    """El mismo sobre para toda coleccion.

    Que las cuatro colecciones se paginen igual es lo que permite que el
    frontend escriba el componente de paginacion una vez. `total` va siempre,
    tambien cuando cabe en una pagina, porque "cuantos hay" es la pregunta que
    decide si se pinta el paginador.
    """
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, clave: filas}


def _concepto_publico(fila: Any) -> dict[str, Any]:
    return {
        "codigo": fila.codigo,
        "nombre": fila.nombre_canonico,
        "categoria": fila.categoria,
        "tipo_item": fila.tipo_item,
        "sinonimos": list(fila.sinonimos or ()),
        "admite_personaje": bool(fila.admite_personaje),
        # Los dos papeles del atributo, separados tambien en la respuesta. El
        # discriminante filtra y el descriptivo solo cuenta que estas
        # comprando; el frontend los pinta distinto porque son cosas distintas.
        "atributos_discriminantes": list(fila.atributos_discriminantes or ()),
        "atributos_descriptivos": list(fila.atributos_descriptivos or ()),
        "frecuencia_demanda": int(fila.frecuencia_demanda or 0),
    }


def _producto_publico(fila: Any) -> dict[str, Any]:
    return {
        "sku": fila.sku_interno,
        "nombre": fila.nombre,
        "marca": fila.marca,
        "nivel": fila.nivel,
        "personaje": fila.personaje,
        "imagen_url": fila.imagen_url,
        "descripcion": fila.descripcion,
        # Las dos columnas de las que depende no sumar doce cajas cuando la
        # lista pidio doce lapices. Van en la respuesta porque el frontend
        # tiene que poder decir "una caja de 12" y no "12".
        "unidad_base": fila.unidad_base,
        "unidades_por_empaque": int(fila.unidades_por_empaque or 1),
        "atributos": dict(fila.atributos or {}),
        "quality_score": float(fila.quality_score),
        "concepto": {"codigo": fila.concepto_codigo, "nombre": fila.concepto_nombre},
        "precio_desde": pesos(getattr(fila, "centavos", None)),
        "tiendas": int(getattr(fila, "tiendas", 0) or 0),
    }


def _consulta_productos(precio_min: Any) -> Select:
    return (
        select(
            PRODUCTO.c.id,
            PRODUCTO.c.sku_interno,
            PRODUCTO.c.nombre,
            PRODUCTO.c.descripcion,
            PRODUCTO.c.marca,
            PRODUCTO.c.nivel,
            PRODUCTO.c.personaje,
            PRODUCTO.c.imagen_url,
            PRODUCTO.c.unidad_base,
            PRODUCTO.c.unidades_por_empaque,
            PRODUCTO.c.atributos,
            PRODUCTO.c.quality_score,
            CONCEPTO.c.codigo.label("concepto_codigo"),
            CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
            precio_min.c.centavos,
            precio_min.c.tiendas,
        )
        .select_from(
            PRODUCTO.join(CONCEPTO, CONCEPTO.c.id == PRODUCTO.c.concepto_id).outerjoin(
                precio_min, precio_min.c.pid == PRODUCTO.c.id
            )
        )
        .where(PRODUCTO.c.activo.is_(True))
    )


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("catalogo")


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Catalogo",
    descripcion=(
        "Lectura del catalogo curado: conceptos, productos canonicos con sus niveles y "
        "personaje, ofertas por tienda con precio, y las listas oficiales de los colegios. "
        "Contrato: arquitectura/CONTRATO_API.md seccion 12."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)


# ---------------------------------------------------------------------------
# Conceptos
# ---------------------------------------------------------------------------


@app.get(
    "/v1/catalogo/categorias",
    tags=["catalogo"],
    summary="Las categorias con cuantos conceptos tiene cada una",
)
async def categorias() -> dict[str, Any]:
    async with app.state.motor.engine.begin() as conexion:
        filas = await conexion.execute(
            select(CONCEPTO.c.categoria, func.count().label("conceptos"))
            .where(CONCEPTO.c.activo.is_(True))
            .group_by(CONCEPTO.c.categoria)
            .order_by(CONCEPTO.c.categoria)
        )
        datos = [{"categoria": f.categoria, "conceptos": int(f.conceptos)} for f in filas]
    return {"total": len(datos), "categorias": datos}


@app.get("/v1/catalogo/conceptos", tags=["catalogo"], summary="Conceptos del catalogo, paginados")
async def listar_conceptos(
    categoria: Annotated[str | None, Query(description="Filtra por categoria exacta")] = None,
    tipo_item: Annotated[str | None, Query(description="util, texto, libro_libre, ...")] = None,
    busqueda: Annotated[str | None, Query(description="Texto en el nombre o en los sinonimos")] = None,
    con_producto: Annotated[bool | None, Query(description="Solo los que tienen algun producto")] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAXIMO)] = POR_PAGINA_POR_OMISION,
) -> dict[str, Any]:
    productos_por_concepto = (
        select(
            PRODUCTO.c.concepto_id.label("cid"),
            func.count().label("productos"),
            func.count(func.distinct(PRODUCTO.c.nivel)).label("niveles"),
        )
        .where(PRODUCTO.c.activo.is_(True))
        .group_by(PRODUCTO.c.concepto_id)
        .subquery()
    )

    consulta = (
        select(
            CONCEPTO.c.codigo,
            CONCEPTO.c.nombre_canonico,
            CONCEPTO.c.categoria,
            CONCEPTO.c.tipo_item,
            CONCEPTO.c.sinonimos,
            CONCEPTO.c.admite_personaje,
            CONCEPTO.c.atributos_discriminantes,
            CONCEPTO.c.atributos_descriptivos,
            CONCEPTO.c.frecuencia_demanda,
            func.coalesce(productos_por_concepto.c.productos, 0).label("productos"),
            func.coalesce(productos_por_concepto.c.niveles, 0).label("niveles"),
        )
        .select_from(
            CONCEPTO.outerjoin(productos_por_concepto, productos_por_concepto.c.cid == CONCEPTO.c.id)
        )
        .where(CONCEPTO.c.activo.is_(True))
    )

    if categoria:
        consulta = consulta.where(CONCEPTO.c.categoria == categoria)
    if tipo_item:
        consulta = consulta.where(CONCEPTO.c.tipo_item == tipo_item)
    if busqueda:
        patron = f"%{busqueda.lower()}%"
        consulta = consulta.where(func.lower(CONCEPTO.c.nombre_canonico).like(patron))
    if con_producto is True:
        consulta = consulta.where(productos_por_concepto.c.productos > 0)
    elif con_producto is False:
        consulta = consulta.where(productos_por_concepto.c.productos.is_(None))

    # Por demanda y no alfabetico: el orden por omision de una pantalla de
    # catalogo tiene que ser el de lo que los colegios de verdad piden, que es
    # lo que midio el corpus. Alfabetico pondria `abaco` antes que `cuaderno`.
    consulta = consulta.order_by(CONCEPTO.c.frecuencia_demanda.desc(), CONCEPTO.c.codigo)

    async with app.state.motor.engine.begin() as conexion:
        total = await _total(conexion, consulta)
        filas = await conexion.execute(_paginar(consulta, pagina, por_pagina))
        datos = [
            _concepto_publico(f) | {"productos": int(f.productos), "niveles_disponibles": int(f.niveles)}
            for f in filas
        ]
    return _sobre(pagina, por_pagina, total, "conceptos", datos)


@app.get(
    "/v1/catalogo/conceptos/{codigo}",
    tags=["catalogo"],
    summary="Un concepto con sus productos, uno por nivel disponible",
)
async def ver_concepto(codigo: str) -> dict[str, Any]:
    precio_min = _precio_minimo_vigente()
    async with app.state.motor.engine.begin() as conexion:
        fila = (await conexion.execute(select(CONCEPTO).where(CONCEPTO.c.codigo == codigo))).one_or_none()
        if fila is None:
            raise ErrorDominio(
                "concepto_no_existe",
                f"No hay ningun concepto con el codigo {codigo}.",
                estado=404,
            )
        productos = await conexion.execute(
            _consulta_productos(precio_min)
            .where(PRODUCTO.c.concepto_id == fila.id)
            .order_by(PRODUCTO.c.nivel, PRODUCTO.c.nombre)
        )
        elegidos = [_producto_publico(p) for p in productos]

    # El orden del nivel es economico, confiable, premium y no el alfabetico
    # que da la base (confiable, economico, premium). Es el eje con el que el
    # acudiente compara, asi que verlo desordenado cuesta una lectura extra.
    elegidos.sort(
        key=lambda p: (_ORDEN_NIVEL.index(p["nivel"]) if p["nivel"] in _ORDEN_NIVEL else 9, p["nombre"])
    )
    return _concepto_publico(fila) | {"productos": elegidos}


# ---------------------------------------------------------------------------
# Productos y ofertas
# ---------------------------------------------------------------------------


@app.get("/v1/catalogo/productos", tags=["catalogo"], summary="Productos canonicos, paginados")
async def listar_productos(
    concepto: Annotated[str | None, Query(description="Codigo de concepto")] = None,
    nivel: Annotated[str | None, Query(description="economico | confiable | premium")] = None,
    personaje: Annotated[str | None, Query(description="Nombre del personaje")] = None,
    con_personaje: Annotated[bool | None, Query(description="Solo con, o solo sin, personaje")] = None,
    busqueda: Annotated[str | None, Query(description="Texto en el nombre del producto")] = None,
    con_precio: Annotated[bool | None, Query(description="Solo los que tienen precio vigente")] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAXIMO)] = POR_PAGINA_POR_OMISION,
) -> dict[str, Any]:
    if nivel is not None and nivel not in _ORDEN_NIVEL:
        raise ErrorDominio(
            "nivel_invalido",
            f"El nivel debe ser uno de {', '.join(_ORDEN_NIVEL)}.",
            campo="nivel",
        )

    precio_min = _precio_minimo_vigente()
    consulta = _consulta_productos(precio_min)

    if concepto:
        consulta = consulta.where(CONCEPTO.c.codigo == concepto)
    if nivel:
        consulta = consulta.where(PRODUCTO.c.nivel == nivel)
    if personaje:
        consulta = consulta.where(func.lower(PRODUCTO.c.personaje) == personaje.lower())
    if con_personaje is True:
        consulta = consulta.where(PRODUCTO.c.personaje.is_not(None))
    elif con_personaje is False:
        consulta = consulta.where(PRODUCTO.c.personaje.is_(None))
    if busqueda:
        patron = f"%{busqueda.lower()}%"
        consulta = consulta.where(
            or_(func.lower(PRODUCTO.c.nombre).like(patron), func.lower(PRODUCTO.c.marca).like(patron))
        )
    if con_precio is True:
        consulta = consulta.where(precio_min.c.centavos.is_not(None))

    consulta = consulta.order_by(CONCEPTO.c.codigo, PRODUCTO.c.nivel, PRODUCTO.c.nombre)

    async with app.state.motor.engine.begin() as conexion:
        total = await _total(conexion, consulta)
        filas = await conexion.execute(_paginar(consulta, pagina, por_pagina))
        datos = [_producto_publico(f) for f in filas]
    return _sobre(pagina, por_pagina, total, "productos", datos)


@app.get(
    "/v1/catalogo/productos/{sku}",
    tags=["catalogo"],
    summary="Un producto con TODAS sus ofertas, para comparar precio entre tiendas",
)
async def ver_producto(sku: str) -> dict[str, Any]:
    precio_min = _precio_minimo_vigente()
    async with app.state.motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(_consulta_productos(precio_min).where(PRODUCTO.c.sku_interno == sku))
        ).one_or_none()
        if fila is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)

        ofertas = await conexion.execute(
            select(
                TIENDA.c.slug,
                TIENDA.c.nombre.label("tienda_nombre"),
                TIENDA.c.tipo,
                OFERTA.c.url,
                OFERTA.c.disponible,
                OFERTA.c.metodo_vinculacion,
                OFERTA.c.confianza_vinculacion,
                PRECIO.c.valor_centavos,
                PRECIO.c.vigente_desde,
                PRECIO.c.vigente_hasta,
                PRECIO.c.fuente,
            )
            .select_from(
                OFERTA.join(TIENDA, TIENDA.c.id == OFERTA.c.tienda_id).outerjoin(
                    PRECIO,
                    and_(PRECIO.c.oferta_id == OFERTA.c.id, PRECIO.c.vigente_hasta.is_(None)),
                )
            )
            .where(OFERTA.c.producto_canonico_id == fila.id, OFERTA.c.activo.is_(True))
        )
        detalle = [
            {
                "tienda": f.slug,
                "tienda_nombre": f.tienda_nombre,
                "tipo_tienda": f.tipo,
                "url": f.url,
                # Tres valores y no dos: `null` es "la fuente no reporta
                # existencias", que no es lo mismo que "no hay". El canal
                # mayorista nunca las reporta, y forzar `false` descartaria
                # ofertas legitimas por una observacion que nunca se hizo.
                "disponible": f.disponible,
                "precio": pesos(f.valor_centavos),
                "vigente_desde": f.vigente_desde.isoformat() if f.vigente_desde else None,
                "vigente_hasta": f.vigente_hasta.isoformat() if f.vigente_hasta else None,
                "fuente_precio": f.fuente,
                "metodo_vinculacion": f.metodo_vinculacion,
                "confianza_vinculacion": float(f.confianza_vinculacion),
            }
            for f in ofertas
        ]
    # Las que tienen precio primero y de menor a mayor; las que no lo tienen al
    # final, porque una oferta sin precio no se puede comparar pero tampoco se
    # esconde: existe y el acudiente puede ir a mirarla.
    detalle.sort(key=lambda o: (o["precio"] is None, o["precio"] or 0))
    return _producto_publico(fila) | {"ofertas": detalle}


@app.get("/v1/catalogo/tiendas", tags=["catalogo"], summary="Las tiendas con oferta viva en el catalogo")
async def listar_tiendas() -> dict[str, Any]:
    async with app.state.motor.engine.begin() as conexion:
        filas = await conexion.execute(
            select(
                TIENDA.c.slug,
                TIENDA.c.nombre,
                TIENDA.c.tipo,
                TIENDA.c.url_base,
                func.count(OFERTA.c.id).label("ofertas"),
            )
            .select_from(
                TIENDA.outerjoin(OFERTA, and_(OFERTA.c.tienda_id == TIENDA.c.id, OFERTA.c.activo.is_(True)))
            )
            .where(TIENDA.c.activa.is_(True))
            .group_by(TIENDA.c.slug, TIENDA.c.nombre, TIENDA.c.tipo, TIENDA.c.url_base)
            .order_by(func.count(OFERTA.c.id).desc(), TIENDA.c.slug)
        )
        datos = [
            {
                "slug": f.slug,
                "nombre": f.nombre,
                "tipo": f.tipo,
                "url_base": f.url_base,
                "ofertas": int(f.ofertas),
            }
            for f in filas
        ]
    return {"total": len(datos), "tiendas": datos}


# ---------------------------------------------------------------------------
# Listas oficiales
# ---------------------------------------------------------------------------


@app.get("/v1/listas", tags=["listas"], summary="Listas oficiales publicadas, filtrables por colegio y grado")
async def listar_listas(
    colegio_id: Annotated[
        uuid.UUID | None, Query(description="Identificador del colegio (viene de identidad)")
    ] = None,
    grado: Annotated[str | None, Query(description="Grado tal como lo nombra el colegio")] = None,
    anio_lectivo: Annotated[int | None, Query(ge=2020, le=2100)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAXIMO)] = POR_PAGINA_POR_OMISION,
) -> dict[str, Any]:
    # La etiqueta es `renglones` y no `items` por una razon que cuesta media
    # hora encontrar: `subconsulta.c.items` no devuelve la columna sino el
    # metodo `items()` de la coleccion de columnas, y SQLAlchemy lo pasa como
    # parametro al motor. El sintoma es un error de tipo de asyncpg que no
    # menciona en ningun momento el nombre de la columna.
    items_por_version = (
        select(ITEM.c.version_id.label("vid"), func.count().label("renglones"))
        .group_by(ITEM.c.version_id)
        .subquery()
    )

    consulta = (
        select(
            LISTA.c.id,
            LISTA.c.colegio_id,
            LISTA.c.sede_id,
            LISTA.c.grado,
            LISTA.c.anio_lectivo,
            VERSION.c.id.label("version_id"),
            VERSION.c.numero,
            VERSION.c.publicada_en,
            VERSION.c.revisada_en,
            func.coalesce(items_por_version.c.renglones, 0).label("renglones"),
        )
        .select_from(
            LISTA.join(
                VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.vigente.is_(True))
            ).outerjoin(items_por_version, items_por_version.c.vid == VERSION.c.id)
        )
        .where(LISTA.c.activa.is_(True))
    )

    if colegio_id is not None:
        consulta = consulta.where(LISTA.c.colegio_id == colegio_id)
    if grado:
        consulta = consulta.where(LISTA.c.grado == grado)
    if anio_lectivo is not None:
        consulta = consulta.where(LISTA.c.anio_lectivo == anio_lectivo)

    consulta = consulta.order_by(LISTA.c.anio_lectivo.desc(), LISTA.c.colegio_id, LISTA.c.grado)

    async with app.state.motor.engine.begin() as conexion:
        total = await _total(conexion, consulta)
        filas = await conexion.execute(_paginar(consulta, pagina, por_pagina))
        datos = [
            {
                "lista_id": str(f.id),
                "colegio_id": str(f.colegio_id),
                "sede_id": str(f.sede_id) if f.sede_id else None,
                "grado": f.grado,
                "anio_lectivo": int(f.anio_lectivo),
                "version_id": str(f.version_id),
                "version": int(f.numero),
                "publicada_en": f.publicada_en.isoformat() if f.publicada_en else None,
                # Que este sin revisar no es un defecto: es la puerta que
                # habilita salir a una tienda por lo que la lista pide y el
                # catalogo no tiene. Una vez revisada, no se vuelve a abrir.
                "revisada": f.revisada_en is not None,
                "items": int(f.renglones),
            }
            for f in filas
        ]
    return _sobre(pagina, por_pagina, total, "listas", datos)


@app.get(
    "/v1/listas/{lista_id}",
    tags=["listas"],
    summary="Los renglones de la version vigente de una lista, ya resueltos a concepto",
)
async def ver_lista(lista_id: uuid.UUID) -> dict[str, Any]:
    async with app.state.motor.engine.begin() as conexion:
        cabeza = (
            await conexion.execute(
                select(LISTA, VERSION.c.id.label("version_id"), VERSION.c.numero, VERSION.c.revisada_en)
                .select_from(
                    LISTA.join(VERSION, and_(VERSION.c.lista_id == LISTA.c.id, VERSION.c.vigente.is_(True)))
                )
                .where(LISTA.c.id == lista_id)
            )
        ).one_or_none()
        if cabeza is None:
            raise ErrorDominio(
                "lista_no_existe",
                "No hay ninguna lista con ese identificador, o su version vigente falta.",
                estado=404,
            )

        filas = await conexion.execute(
            select(
                ITEM.c.id,
                ITEM.c.orden,
                ITEM.c.texto_original,
                ITEM.c.cantidad,
                ITEM.c.unidad,
                ITEM.c.tipo_item,
                ITEM.c.modo_adquisicion,
                ITEM.c.instruccion_colegio,
                ITEM.c.url_externa,
                ITEM.c.atributos,
                ITEM.c.requiere_revision,
                CONCEPTO.c.codigo.label("concepto_codigo"),
                CONCEPTO.c.nombre_canonico.label("concepto_nombre"),
                CONCEPTO.c.tipo_item.label("concepto_tipo_item"),
            )
            .select_from(ITEM.outerjoin(CONCEPTO, CONCEPTO.c.id == ITEM.c.concepto_id))
            .where(ITEM.c.version_id == cabeza.version_id)
            .order_by(ITEM.c.orden)
        )
        items = [
            {
                "item_id": str(f.id),
                "orden": int(f.orden),
                "texto_original": f.texto_original,
                "cantidad": int(f.cantidad),
                "unidad": f.unidad,
                # Nulo en el renglon significa "lo que diga el concepto", NO
                # `util`. Se resuelve aqui para que el cliente no tenga que
                # reimplementar la regla, y se conservan los dos campos para
                # que se pueda ver de donde salio.
                "tipo_item": f.tipo_item or f.concepto_tipo_item,
                "tipo_item_declarado": f.tipo_item,
                "modo_adquisicion": f.modo_adquisicion,
                "surtible": f.modo_adquisicion in ("mercado_abierto", "libro_libre"),
                "instruccion_colegio": f.instruccion_colegio,
                "url_externa": f.url_externa,
                "atributos": dict(f.atributos or {}),
                "requiere_revision": bool(f.requiere_revision),
                "concepto": (
                    {"codigo": f.concepto_codigo, "nombre": f.concepto_nombre} if f.concepto_codigo else None
                ),
            }
            for f in filas
        ]

    return {
        "lista_id": str(cabeza.id),
        "colegio_id": str(cabeza.colegio_id),
        "sede_id": str(cabeza.sede_id) if cabeza.sede_id else None,
        "grado": cabeza.grado,
        "anio_lectivo": int(cabeza.anio_lectivo),
        "version_id": str(cabeza.version_id),
        "version": int(cabeza.numero),
        "revisada": cabeza.revisada_en is not None,
        "total_items": len(items),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Emparejamiento
# ---------------------------------------------------------------------------


@app.post(
    "/v1/catalogo/emparejar",
    tags=["catalogo"],
    summary="Empareja renglones de lista contra el catalogo. No escribe nada.",
)
async def emparejar_renglones(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """La misma decision que `consulta.emparejar`, expuesta por HTTP.

    Existe porque `inteligencia` no puede ver esta base ni importar este
    paquete (invariantes 1 y 3), y sin embargo la etapa de resolucion de su
    pipeline necesita exactamente esto. La alternativa habria sido que el
    pipeline hablara con `tukit_catalogo` en el mismo proceso, que es la
    frontera que el rediseno entero existe para no volver a cruzar.

    No escribe: es el match del acudiente, y ese camino no sale a la red ni
    da nada de alta. Lo que da de alta es `descubrir`, y solo a traves de una
    version de lista sin revisar.
    """
    from .consulta import emparejar

    renglones = cuerpo.get("renglones")
    if not isinstance(renglones, list) or not renglones:
        raise ErrorDominio(
            "renglones_vacios",
            "Manda al menos un renglon en `renglones`.",
            campo="renglones",
        )
    if len(renglones) > 500:
        raise ErrorDominio(
            "demasiados_renglones",
            "Una lista de un grado no tiene 500 renglones. Manda como mucho 500.",
            estado=422,
            campo="renglones",
        )

    conceptos, productos = await _indice(app.state.motor)
    resultados = [emparejar(str(r), conceptos, productos) for r in renglones]
    return {"total": len(resultados), "emparejamientos": [r.a_dict() for r in resultados]}


async def _indice(motor: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Conceptos y productos en la forma que `emparejar` espera.

    Es la consulta de `consulta.cargar_indice`, pero reusando el motor que ya
    tiene abierto el servicio en vez de crear uno por llamada. Crear y
    desechar un motor por peticion es un pool de conexiones nuevo cada vez, y
    ese fue uno de los cuellos que el perfilado encontro en la ingesta.
    """
    precio_min = _precio_minimo_vigente()
    async with motor.engine.begin() as conexion:
        conceptos = [
            {
                "id": f.id,
                "codigo": f.codigo,
                "nombre": f.nombre_canonico,
                "sinonimos": list(f.sinonimos or ()),
                "discriminantes": tuple(f.atributos_discriminantes or ()),
            }
            for f in await conexion.execute(
                select(
                    CONCEPTO.c.id,
                    CONCEPTO.c.codigo,
                    CONCEPTO.c.nombre_canonico,
                    CONCEPTO.c.sinonimos,
                    CONCEPTO.c.atributos_discriminantes,
                ).where(CONCEPTO.c.activo.is_(True))
            )
        ]
        productos = [
            {
                "id": f.id,
                "concepto_id": f.concepto_id,
                "sku": f.sku_interno,
                "nombre": f.nombre,
                "nivel": f.nivel,
                "personaje": f.personaje,
                "marca": f.marca,
                "imagen_url": f.imagen_url,
                "unidad_base": f.unidad_base,
                "unidades_por_empaque": int(f.unidades_por_empaque or 1),
                "atributos": dict(f.atributos or {}),
                "precio_cop": pesos(f.centavos),
            }
            for f in await conexion.execute(
                select(
                    PRODUCTO.c.id,
                    PRODUCTO.c.concepto_id,
                    PRODUCTO.c.sku_interno,
                    PRODUCTO.c.nombre,
                    PRODUCTO.c.nivel,
                    PRODUCTO.c.personaje,
                    PRODUCTO.c.marca,
                    PRODUCTO.c.imagen_url,
                    PRODUCTO.c.unidad_base,
                    PRODUCTO.c.unidades_por_empaque,
                    PRODUCTO.c.atributos,
                    precio_min.c.centavos,
                )
                .select_from(PRODUCTO.outerjoin(precio_min, precio_min.c.pid == PRODUCTO.c.id))
                .where(PRODUCTO.c.activo.is_(True))
            )
        ]
    return conceptos, productos


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de lectura del catalogo.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
