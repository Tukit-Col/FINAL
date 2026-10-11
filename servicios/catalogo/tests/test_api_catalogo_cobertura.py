"""NFR-MAN-01: rutas del catalogo que ninguna prueba HTTP ejercia, y el SKU que nunca se inventa.

`test_api_catalogo` y `test_api_productos` cubren navegar conceptos y productos.
Este archivo cierra lo que quedaba sin llamar, y cada pieza guarda una promesa:

  - `/resumen` y `/categorias` son el encabezado de la consola; no se pueden
    derivar de las colecciones paginadas, asi que un conteo inflado por lo
    apagado se ve como un catalogo mas completo de lo que es;
  - `productos?con_ofertas=true` expande la pagina con las ofertas vivas, las
    de precio de menor a mayor y la que no tiene precio al final (existe, pero
    no se compara);
  - `/interno/resolver-sku` es lo que Comercio usa para congelar la linea: el id
    canonico y el precio de un SKU, y 404 si el SKU no existe o esta retirado;
  - editar o reclasificar un producto RETIRADO responde 404 y no persiste nada
    (la transaccion se revierte), aunque el SQL de existencia no filtre `activo`;
  - restriccion dura del producto: `emparejar` solo ofrece SKU que existen y
    estan activos en `producto_canonico`, con o sin canal semantico, y degrada a
    lexico si el proveedor de embeddings falla.

El embeder de Gemini nunca se usa: donde hace falta un vector se inyecta
`embeder_falso` (trigramas, sin red). Datos ficticios.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.api import app
from tukit_catalogo.embeddings import MODELO_FALSO, embeder_falso, texto_de_producto
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("dddddddd-dddd-5ddd-8ddd-dddddddddddd")
DESDE = datetime(2026, 2, 1, tzinfo=UTC)
TEXTO_PREVIO = "texto previo del embedding"


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """3 conceptos activos (+1 apagado), 3 productos activos (+1 retirado) y 3 tiendas.

    ECO tiene tres ofertas: Panamericana a 4500, Exito a 5000 y una tercera
    tienda sin ningun precio observado. El retirado (`TK-C001-RET`) tiene una
    oferta viva y un `texto_embedding` previo, para ver que nada lo toca.
    """
    cuaderno = Concepto(
        codigo="C001",
        nombre_canonico="cuaderno",
        categoria="Cuadernos",
        sinonimos=["cuaderno cuadriculado", "libreta"],
        atributos_discriminantes=["rayado"],
        frecuencia_demanda=17,
    )
    colores = Concepto(
        codigo="C002", nombre_canonico="colores", categoria="Arte", sinonimos=["lapices de colores"]
    )
    plan = Concepto(
        codigo="C003", nombre_canonico="plan lector", categoria="Lectura", tipo_item="licencia_digital"
    )
    viejo = Concepto(codigo="C004", nombre_canonico="cuaderno viejo", categoria="Cuadernos", activo=False)
    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    pana = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
    tercera = Tienda(slug="tercera", nombre="Tercera Tienda", tipo="minorista")
    sesion.add_all([cuaderno, colores, plan, viejo, exito, pana, tercera])
    sesion.flush()

    def _producto(concepto, sku, nombre, nivel, *, vector=False, **extra):
        texto = texto_de_producto(nombre, concepto.nombre_canonico, extra.get("atributos"))
        producto = ProductoCanonico(
            concepto_id=concepto.id,
            sku_interno=sku,
            nombre=nombre,
            nivel=nivel,
            curado_por=CURADOR,
            embedding=embeder_falso([texto])[0] if vector else None,
            embedding_model=MODELO_FALSO if vector else None,
            texto_embedding=texto if vector else extra.pop("texto_embedding", None),
            **extra,
        )
        sesion.add(producto)
        sesion.flush()
        return producto

    eco = _producto(
        cuaderno,
        "TK-C001-ECO",
        "Cuaderno cuadriculado economico",
        "economico",
        vector=True,
        atributos={"rayado": "cuadriculado"},
        imagen_url="https://e.test/eco.jpg",
        quality_score=0.9,
    )
    con = _producto(
        cuaderno,
        "TK-C001-CON",
        "Cuaderno cuadriculado confiable",
        "confiable",
        vector=True,
        atributos={"rayado": "cuadriculado"},
        imagen_url="https://e.test/con.jpg",
        quality_score=0.9,
    )
    col = _producto(colores, "TK-C002-CON", "Colores Faber x12", "confiable", quality_score=0.3)
    ret = _producto(
        cuaderno,
        "TK-C001-RET",
        "Cuaderno premium retirado",
        "premium",
        activo=False,
        texto_embedding=TEXTO_PREVIO,
    )

    def _oferta(producto, tienda, centavos):
        oferta = OfertaTienda(
            producto_canonico_id=producto.id,
            tienda_id=tienda.id,
            referencia_externa=f"{tienda.slug}-{producto.sku_interno}",
            url=f"https://{tienda.slug}.example.test/{producto.sku_interno}",
            metodo_vinculacion="manual",
            disponible=True,
        )
        sesion.add(oferta)
        sesion.flush()
        if centavos is not None:
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id, valor_centavos=centavos, fuente="scraper", vigente_desde=DESDE
                )
            )
        sesion.flush()

    _oferta(eco, exito, 500000)
    _oferta(eco, pana, 450000)
    _oferta(eco, tercera, None)
    _oferta(ret, exito, 700000)
    return {"eco": eco.id, "con": con.id, "col": col.id, "ret": ret.id, "cuaderno": cuaderno.id}


@pytest.fixture()
async def cliente():
    """La app contra SQLite en memoria; `cliente.ids` y `cliente.fabrica` dejan mirar la base."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        http.fabrica = fabrica  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


