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

from fastapi import FastAPI, Query, Response
from sqlalchemy import Select, and_, func, or_, select, update
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
TAREA = Base.metadata.tables["tarea_importacion"]


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
        # `sku` y no `sku_interno`: hacia afuera el identificador del producto
        # se llama igual en el catalogo y en el `ProductoKit` de la seccion 5,
        # que es lo que permite que una tarjeta de catalogo y una linea de kit
        # compartan componente. El nombre interno se queda en la base.
        "sku": fila.sku_interno,
        # El EAN no es un adorno: es lo unico que permite reconocer el mismo
        # producto en dos tiendas que lo nombran distinto, y la pantalla de
        # comparacion se apoya en eso. Es nulo cuando la fuente no lo publica.
        "ean": fila.ean,
        "nombre": fila.nombre,
        "marca": fila.marca,
        "nivel": fila.nivel,
        "personaje": fila.personaje,
        "imagen_url": fila.imagen_url,
        "descripcion": fila.descripcion,
        # Marca propia de Tukit. Cambia como se lee el precio -no hay una
        # tienda tercera detras- asi que la pantalla lo etiqueta aparte.
        "es_propio": bool(fila.es_propio),
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
            PRODUCTO.c.ean,
            PRODUCTO.c.es_propio,
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


def _oferta_publica(fila: Any) -> dict[str, Any]:
    return {
        "tienda": fila.slug,
        "tienda_nombre": fila.tienda_nombre,
        "tipo_tienda": fila.tipo,
        "url": fila.url,
        # Tres valores y no dos: `null` es "la fuente no reporta
        # existencias", que no es lo mismo que "no hay". El canal
        # mayorista nunca las reporta, y forzar `false` descartaria
        # ofertas legitimas por una observacion que nunca se hizo.
        "disponible": fila.disponible,
        "precio": pesos(fila.valor_centavos),
        "vigente_desde": fila.vigente_desde.isoformat() if fila.vigente_desde else None,
        "vigente_hasta": fila.vigente_hasta.isoformat() if fila.vigente_hasta else None,
        # El instante en que se observo el precio que se esta mostrando. La
        # pantalla lo necesita para poder decir "visto el 12/09" en vez de
        # presentar un precio de hace tres meses como si fuera de hoy.
        "visto_en": fila.vigente_desde.isoformat() if fila.vigente_desde else None,
        "fuente_precio": fila.fuente,
        "metodo_vinculacion": fila.metodo_vinculacion,
        "confianza_vinculacion": float(fila.confianza_vinculacion),
    }


