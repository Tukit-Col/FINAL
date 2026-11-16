"""Las rutas de lectura del catalogo y la escritura de un producto.

Parsea la peticion, arma el repo sobre la conexion de la unidad de trabajo,
pasa las filas por los shapers puros de `dominio/catalogo.py` y traduce el
"no existe" a un `ErrorDominio` 404 (ADR 0019). El SQL vive en
`repositorios/catalogo.py`; aqui no hay `select`/`update`.

Tres superficies de la seccion 12 del contrato:

- **Catalogo** (`/v1/catalogo/*`): conceptos, productos canonicos con su nivel y
  personaje, ofertas por tienda con precio; mas la mano de la persona que cura
  (editar, reclasificar, retirar un producto), que vive aqui y no en `/v1/admin`
  porque el SPA lee y escribe el producto contra el mismo prefijo.
- **Listas** (`/v1/listas*`): las listas oficiales publicadas, ya resueltas a
  concepto.
- **Interno** (`/interno/resolver-sku`): sku -> (id, precio) para Comercio, fuera
  del prefijo publico a proposito (la puerta no la expone, RPO cero ADR 0017).

`/v1/catalogo/emparejar` es el unico que no toca el repo: reusa `consulta` (el
canal semantico de OE3) sobre la conexion, y no escribe nada.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel
from tukit_comun.http import ErrorDominio

from ..dominio.catalogo import (
    _CAMPOS_QUE_REEMBEBEN,
    _ORDEN_NIVEL,
    _concepto_publico,
    _oferta_publica,
    _ordenar_ofertas,
    _producto_publico,
    _sobre,
    _validar_edicion,
    pesos,
)
from ..repositorios import RepoCatalogo

router = APIRouter()

# Tope duro del tamano de pagina. No es una manía de rendimiento: sin el, un
# cliente puede pedir las 261 filas con sus ofertas y sus precios en una sola
# respuesta, y el dia que el catalogo tenga 26.000 la misma llamada tumba la
# pantalla sin que nada haya cambiado en el codigo del frontend.
POR_PAGINA_MAXIMO = 200
POR_PAGINA_POR_OMISION = 50


# ---------------------------------------------------------------------------
# Conceptos
# ---------------------------------------------------------------------------


@router.get(
    "/v1/catalogo/resumen",
    tags=["catalogo"],
    summary="Las siete cifras que resumen el estado del catalogo curado",
)
async def resumen_catalogo(peticion: Request) -> dict[str, Any]:
    """El encabezado de la pantalla de catalogo, en una sola consulta.

    No es una comodidad: es la unica cifra que NO se puede derivar de las
    colecciones paginadas. Un cliente que solo tuviera `/productos` sabria
    cuantos hay en su pagina, no cuantos hay con foto en las 385, y para
    averiguarlo tendria que traerse el catalogo entero, que es exactamente lo
    que la paginacion existe para impedir. Sin esta ruta, el tope de pagina y
    la pantalla se contradicen.
    """
    async with peticion.app.state.motor.sesion() as db:
        return await RepoCatalogo(await db.connection()).resumen()


@router.get(
    "/v1/catalogo/categorias",
    tags=["catalogo"],
    summary="Las categorias con cuantos conceptos tiene cada una",
)
async def categorias(peticion: Request) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        filas = await RepoCatalogo(await db.connection()).categorias()
    datos = [{"categoria": f.categoria, "conceptos": int(f.conceptos)} for f in filas]
    return {"total": len(datos), "categorias": datos}


@router.get("/v1/catalogo/conceptos", tags=["catalogo"], summary="Conceptos del catalogo, paginados")
async def listar_conceptos(
    peticion: Request,
    categoria: Annotated[str | None, Query(description="Filtra por categoria exacta")] = None,
    tipo_item: Annotated[str | None, Query(description="util, texto, libro_libre, ...")] = None,
    busqueda: Annotated[str | None, Query(description="Texto en el nombre o en los sinonimos")] = None,
    con_producto: Annotated[bool | None, Query(description="Solo los que tienen algun producto")] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAXIMO)] = POR_PAGINA_POR_OMISION,
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        total, filas = await RepoCatalogo(await db.connection()).listar_conceptos(
            categoria=categoria,
            tipo_item=tipo_item,
            busqueda=busqueda,
            con_producto=con_producto,
            pagina=pagina,
            por_pagina=por_pagina,
        )
    datos = [
        _concepto_publico(f) | {"productos": int(f.productos), "niveles_disponibles": int(f.niveles)}
        for f in filas
    ]
    return _sobre(pagina, por_pagina, total, "conceptos", datos)


@router.get(
    "/v1/catalogo/conceptos/{codigo}",
    tags=["catalogo"],
    summary="Un concepto con sus productos, uno por nivel disponible",
)
async def ver_concepto(peticion: Request, codigo: str) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        fila, productos = await RepoCatalogo(await db.connection()).ver_concepto(codigo)
    if fila is None:
        raise ErrorDominio(
            "concepto_no_existe",
            f"No hay ningun concepto con el codigo {codigo}.",
            estado=404,
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


@router.get("/v1/catalogo/productos", tags=["catalogo"], summary="Productos canonicos, paginados")
async def listar_productos(
    peticion: Request,
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

    async with peticion.app.state.motor.sesion() as db:
        total, filas, ofertas_por_pid = await RepoCatalogo(await db.connection()).listar_productos(
            concepto=concepto,
            nivel=nivel,
            personaje=personaje,
            con_personaje=con_personaje,
            busqueda=busqueda,
            con_precio=con_precio,
            con_ofertas=con_ofertas,
            pagina=pagina,
            por_pagina=por_pagina,
        )

    datos = [_producto_publico(f) for f in filas]
    if con_ofertas:
        for producto, fila in zip(datos, filas, strict=True):
            crudas = [_oferta_publica(o) for o in ofertas_por_pid.get(fila.id, [])]
            producto["ofertas"] = _ordenar_ofertas(crudas)
    return _sobre(pagina, por_pagina, total, "productos", datos)


@router.get(
    "/v1/catalogo/productos/{sku}",
    tags=["catalogo"],
    summary="Un producto con TODAS sus ofertas, para comparar precio entre tiendas",
)
async def ver_producto(peticion: Request, sku: str) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        fila, ofertas = await RepoCatalogo(await db.connection()).ver_producto(sku)
    if fila is None:
        raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)

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


@router.get(
    "/interno/resolver-sku/{sku}",
    tags=["interno"],
    include_in_schema=False,
    summary="sku -> (id canonico, precio) para Comercio; NO es publica",
)
async def resolver_sku(peticion: Request, sku: str) -> dict[str, Any]:
    """El id canonico y el precio de un sku, para que Comercio congele la linea.

    Vive fuera de `/v1/catalogo` A PROPOSITO: la puerta rutea por ese prefijo,
    asi que esta ruta no existe hacia el navegador (RPO cero, ADR 0017) y solo
    la alcanza otro servicio que hable con Catalogo directo. Es la MISMA lectura
    que `precio_de` hace hoy, mas el id que la orden necesita y la superficie
    publica nunca expone.
    """
    async with peticion.app.state.motor.sesion() as db:
        fila = await RepoCatalogo(await db.connection()).producto_por_sku(sku)
    if fila is None:
        raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
    return {"producto_canonico_id": str(fila.id), "precio_desde": pesos(getattr(fila, "centavos", None))}


@router.get(
    "/interno/listas-por-contacto/{contacto_referencia}",
    tags=["interno"],
    include_in_schema=False,
    summary="Las listas que subio un acudiente, por su usuario_id; NO es publica",
)
async def listas_por_contacto(peticion: Request, contacto_referencia: uuid.UUID) -> dict[str, Any]:
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
    async with peticion.app.state.motor.sesion() as db:
        filas = await RepoCatalogo(await db.connection()).tareas_por_contacto(contacto_referencia)

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
                # La tarea mas reciente de la fila: es con lo que el acudiente
                # cancela su solicitud (`retirar_de_contacto`).
                "tarea_id": str(f.id),
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


class RetiroDeContacto(BaseModel):
    """Que solicitud deja de ser del acudiente: una tarea o toda una version."""

    tarea_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None


@router.post(
    "/interno/listas-por-contacto/{contacto_referencia}/retirar",
    tags=["interno"],
    include_in_schema=False,
    summary="El acudiente cancela una lista que subio: deja de ser suya; NO es publica",
)
async def retirar_de_contacto(
    peticion: Request, contacto_referencia: uuid.UUID, cuerpo: RetiroDeContacto
) -> dict[str, Any]:
    """Desvincula al acudiente de una lista que subio, sin borrar la lista.

    Es la mitad del Catalogo de "cancelar solicitud": la lista sigue siendo una
    lista oficial del colegio (otra persona la puede curar y aprobar), pero ya no
    sale en "Mis solicitudes" y, al aprobarse, no le arma un kit a nadie (el
    poller exige `contacto_referencia`). Se desvinculan TODAS las tareas del
    contacto en esa version —la fila que el acudiente ve agrupa varias—.

    Como `listas_por_contacto`, vive en `/interno`: el `contacto_referencia` lo
    pone Inteligencia con el `usuario_id` de una sesion que ya valido.
    """
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoCatalogo(await db.connection())
        retiradas = await repo.retirar_de_contacto(contacto_referencia, cuerpo.tarea_id, cuerpo.version_id)
    return {"retiradas": retiradas}


# ---------------------------------------------------------------------------
# Escritura de productos (la mano de la persona que cura el catalogo)
# ---------------------------------------------------------------------------
#
# Vive aqui y NO en `admin_http` a proposito, contra lo que hace la revision de
# listas: los productos ya se leen por este prefijo, y el SPA lee y escribe
# contra el mismo origen para reusar `_producto_publico`. La promesa de "solo
# lectura" del modulo se refiere a que ninguna busqueda da de alta catalogo sin
# una persona: estas rutas SON esa persona.


async def _refrescar_producto(repo: RepoCatalogo, sku: str) -> dict[str, Any]:
    """Re-lee el producto en su forma publica tras una escritura, o 404.

    La misma consulta que la lectura, para que lo que devuelve una escritura
    coincida clave por clave con lo que el SPA ya pinta.
    """
    fila = await repo.producto_por_sku(sku)
    if fila is None:
        raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
    return _producto_publico(fila)


@router.patch(
    "/v1/catalogo/productos/{sku}",
    tags=["catalogo"],
    summary="Edita los campos de un producto. No reasigna concepto ni escribe embedding.",
)
async def editar_producto(peticion: Request, sku: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
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

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoCatalogo(await db.connection())
        if await repo.existe_producto(sku) is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
        await repo.actualizar_producto(sku, valores)
        return await _refrescar_producto(repo, sku)


@router.post(
    "/v1/catalogo/productos/{sku}/reclasificar",
    tags=["catalogo"],
    summary="Reasigna el concepto de un producto. Invalida su embedding.",
)
async def reclasificar_producto(peticion: Request, sku: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """Mueve un producto a otro concepto por el codigo del concepto.

    Va aparte del PATCH porque cambiar el concepto cambia el texto del que sale
    el vector: se invalida `texto_embedding` a NULL (no se re-embebe aqui). El
    concepto se busca por su codigo; si no existe es 404, no un 400 de campo,
    porque el recurso destino no esta.
    """
    codigo = cuerpo.get("concepto")
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoCatalogo(await db.connection())
        if await repo.existe_producto(sku) is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
        cid = await repo.concepto_id_por_codigo(codigo)
        if cid is None:
            raise ErrorDominio(
                "concepto_no_existe", f"No hay ningun concepto con el codigo {codigo}.", estado=404
            )
        nuevo_sku = await repo.reclasificar_producto(sku, cid, str(codigo))
        return await _refrescar_producto(repo, nuevo_sku)


@router.delete(
    "/v1/catalogo/productos/{sku}",
    status_code=204,
    tags=["catalogo"],
    summary="Retira un producto del catalogo (soft delete: activo=False).",
)
async def retirar_producto(peticion: Request, sku: str) -> Response:
    """Baja logica, nunca fisica: `activo=False`, no un DELETE.

    Las ofertas y los precios cuelgan del producto; un borrado fisico los
    dejaria huerfanos o los arrastraria. Poner `activo=False` lo saca de toda
    la lectura publica (que filtra por `activo`) sin perder el historial. Es
    idempotente: retirar dos veces sigue siendo 204; solo un sku que nunca
    existio es 404.
    """
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoCatalogo(await db.connection())
        if await repo.existe_producto(sku) is None:
            raise ErrorDominio("producto_no_existe", f"No hay ningun producto con el sku {sku}.", estado=404)
        await repo.retirar_producto(sku)
    return Response(status_code=204)


@router.get(
    "/v1/catalogo/personajes",
    tags=["catalogo"],
    summary="Los personajes en existencia, con cuantos productos y en que conceptos",
)
async def listar_personajes(peticion: Request) -> dict[str, Any]:
    """Enumera los personajes con producto activo, su conteo y sus conceptos.

    Alimenta el selector del empezar (P4b) y el re-etiquetado del SPA (P4c). NO
    calcula el gate de los cuatro anclas (C001/C009/C011/C086): esa completitud
    es de la UI. Solo dice que personajes hay, cuantos productos tiene cada uno
    y en que conceptos aparecen, para que el SPA compute el gate sin otra
    llamada.
    """
    async with peticion.app.state.motor.sesion() as db:
        filas = await RepoCatalogo(await db.connection()).listar_personajes()
    # Se agrupa por (personaje, concepto) en SQL y se pliega en Python: el
    # conteo de productos del personaje es la suma sobre sus conceptos, y los
    # codigos de concepto salen de las mismas filas sin una segunda consulta.
    por_personaje: dict[str, dict[str, Any]] = {}
    for fila in filas:
        entrada = por_personaje.setdefault(
            fila.personaje, {"nombre": fila.personaje, "productos": 0, "conceptos": []}
        )
        entrada["productos"] += int(fila.productos)
        entrada["conceptos"].append(fila.concepto_codigo)
    personajes = sorted(por_personaje.values(), key=lambda p: p["nombre"])
    return {"personajes": personajes}


@router.get("/v1/catalogo/tiendas", tags=["catalogo"], summary="Las tiendas con oferta viva en el catalogo")
async def listar_tiendas(peticion: Request) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        filas = await RepoCatalogo(await db.connection()).listar_tiendas()
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


@router.get(
    "/v1/listas", tags=["listas"], summary="Listas oficiales publicadas, filtrables por colegio y grado"
)
async def listar_listas(
    peticion: Request,
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
    async with peticion.app.state.motor.sesion() as db:
        total, filas = await RepoCatalogo(await db.connection()).listar_listas(
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio_lectivo,
            revisada=revisada,
            pagina=pagina,
            por_pagina=por_pagina,
        )
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
            # Que este sin revisar no es un defecto: es la puerta que habilita
            # salir a una tienda por lo que la lista pide y el catalogo no
            # tiene. Una vez revisada, no se vuelve a abrir.
            "revisada": f.revisada_en is not None,
            "items": int(f.renglones),
        }
        for f in filas
    ]
    return _sobre(pagina, por_pagina, total, "listas", datos)


@router.get(
    "/v1/listas/{lista_id}",
    tags=["listas"],
    summary="Los renglones de la version vigente de una lista, ya resueltos a concepto",
)
async def ver_lista(peticion: Request, lista_id: uuid.UUID) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        cabeza, filas = await RepoCatalogo(await db.connection()).ver_lista(lista_id)
    if cabeza is None:
        raise ErrorDominio(
            "lista_no_existe",
            "No hay ninguna lista con ese identificador, o su version vigente falta.",
            estado=404,
        )
    items = [
        {
            "item_id": str(f.id),
            "orden": int(f.orden),
            "texto_original": f.texto_original,
            "cantidad": int(f.cantidad),
            "unidad": f.unidad,
            # Nulo en el renglon significa "lo que diga el concepto", NO `util`.
            # Se resuelve aqui para que el cliente no reimplemente la regla, y se
            # conservan los dos campos para que se vea de donde salio.
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


@router.post(
    "/v1/catalogo/emparejar",
    tags=["catalogo"],
    summary="Empareja renglones de lista contra el catalogo. No escribe nada.",
)
async def emparejar_renglones(peticion: Request, cuerpo: dict[str, Any]) -> dict[str, Any]:
    """La misma decision que `consulta.emparejar`, expuesta por HTTP.

    Existe porque `inteligencia` no puede ver esta base ni importar este
    paquete (invariantes 1 y 3), y sin embargo la etapa de resolucion de su
    pipeline necesita exactamente esto. No escribe: es el match del acudiente, y
    ese camino no sale a la red ni da nada de alta. Lo que da de alta es
    `descubrir`, y solo a traves de una version de lista sin revisar.
    """
    from ..consulta import _embeder_por_entorno, calcular_vectores, cargar_indice, emparejar

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
    # calcula en un solo lote y degrada a lexico si no hay clave o el proveedor
    # falla — mismo contrato que `emparejar_en_catalogo`.
    async with peticion.app.state.motor.sesion() as db:
        conceptos, productos = await cargar_indice(await db.connection())
    # `conceptos` es opcional y va en paralelo a `renglones`: el codigo que una
    # persona ya asigno a ese renglon (o null). Si no cuadra en largo, se ignora.
    asignados = cuerpo.get("conceptos")
    if not isinstance(asignados, list) or len(asignados) != len(textos):
        asignados = [None] * len(textos)
    # `app.state.embeder` es la costura de las pruebas, como `app.state.motor`;
    # sin ella se resuelve por entorno.
    embeder = getattr(peticion.app.state, "embeder", None) or _embeder_por_entorno()
    vectores = await calcular_vectores(textos, embeder)
    resultados = [
        emparejar(t, conceptos, productos, embedding_renglon=v, concepto_forzado=(str(a) if a else None))
        for t, v, a in zip(textos, vectores, asignados, strict=True)
    ]
    return {"total": len(resultados), "emparejamientos": [r.a_dict() for r in resultados]}