async def _producto_en_base(cliente, sku: str) -> ProductoCanonico:
    async with cliente.fabrica() as sesion:
        return (
            await sesion.execute(select(ProductoCanonico).where(ProductoCanonico.sku_interno == sku))
        ).scalar_one()


async def _skus_activos(cliente) -> set[str]:
    async with cliente.fabrica() as sesion:
        filas = await sesion.execute(
            select(ProductoCanonico.sku_interno).where(ProductoCanonico.activo.is_(True))
        )
        return {sku for (sku,) in filas}


# --- resumen y categorias ---------------------------------------------------------


async def test_el_resumen_cuenta_solo_lo_activo(cliente):
    """Las siete cifras ignoran el concepto apagado, el producto retirado y no cuentan sus ofertas."""
    respuesta = await cliente.get("/v1/catalogo/resumen")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "conceptos": 3,
        "productos": 3,
        "conceptos_con_tres_niveles": 0,  # C001 tiene dos niveles activos: el premium esta retirado
        "conceptos_sin_producto": 1,  # C003 (plan lector)
        "productos_con_foto": 2,
        "tiendas": 3,
        "productos_sin_revisar": 1,  # Colores Faber, con calidad 0,3
    }


async def test_las_categorias_se_agrupan_en_orden_y_el_concepto_apagado_no_suma(cliente):
    """`Cuadernos` cuenta 1 (el C004 apagado no suma) y la lista viene ordenada con su total."""
    respuesta = await cliente.get("/v1/catalogo/categorias")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "total": 3,
        "categorias": [
            {"categoria": "Arte", "conceptos": 1},
            {"categoria": "Cuadernos", "conceptos": 1},
            {"categoria": "Lectura", "conceptos": 1},
        ],
    }


# --- productos con ofertas -----------------------------------------------------------


async def test_con_ofertas_expande_la_pagina_con_las_de_menor_precio_primero_y_la_sin_precio_al_final(
    cliente,
):
    """ECO trae sus tres ofertas: 4500, 5000 y, al final, la tercera tienda que no reporta precio.

    La sin precio no se esconde (el acudiente puede ir a mirarla) pero tampoco
    compite en la comparacion. El producto sin ofertas trae la lista vacia.
    """
    respuesta = await cliente.get("/v1/catalogo/productos?concepto=C001&con_ofertas=true")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 2  # el retirado no cuenta
    por_sku = {p["sku"]: p for p in cuerpo["productos"]}
    ofertas = por_sku["TK-C001-ECO"]["ofertas"]
    assert [(o["tienda"], o["precio"]) for o in ofertas] == [
        ("panamericana", 4500),
        ("exito", 5000),
        ("tercera", None),
    ]
    assert ofertas[0]["url"].endswith("/TK-C001-ECO")
    assert ofertas[2]["vigente_desde"] is None
    assert por_sku["TK-C001-CON"]["ofertas"] == []
    assert "TK-C001-RET" not in por_sku


async def test_sin_con_ofertas_el_producto_no_trae_el_arreglo(cliente):
    """El valor por omision no expande: la clave `ofertas` no existe en la respuesta."""
    cuerpo = (await cliente.get("/v1/catalogo/productos?concepto=C001")).json()
    assert cuerpo["productos"]
    assert all("ofertas" not in p for p in cuerpo["productos"])