def _consulta_ofertas(producto_ids: list[Any]) -> Select:
    """Las ofertas vivas de un conjunto de productos, con su precio vigente.

    Toma una lista de identificadores y no uno solo porque la pantalla de
    catalogo necesita las ofertas de la pagina entera: pedirlas producto a
    producto serian doscientas idas y vueltas para pintar una pagina, que es
    el patron N+1 que el perfilado ya encontro una vez en la ingesta.
    """
    return (
        select(
            OFERTA.c.producto_canonico_id.label("pid"),
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
        .where(OFERTA.c.producto_canonico_id.in_(producto_ids), OFERTA.c.activo.is_(True))
    )


def _ordenar_ofertas(ofertas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las que tienen precio primero y de menor a mayor; las que no, al final.

    Una oferta sin precio no se puede comparar, pero tampoco se esconde:
    existe y el acudiente puede ir a mirarla.
    """
    return sorted(ofertas, key=lambda o: (o["precio"] is None, o["precio"] or 0))


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

# La superficie de ESCRITURA de la revision de listas vive aparte, en
# `admin_http`, para que este modulo pueda seguir diciendo con verdad que es de
# solo lectura. Es la mano de la persona que revisa: editar renglones, decidir
# propuestas, cerrar una lista y clonarla para corregir. Se monta sobre la
# misma app —y el mismo `app.state.motor`— y se rutea por su prefijo `/v1/admin`.
from .admin_http import router as _router_admin  # noqa: E402

app.include_router(_router_admin)


# ---------------------------------------------------------------------------
# Conceptos
# ---------------------------------------------------------------------------


# Por debajo de esto un producto lo sugirio la busqueda y nadie lo confirmo.
# Vive aqui y no en la pantalla porque la cifra del resumen y la etiqueta de
# la tarjeta tienen que salir del MISMO numero: si cada lado eligiera el suyo,
# la pantalla se contradiria con su propio encabezado y no habria forma de
# saber cual de los dos miente.
UMBRAL_SIN_REVISAR = 0.5


@app.get(
    "/v1/catalogo/resumen",
    tags=["catalogo"],
    summary="Las siete cifras que resumen el estado del catalogo curado",
)
async def resumen_catalogo() -> dict[str, Any]:
    """El encabezado de la pantalla de catalogo, en una sola consulta.

    No es una comodidad: es la unica cifra que NO se puede derivar de las
    colecciones paginadas. Un cliente que solo tuviera `/productos` sabria
    cuantos hay en su pagina, no cuantos hay con foto en las 385, y para
    averiguarlo tendria que traerse el catalogo entero, que es exactamente lo
    que la paginacion existe para impedir. Sin esta ruta, el tope de pagina y
    la pantalla se contradicen.

    Las carencias se cuentan igual que los logros -conceptos sin ningun
    producto, productos sin foto, productos sin revisar- porque la pantalla se
    usa para decidir que curar, y un resumen que solo cuenta lo bueno no sirve
    para eso.
    """
    productos_por_concepto = (
        select(
            PRODUCTO.c.concepto_id.label("cid"),
            func.count(func.distinct(PRODUCTO.c.nivel)).label("niveles"),
        )
        .where(PRODUCTO.c.activo.is_(True))
        .group_by(PRODUCTO.c.concepto_id)
        .subquery()
    )

    async with app.state.motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(
                    func.count().label("conceptos"),
                    func.count(productos_por_concepto.c.niveles)
                    .filter(productos_por_concepto.c.niveles >= 3)
                    .label("tres_niveles"),
                    func.count().filter(productos_por_concepto.c.niveles.is_(None)).label("sin_producto"),
                )
                .select_from(
                    CONCEPTO.outerjoin(productos_por_concepto, productos_por_concepto.c.cid == CONCEPTO.c.id)
                )
                .where(CONCEPTO.c.activo.is_(True))
            )
        ).one()

        productos = (
            await conexion.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(PRODUCTO.c.imagen_url.is_not(None)).label("con_foto"),
                    func.count().filter(PRODUCTO.c.quality_score < UMBRAL_SIN_REVISAR).label("sin_revisar"),
                ).where(PRODUCTO.c.activo.is_(True))
            )
        ).one()

        tiendas = await conexion.scalar(
            select(func.count()).select_from(TIENDA).where(TIENDA.c.activa.is_(True))
        )

    return {
        "conceptos": int(fila.conceptos),
        "productos": int(productos.total),
        "conceptos_con_tres_niveles": int(fila.tres_niveles),
        "conceptos_sin_producto": int(fila.sin_producto),
        "productos_con_foto": int(productos.con_foto),
        "tiendas": int(tiendas or 0),
        "productos_sin_revisar": int(productos.sin_revisar),
    }


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
    con_ofertas: Annotated[
        bool, Query(description="Incluye el arreglo `ofertas` de cada producto de la pagina")
    ] = False,
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
        filas = list(await conexion.execute(_paginar(consulta, pagina, por_pagina)))
        datos = [_producto_publico(f) for f in filas]

        # `con_ofertas` expande la pagina, no el catalogo. La comparacion de
        # precio entre tiendas es el nucleo de la propuesta y una pantalla que
        # la pinte necesita las ofertas de todo lo que muestra; pedirlas una a
        # una serian `por_pagina` idas y vueltas. Sigue acotado por el mismo
        # tope de pagina, asi que el dia que el catalogo tenga 26.000
        # productos esta respuesta pesa lo mismo que hoy.
        if con_ofertas and filas:
            por_producto: dict[Any, list[dict[str, Any]]] = {}
            for oferta in await conexion.execute(_consulta_ofertas([f.id for f in filas])):
                por_producto.setdefault(oferta.pid, []).append(_oferta_publica(oferta))
            for producto, fila in zip(datos, filas, strict=True):
                producto["ofertas"] = _ordenar_ofertas(por_producto.get(fila.id, []))

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


@app.get(
    "/interno/resolver-sku/{sku}",
    tags=["interno"],
    include_in_schema=False,
    summary="sku -> (id canonico, precio) para Comercio; NO es publica",
)
async def resolver_sku(sku: str) -> dict[str, Any]:
    """El id canonico y el precio de un sku, para que Comercio congele la linea.

    Vive fuera de `/v1/catalogo` A PROPOSITO: la puerta rutea por ese prefijo,
    asi que esta ruta no existe hacia el navegador (RPO cero, ADR 0017) y solo
    la alcanza otro servicio que hable con Catalogo directo. Es la MISMA lectura
    que `precio_de` hace hoy, mas el id que la orden necesita y la superficie
    publica nunca expone.
    """
    precio_min = _precio_minimo_vigente()
    async with app.state.motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(_consulta_productos(precio_min).where(PRODUCTO.c.sku_interno == sku))
        ).one_or_none()
    if fila is None:
        raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
    return {"producto_canonico_id": str(fila.id), "precio_desde": pesos(getattr(fila, "centavos", None))}


@app.get(
    "/interno/listas-por-contacto/{contacto_referencia}",
    tags=["interno"],
    include_in_schema=False,
    summary="Las listas que subio un acudiente, por su usuario_id; NO es publica",
)
async def listas_por_contacto(contacto_referencia: uuid.UUID) -> dict[str, Any]:
    """Las listas subidas de un acudiente, para su panel "Mis solicitudes".

    Vive fuera de `/v1/` A PROPOSITO —igual que `resolver_sku`—: la puerta rutea
    por prefijo, asi que esta ruta no existe hacia el navegador (nadie de fuera
    pide "las listas de un contacto") y solo la alcanza Inteligencia hablando con
    Catalogo directo, con el `usuario_id` de la sesion que ya valido.

    Una fila por VERSION (gana la tarea mas reciente de cada version); una tarea
    sin version todavia —sugerencia aun pendiente— tambien sale, como recibida.
    `colegio_nombre` viene de `colegio_datos` cuando el colegio es nuevo; para un
    colegio aliado es `None` (su nombre vive en identidad, no aca) y lo resuelve
    la web.
    """
    consulta = (
        select(
            TAREA.c.id,
            TAREA.c.version_id,
            TAREA.c.colegio_id,
            TAREA.c.grado,
            TAREA.c.anio_lectivo,
            TAREA.c.colegio_datos,
            TAREA.c.creada_en,
            VERSION.c.revisada_en,
        )
        .select_from(TAREA.outerjoin(VERSION, VERSION.c.id == TAREA.c.version_id))
        .where(TAREA.c.contacto_referencia == contacto_referencia)
        .order_by(TAREA.c.creada_en.desc())
    )
    async with app.state.motor.engine.begin() as conexion:
        filas = list(await conexion.execute(consulta))

    # Una sola fila por version (la tarea mas reciente ya viene primero por el
    # orden). Las tareas sin version aun no comparten identidad: cada una es su
    # propia solicitud, asi que se llavean por su id.
    vistas: set[str] = set()
    listas: list[dict[str, Any]] = []
    for f in filas:
        clave = str(f.version_id) if f.version_id else f"tarea:{f.id}"
        if clave in vistas:
            continue
        vistas.add(clave)
        nombre = None
        if f.colegio_datos:
            nombre = dict(f.colegio_datos).get("nombre")
        listas.append(
            {
                "version_id": str(f.version_id) if f.version_id else None,
                "colegio_id": str(f.colegio_id) if f.colegio_id else None,
                "colegio_nombre": nombre,
                "grado": f.grado,
                "anio_lectivo": f.anio_lectivo,
                "revisada_en": f.revisada_en.isoformat() if f.revisada_en else None,
                "creada_en": f.creada_en.isoformat() if f.creada_en else None,
            }
        )
    return {"listas": listas}


# ---------------------------------------------------------------------------
# Escritura de productos (la mano de la persona que cura el catalogo)
# ---------------------------------------------------------------------------
#
# Vive en `api.py` y NO en `admin_http` a proposito, contra lo que hace la
# revision de listas: los productos ya viven aqui —`GET /v1/catalogo/productos`
# los lista y `GET .../{sku}` los muestra—, y el SPA lee y escribe contra el
# mismo prefijo. Poner la escritura en `/v1/admin` obligaria al SPA a hablar con
# dos origenes para la misma entidad y a mantener dos formas del producto en vez
# de reusar `_producto_publico`. La promesa de "solo lectura" del encabezado del
# modulo se refiere a que ninguna busqueda da de alta catalogo sin una persona:
# estas rutas SON esa persona.

# Los campos que una persona puede tocar por PATCH. El concepto NO esta: se
# reasigna por su propia ruta (`/reclasificar`) porque arrastra la invalidacion
# del vector y no es una edicion de texto mas. `sku`, `id`, `curado_*` y
# `embedding*` no se listan porque no se editan: cambiarlos rompe la identidad
# del producto o la huella del canal semantico.
_CAMPOS_EDITABLES = frozenset(
    {
        "nombre",
        "descripcion",
        "marca",
        "nivel",
        "personaje",
        "imagen_url",
        "unidad_base",
        "unidades_por_empaque",
        "atributos",
        "quality_score",
        "es_propio",
    }
)

_UNIDADES_BASE = ("unidad", "hoja", "pliego", "metro", "gramo", "mililitro")

# Cambiar uno de estos cambia el texto del que sale el embedding, asi que hay
# que invalidar `texto_embedding` para que `enriquecer` lo recalcule. El resto
# (marca, precio, imagen) no alimenta el vector y no gasta una re-embebida.
_CAMPOS_QUE_REEMBEBEN = frozenset({"nombre", "atributos"})


def _validar_edicion(cambios: dict[str, Any]) -> None:
    """Los mismos CHECK del modelo, dichos en el borde como error de dominio.

    Se rechaza antes de que la base lo grite para que el mensaje nombre el campo
    y el SPA lo pinte donde toca. Un cuerpo con una clave que no se edita es un
    400 que la nombra: es un error del cliente, no un dato que se ignora en
    silencio (ignorarlo dejaria creer que se guardo).
    """
    for campo in cambios:
        if campo not in _CAMPOS_EDITABLES:
            raise ErrorDominio(
                "campo_no_editable",
                f"El campo {campo} no se edita por esta ruta.",
                campo=campo,
            )
    if "nivel" in cambios and cambios["nivel"] not in _ORDEN_NIVEL:
        raise ErrorDominio(
            "nivel_invalido", f"El nivel debe ser uno de {', '.join(_ORDEN_NIVEL)}.", campo="nivel"
        )
    if "unidad_base" in cambios and cambios["unidad_base"] not in _UNIDADES_BASE:
        raise ErrorDominio(
            "unidad_base_invalida",
            f"La unidad base debe ser una de {', '.join(_UNIDADES_BASE)}.",
            campo="unidad_base",
        )
    if "unidades_por_empaque" in cambios and int(cambios["unidades_por_empaque"]) < 1:
        raise ErrorDominio(
            "empaque_invalido",
            "Las unidades por empaque tienen que ser al menos 1.",
            campo="unidades_por_empaque",
        )
    if "quality_score" in cambios and not (0 <= float(cambios["quality_score"]) <= 1):
        raise ErrorDominio(
            "quality_score_invalido", "El quality_score va entre 0 y 1.", campo="quality_score"
        )
    if "atributos" in cambios:
        # Los atributos son un mapa de valores ESCALARES (str/int/float/bool o
        # null): el tipo lo fija el cliente y el backend solo lo endurece. Una
        # lista o un dict anidado es basura que no se persiste; se nombra la
        # clave ofensora. bool es subclase de int en Python: ambos valen.
        for clave, valor in (cambios["atributos"] or {}).items():
            if valor is not None and not isinstance(valor, (str, int, float)):
                raise ErrorDominio(
                    "atributos_invalido",
                    f"El atributo '{clave}' debe ser un valor simple.",
                    estado=422,
                    campo="atributos",
                )


async def _producto_por_sku(conexion: Any, sku: str) -> dict[str, Any]:
    """Re-lee el producto en su forma publica, con precio y tiendas, o 404.

    La misma consulta que `ver_producto`/`listar_productos`, para que lo que
    devuelve una escritura coincida clave por clave con lo que el SPA ya
    pinta. El precio_desde y el conteo de tiendas salen igual que en la lectura.
    """
    precio_min = _precio_minimo_vigente()
    fila = (
        await conexion.execute(_consulta_productos(precio_min).where(PRODUCTO.c.sku_interno == sku))
    ).one_or_none()
    if fila is None:
        raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
    return _producto_publico(fila)


@app.patch(
    "/v1/catalogo/productos/{sku}",
    tags=["catalogo"],
    summary="Edita los campos de un producto. No reasigna concepto ni escribe embedding.",
)
async def editar_producto(sku: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Edicion parcial de un producto por su sku, con los CHECK del modelo.

    Cuando cambia lo que alimenta el vector (nombre o atributos) se invalida
    `texto_embedding` a NULL en la misma transaccion, PERO no se llama a Gemini
    aqui: el camino de la peticion no sale a la red. El siguiente `enriquecer`
    ve el NULL y re-embebe. Devuelve la forma publica ya con precio y tiendas.
    """
    _validar_edicion(cuerpo)
    valores = {c: cuerpo[c] for c in cuerpo}
    if _CAMPOS_QUE_REEMBEBEN & valores.keys():
        valores["texto_embedding"] = None

    async with app.state.motor.engine.begin() as conexion:
        existe = await conexion.scalar(select(PRODUCTO.c.id).where(PRODUCTO.c.sku_interno == sku))
        if existe is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
        if valores:
            await conexion.execute(update(PRODUCTO).where(PRODUCTO.c.sku_interno == sku).values(**valores))
        return await _producto_por_sku(conexion, sku)


@app.post(
    "/v1/catalogo/productos/{sku}/reclasificar",
    tags=["catalogo"],
    summary="Reasigna el concepto de un producto. Invalida su embedding.",
)
async def reclasificar_producto(sku: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Mueve un producto a otro concepto por el codigo del concepto.

    Va aparte del PATCH porque cambiar el concepto cambia el texto del que sale
    el vector: se invalida `texto_embedding` a NULL (no se re-embebe aqui). El
    concepto se busca por su codigo; si no existe es 404, no un 400 de campo,
    porque el recurso destino no esta.
    """
    codigo = cuerpo.get("concepto")
    async with app.state.motor.engine.begin() as conexion:
        pid = await conexion.scalar(select(PRODUCTO.c.id).where(PRODUCTO.c.sku_interno == sku))
        if pid is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
        cid = await conexion.scalar(select(CONCEPTO.c.id).where(CONCEPTO.c.codigo == codigo))
        if cid is None:
            raise ErrorDominio(
                "concepto_no_existe", f"No hay ningun concepto con el codigo {codigo}.", estado=404
            )
        await conexion.execute(
            update(PRODUCTO)
            .where(PRODUCTO.c.sku_interno == sku)
            .values(concepto_id=cid, texto_embedding=None)
        )
        return await _producto_por_sku(conexion, sku)


@app.delete(
    "/v1/catalogo/productos/{sku}",
    status_code=204,
    tags=["catalogo"],
    summary="Retira un producto del catalogo (soft delete: activo=False).",
)
async def retirar_producto(sku: str) -> Response:
    """Baja logica, nunca fisica: `activo=False`, no un DELETE.

    Las ofertas y los precios cuelgan del producto; un borrado fisico los
    dejaria huerfanos o los arrastraria. Poner `activo=False` lo saca de toda
    la lectura publica (que filtra por `activo`) sin perder el historial. Es
    idempotente: retirar dos veces sigue siendo 204; solo un sku que nunca
    existio es 404.
    """
    async with app.state.motor.engine.begin() as conexion:
        pid = await conexion.scalar(select(PRODUCTO.c.id).where(PRODUCTO.c.sku_interno == sku))
        if pid is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
        await conexion.execute(update(PRODUCTO).where(PRODUCTO.c.sku_interno == sku).values(activo=False))
    return Response(status_code=204)


@app.get(
    "/v1/catalogo/personajes",
    tags=["catalogo"],
    summary="Los personajes en existencia, con cuantos productos y en que conceptos",
)
async def listar_personajes() -> dict[str, Any]:
    """Enumera los personajes con producto activo, su conteo y sus conceptos.

    Alimenta el selector del empezar (P4b) y el re-etiquetado del SPA (P4c). NO
    calcula el gate de los cuatro anclas (C001/C009/C011/C086): esa completitud
    es de la UI. Solo dice que personajes hay, cuantos productos tiene cada uno
    y en que conceptos aparecen, para que el SPA compute el gate sin otra
    llamada. Es una sola consulta agrupada por personaje/concepto.
    """
    async with app.state.motor.engine.begin() as conexion:
        filas = await conexion.execute(
            select(
                PRODUCTO.c.personaje,
                CONCEPTO.c.codigo.label("concepto_codigo"),
                func.count().label("productos"),
            )
            .select_from(PRODUCTO.join(CONCEPTO, CONCEPTO.c.id == PRODUCTO.c.concepto_id))
            .where(PRODUCTO.c.activo.is_(True), PRODUCTO.c.personaje.is_not(None))
            .group_by(PRODUCTO.c.personaje, CONCEPTO.c.codigo)
        )
        # Se agrupa por (personaje, concepto) en SQL y se pliega en Python: el
        # conteo de productos del personaje es la suma sobre sus conceptos, y
        # los codigos de concepto salen de las mismas filas sin una segunda
        # consulta.
        por_personaje: dict[str, dict[str, Any]] = {}
        for fila in filas:
            entrada = por_personaje.setdefault(
                fila.personaje, {"nombre": fila.personaje, "productos": 0, "conceptos": []}
            )
            entrada["productos"] += int(fila.productos)
            entrada["conceptos"].append(fila.concepto_codigo)
    personajes = sorted(por_personaje.values(), key=lambda p: p["nombre"])
    return {"personajes": personajes}


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
    revisada: Annotated[
        bool | None,
        Query(description="Solo listas verificadas (true) o solo pendientes (false)"),
    ] = None,
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
    # `revisada` es un derivado de `revisada_en IS NULL`; se filtra aqui para
    # que el selector del acudiente pida `?revisada=true` y no traiga las
    # pendientes solo para descartarlas en el navegador.
    if revisada is True:
        consulta = consulta.where(VERSION.c.revisada_en.is_not(None))
    elif revisada is False:
        consulta = consulta.where(VERSION.c.revisada_en.is_(None))

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
    from .consulta import _embeder_por_entorno, calcular_vectores, cargar_indice, emparejar

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

    textos = [str(r) for r in renglones]
    # El motor del servicio (su pool) trae la conexion; `cargar_indice` es la
    # unica copia de la consulta y SI carga embeddings, asi que el canal
    # semantico de OE3 corre aqui igual que en la CLI. El vector del renglon se
    # calcula en un solo lote (una peticion) y degrada a lexico si no hay clave
    # o el proveedor falla — misma contrato que `emparejar_en_catalogo`.
    async with app.state.motor.engine.begin() as conexion:
        conceptos, productos = await cargar_indice(conexion)
    vectores = calcular_vectores(textos, _embeder_por_entorno())
    resultados = [
        emparejar(t, conceptos, productos, embedding_renglon=v) for t, v in zip(textos, vectores, strict=True)
    ]
    return {"total": len(resultados), "emparejamientos": [r.a_dict() for r in resultados]}


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de lectura del catalogo.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    # Se arranca por CADENA DE IMPORTACION, no pasando `app`, a proposito. Con
    # `python -m tukit_catalogo.api` este archivo es `__main__`, y uvicorn
    # correria el lifespan sobre `__main__.app`. Pero `admin_http._motor()` hace
    # `from .api import app`, que importa `tukit_catalogo.api` como OTRO modulo:
    # una segunda `app` cuyo lifespan nunca corrio y cuyo `state.motor` no
    # existe (de ahi el 500 en `/v1/admin/*`). Nombrar el modulo canonico hace
    # que uvicorn importe esa misma `tukit_catalogo.api`, corra su lifespan y
    # sea la que `admin_http` ve: una sola `app`, un solo motor.
    uvicorn.run("tukit_catalogo.api:app", host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