async def test_con_ofertas_y_sin_resultados_responde_vacio(cliente):
    """Una busqueda sin coincidencias con `con_ofertas` da una pagina vacia y no un error."""
    respuesta = await cliente.get("/v1/catalogo/productos?busqueda=nada-coincide&con_ofertas=true")

    assert respuesta.status_code == 200
    assert (respuesta.json()["total"], respuesta.json()["productos"]) == (0, [])


# --- resolver SKU (interno) ------------------------------------------------------------


async def test_resolver_sku_devuelve_el_id_canonico_y_el_precio_en_pesos(cliente):
    """Comercio congela la linea con el id canonico y el precio desde del SKU (el menor vigente)."""
    respuesta = await cliente.get("/interno/resolver-sku/TK-C001-ECO")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "producto_canonico_id": str(cliente.ids["eco"]),
        "precio_desde": 4500,
    }


async def test_resolver_sku_de_un_producto_sin_ofertas_da_precio_nulo_y_no_cero(cliente):
    """Sin ofertas el precio es `null` ("no se conoce"): un cero se sumaria al total sin ruido."""
    cuerpo = (await cliente.get("/interno/resolver-sku/TK-C001-CON")).json()
    assert cuerpo["precio_desde"] is None
    assert cuerpo["producto_canonico_id"] == str(cliente.ids["con"])


@pytest.mark.parametrize("sku", ["TK-C001-RET", "TK-NO-EXISTE"])
async def test_resolver_sku_de_uno_retirado_o_desconocido_es_404(cliente, sku):
    """El retirado no se puede comprar: se trata como si no existiera, con el error de dominio de siempre."""
    respuesta = await cliente.get(f"/interno/resolver-sku/{sku}")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "producto_no_existe"
    assert sku in respuesta.json()["mensaje"]


async def test_resolver_sku_no_se_publica_en_el_esquema(cliente):
    """Es una ruta entre servicios: no aparece en el OpenAPI que ve el navegador."""
    assert not any(ruta.startswith("/interno/") for ruta in app.openapi()["paths"])


# --- escribir sobre un producto retirado ---------------------------------------------------


async def test_editar_un_producto_retirado_es_404_y_no_deja_nada_escrito(cliente):
    """El PATCH de un retirado se rechaza y la transaccion se revierte: ni nombre nuevo ni embedding anulado.

    `existe_producto` no filtra por `activo`, asi que la actualizacion SI llega a
    ejecutarse; es la relectura publica la que no lo encuentra y levanta el 404.
    El `rollback` de la unidad de trabajo es lo que evita que un retirado cambie.
    """
    respuesta = await cliente.patch("/v1/catalogo/productos/TK-C001-RET", json={"nombre": "Nombre nuevo"})

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "producto_no_existe"
    en_base = await _producto_en_base(cliente, "TK-C001-RET")
    assert en_base.nombre == "Cuaderno premium retirado"
    assert en_base.texto_embedding == TEXTO_PREVIO
    assert en_base.activo is False


async def test_reclasificar_un_producto_retirado_es_404_y_conserva_su_concepto(cliente):
    """Lo mismo para reclasificar: el retirado sigue en su concepto y con su `texto_embedding`."""
    respuesta = await cliente.post(
        "/v1/catalogo/productos/TK-C001-RET/reclasificar", json={"concepto": "C002"}
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "producto_no_existe"
    en_base = await _producto_en_base(cliente, "TK-C001-RET")
    assert en_base.concepto_id == cliente.ids["cuaderno"]
    assert en_base.texto_embedding == TEXTO_PREVIO


async def test_reclasificar_un_producto_activo_lo_mueve_y_anula_su_embedding(cliente):
    """El camino feliz: el producto cambia de concepto, vuelve reclasificado y su texto se invalida.

    Desde 4dfdd99 el SKU de una semilla nombra su concepto y se re-acuna al moverla
    (repositorios/catalogo.py:399-417); `TK-C002-CON` ya existe, asi que lleva sufijo.
    """
    respuesta = await cliente.post(
        "/v1/catalogo/productos/TK-C001-CON/reclasificar", json={"concepto": "C002"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["concepto"]["codigo"] == "C002"
    assert respuesta.json()["sku"] == "TK-C002-CON-2"
    assert await _skus_activos(cliente) >= {"TK-C002-CON", "TK-C002-CON-2"}
    assert "TK-C001-CON" not in await _skus_activos(cliente)
    en_base = await _producto_en_base(cliente, "TK-C002-CON-2")
    assert en_base.texto_embedding is None
    assert en_base.embedding is not None  # no se re-embebe en la peticion: solo se invalida el texto


# --- emparejar: el SKU siempre existe -----------------------------------------------------------


RENGLONES_VARIADOS = [
    "2 cuadernos cuadriculados",
    "libreta",
    "lapices de colores x 12",
    "plan lector",
    "tijeras punta roma",
    "TK-C001-RET cuaderno premium retirado",
    "cuaderno viejo",
]


@pytest.mark.parametrize("con_embeder", [False, True], ids=["solo-lexico", "con-embeder-falso"])
async def test_emparejar_solo_ofrece_skus_que_existen_y_estan_activos(cliente, monkeypatch, con_embeder):
    """Restriccion dura: ningun renglon recibe un SKU inexistente o retirado, ni nombrando el retirado.

    Cada opcion ademas lleva el `producto_id` de ESE SKU en la base.
    """
    if con_embeder:
        monkeypatch.setattr("tukit_catalogo.consulta._embeder_por_entorno", lambda: embeder_falso)
    activos = await _skus_activos(cliente)

    respuesta = await cliente.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES_VARIADOS})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == len(RENGLONES_VARIADOS)
    ofrecidos = [o for e in cuerpo["emparejamientos"] for o in e["opciones"]]
    assert ofrecidos, "algun renglon debia reconocerse"
    assert {o["sku"] for o in ofrecidos} <= activos
    ids_por_sku = {sku: str((await _producto_en_base(cliente, sku)).id) for sku in activos}
    assert all(o["producto_id"] == ids_por_sku[o["sku"]] for o in ofrecidos)


async def test_emparejar_con_el_embeder_falso_conserva_el_orden_y_el_texto_de_cada_renglon(
    cliente, monkeypatch
):
    """Cada emparejamiento responde a su renglon, en el mismo orden, con el canal semantico encendido."""
    monkeypatch.setattr("tukit_catalogo.consulta._embeder_por_entorno", lambda: embeder_falso)

    cuerpo = (
        await cliente.post("/v1/catalogo/emparejar", json={"renglones": ["libreta", "plan lector", "zxqv"]})
    ).json()

    assert [e["texto"] for e in cuerpo["emparejamientos"]] == ["libreta", "plan lector", "zxqv"]
    assert [e["estado"] for e in cuerpo["emparejamientos"]] == ["reconocido", "hueco_catalogo", "sin_match"]
    assert [o["sku"] for o in cuerpo["emparejamientos"][0]["opciones"]] == ["TK-C001-ECO", "TK-C001-CON"]


async def test_emparejar_con_un_proveedor_de_embeddings_caido_responde_igual_por_lexico(cliente, monkeypatch):
    """Si el embeder falla la ruta no devuelve 500: degrada a lexico y el resultado es el mismo."""

    def roto(textos):
        raise RuntimeError("proveedor ficticio caido")

    cuerpo_base = (await cliente.post("/v1/catalogo/emparejar", json={"renglones": ["libreta"]})).json()
    monkeypatch.setattr("tukit_catalogo.consulta._embeder_por_entorno", lambda: roto)

    respuesta = await cliente.post("/v1/catalogo/emparejar", json={"renglones": ["libreta"]})

    assert respuesta.status_code == 200
    assert respuesta.json() == cuerpo_base


@pytest.mark.parametrize("cuerpo", [{}, {"renglones": "libreta"}, {"renglones": None}, {"renglones": {}}])
async def test_emparejar_exige_una_lista_de_renglones(cliente, cuerpo):
    """Sin `renglones`, o con algo que no es una lista, el error es 400 y nombra el campo."""
    respuesta = await cliente.post("/v1/catalogo/emparejar", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "renglones_vacios"
    assert respuesta.json()["campo"] == "renglones"


async def test_emparejar_convierte_cada_renglon_a_texto_y_acepta_el_maximo_de_500(cliente):
    """Un numero llega como texto ("123"); 500 renglones es el tope permitido y se responden todos."""
    uno = (await cliente.post("/v1/catalogo/emparejar", json={"renglones": [123]})).json()
    assert uno["emparejamientos"][0]["texto"] == "123"

    maximo = await cliente.post("/v1/catalogo/emparejar", json={"renglones": ["libreta"] * 500})

    assert maximo.status_code == 200
    assert maximo.json()["total"] == 500
