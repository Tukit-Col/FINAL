"""NFR-MAN-01: el SQL de `RepoCatalogo`: filtros, conteos y que lo retirado no cuenta.

Las pruebas HTTP del catalogo (`test_api_catalogo`, `test_api_productos`) miran
la respuesta publica; aqui se ata el repositorio a una conexion SQLite y se le
piden las filas directamente, porque los filtros viven en el SQL y un filtro que
se ignora en silencio devuelve un 200 con la lista completa: se ve igual de
sano que uno que funciona.

Lo que se vigila, por orden de costo si falla:

  - lo INACTIVO no cuenta: un concepto, un producto o una oferta apagados no
    entran en el resumen, en las colecciones ni en el precio "desde";
  - el precio "desde" sale del precio VIGENTE mas bajo (un tramo cerrado no
    cuenta) y solo de ofertas activas;
  - cada filtro se aplica solo y el `total` es el de la consulta filtrada, no el
    de la pagina.

Siembra pequena y a mano (datos ficticios): 3 conceptos activos (+1 apagado) y
4 productos activos (+1 retirado) en 2 tiendas activas (+1 cerrada).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
    VersionListaOficial,
)
from tukit_catalogo.repositorios.catalogo import RepoCatalogo

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("55555555-5555-5555-8555-555555555555")
COLEGIO = uuid.UUID("66666666-6666-5666-8666-666666666666")
OTRO_COLEGIO = uuid.UUID("77777777-7777-5777-8777-777777777777")
DESDE = datetime(2026, 2, 1, tzinfo=UTC)
HASTA = datetime(2026, 3, 1, tzinfo=UTC)


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """Conceptos, productos, ofertas y listas con un caso apagado de cada clase."""
    cuaderno = Concepto(
        codigo="C001",
        nombre_canonico="cuaderno",
        categoria="Cuadernos",
        tipo_item="util",
        frecuencia_demanda=17,
    )
    colores = Concepto(
        codigo="C002", nombre_canonico="Colores", categoria="Arte", tipo_item="util", frecuencia_demanda=9
    )
    plan = Concepto(
        codigo="C003",
        nombre_canonico="plan lector",
        categoria="Lectura",
        tipo_item="licencia_digital",
        frecuencia_demanda=9,
    )
    viejo = Concepto(codigo="C004", nombre_canonico="cuaderno viejo", categoria="Cuadernos", activo=False)
    sesion.add_all([cuaderno, colores, plan, viejo])

    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    pana = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
    cerrada = Tienda(slug="cerrada", nombre="Tienda Cerrada", tipo="minorista", activa=False)
    sesion.add_all([exito, pana, cerrada])
    sesion.flush()

    def _producto(concepto, sku, nombre, nivel, **extra):
        p = ProductoCanonico(
            concepto_id=concepto.id, sku_interno=sku, nombre=nombre, nivel=nivel, curado_por=CURADOR, **extra
        )
        sesion.add(p)
        sesion.flush()
        return p

    eco = _producto(cuaderno, "TK-C001-ECO", "Cuaderno Bluey", "economico", personaje="bluey")
    con = _producto(
        cuaderno,
        "TK-C001-CON",
        "Cuaderno Norma",
        "confiable",
        marca="Norma",
        imagen_url="https://e.test/c.jpg",
    )
    pre = _producto(
        cuaderno,
        "TK-C001-PRE",
        "Cuaderno Premium",
        "premium",
        marca="Scribe",
        imagen_url="https://e.test/p.jpg",
    )
    col = _producto(
        colores,
        "TK-C002-CON",
        "Colores Faber",
        "confiable",
        marca="Faber",
        imagen_url="https://e.test/f.jpg",
        quality_score=0.3,
    )
    _producto(colores, "TK-C002-PRE", "Colores retirados", "premium", activo=False)

    def _oferta(producto, tienda, centavos, *, activo=True, historico=None):
        o = OfertaTienda(
            producto_canonico_id=producto.id,
            tienda_id=tienda.id,
            referencia_externa=f"{tienda.slug}-{producto.sku_interno}",
            url=f"https://{tienda.slug}.example.test/{producto.sku_interno}",
            metodo_vinculacion="manual",
            disponible=True,
            activo=activo,
        )
        sesion.add(o)
        sesion.flush()
        if historico is not None:
            sesion.add(
                PrecioOferta(
                    oferta_id=o.id,
                    valor_centavos=historico,
                    fuente="scraper",
                    vigente_desde=DESDE,
                    vigente_hasta=HASTA,
                )
            )
        sesion.add(
            PrecioOferta(oferta_id=o.id, valor_centavos=centavos, fuente="scraper", vigente_desde=HASTA)
        )
        sesion.flush()

    # ECO: dos tiendas, gana la mas barata. CON: un tramo historico MAS BARATO
    # ya cerrado, que no debe contar. COLORES: su unica oferta esta apagada.
    _oferta(eco, exito, 450000)
    _oferta(eco, pana, 500000)
    _oferta(con, exito, 990000, historico=10000)
    _oferta(col, exito, 800000, activo=False)

    def _lista(colegio, grado, anio, *, revisada=False, vigente=True, activa=True, renglones=0):
        lista = ListaOficial(colegio_id=colegio, grado=grado, anio_lectivo=anio, activa=activa)
        sesion.add(lista)
        sesion.flush()
        version = VersionListaOficial(
            lista_id=lista.id, numero=1, vigente=vigente, revisada_en=DESDE if revisada else None
        )
        sesion.add(version)
        sesion.flush()
        for orden in range(1, renglones + 1):
            sesion.add(
                ItemListaOficial(
                    version_id=version.id,
                    orden=orden,
                    texto_original=f"renglon {orden}",
                    cantidad=1,
                    requiere_revision=True,
                )
            )
        sesion.flush()
        return lista

    _lista(COLEGIO, "Cuarto", 2026, revisada=True, renglones=2)
    _lista(COLEGIO, "Quinto", 2025)
    _lista(OTRO_COLEGIO, "Cuarto", 2026)
    _lista(COLEGIO, "Sexto", 2026, activa=False)
    _lista(COLEGIO, "Septimo", 2026, vigente=False)
    sesion.flush()
    return {"eco": eco.id, "con": con.id, "pre": pre.id, "col": col.id}


@pytest.fixture()
async def ambiente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()
    async with engine.connect() as conexion:
        yield RepoCatalogo(conexion), ids
    await engine.dispose()


def _codigos(filas) -> list[str]:
    return [f.codigo for f in filas]


def _skus(filas) -> list[str]:
    return [f.sku_interno for f in filas]


async def _conceptos(repo, **filtros):
    base = {"categoria": None, "tipo_item": None, "busqueda": None, "con_producto": None}
    return await repo.listar_conceptos(**{**base, **filtros}, pagina=1, por_pagina=50)


async def _productos(repo, **filtros):
    base = {
        "concepto": None,
        "nivel": None,
        "personaje": None,
        "con_personaje": None,
        "busqueda": None,
        "con_precio": None,
        "con_ofertas": False,
    }
    return await repo.listar_productos(**{**base, **filtros}, pagina=1, por_pagina=50)


async def test_el_resumen_cuenta_solo_lo_activo(ambiente):
    """Las siete cifras del encabezado ignoran el concepto apagado, el producto retirado y la tienda cerrada.

    Es lo primero que ve el equipo en la consola: un conteo inflado por lo apagado
    hace creer que el catalogo esta mas completo de lo que esta.
    """
    repo, _ = ambiente
    assert await repo.resumen() == {
        "conceptos": 3,
        "productos": 4,
        "conceptos_con_tres_niveles": 1,
        "conceptos_sin_producto": 1,
        "productos_con_foto": 3,
        "tiendas": 2,
        "productos_sin_revisar": 1,
    }


async def test_las_categorias_se_agrupan_en_orden_y_sin_los_conceptos_apagados(ambiente):
    """`Cuadernos` cuenta 1 (el C004 apagado no suma) y la salida va ordenada por nombre."""
    repo, _ = ambiente
    assert [(f.categoria, f.conceptos) for f in await repo.categorias()] == [
        ("Arte", 1),
        ("Cuadernos", 1),
        ("Lectura", 1),
    ]


async def test_los_conceptos_salen_por_demanda_y_luego_por_codigo(ambiente):
    """El orden es el de la demanda (C001 = 17); a igual demanda desempata el codigo (C002 antes de C003)."""
    repo, _ = ambiente
    total, filas = await _conceptos(repo)
    assert total == 3
    assert _codigos(filas) == ["C001", "C002", "C003"]
    assert {f.codigo: (f.productos, f.niveles) for f in filas} == {
        "C001": (3, 3),
        "C002": (1, 1),
        "C003": (0, 0),
    }


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        ({"categoria": "Arte"}, ["C002"]),
        ({"categoria": "arte"}, []),
        ({"tipo_item": "licencia_digital"}, ["C003"]),
        ({"busqueda": "CUAD"}, ["C001"]),
        ({"busqueda": "lector"}, ["C003"]),
        ({"con_producto": True}, ["C001", "C002"]),
        ({"con_producto": False}, ["C003"]),
        ({"categoria": "Cuadernos", "tipo_item": "util", "con_producto": True}, ["C001"]),
    ],
)
async def test_cada_filtro_de_conceptos_se_aplica_y_el_total_es_el_filtrado(ambiente, filtro, esperado):
    """La categoria es exacta; la busqueda ignora mayusculas; `con_producto` parte los conceptos en dos."""
    repo, _ = ambiente
    total, filas = await _conceptos(repo, **filtro)
    assert _codigos(filas) == esperado
    assert total == len(esperado)


async def test_la_paginacion_de_conceptos_conserva_el_total(ambiente):
    """La segunda pagina de dos trae el ultimo concepto, pero el total sigue siendo 3."""
    repo, _ = ambiente
    total, filas = await repo.listar_conceptos(
        categoria=None, tipo_item=None, busqueda=None, con_producto=None, pagina=2, por_pagina=2
    )
    assert total == 3
    assert _codigos(filas) == ["C003"]


async def test_ver_un_concepto_que_no_existe_no_trae_productos(ambiente):
    """Un codigo desconocido da `(None, [])` y no una excepcion."""
    repo, _ = ambiente
    assert await repo.ver_concepto("C999") == (None, [])


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        ({"concepto": "C001"}, ["TK-C001-CON", "TK-C001-ECO", "TK-C001-PRE"]),
        ({"concepto": "C002"}, ["TK-C002-CON"]),
        ({"nivel": "premium"}, ["TK-C001-PRE"]),
        ({"personaje": "BLUEY"}, ["TK-C001-ECO"]),
        ({"con_personaje": True}, ["TK-C001-ECO"]),
        ({"con_personaje": False}, ["TK-C001-CON", "TK-C001-PRE", "TK-C002-CON"]),
        ({"busqueda": "norma"}, ["TK-C001-CON"]),
        ({"busqueda": "FABER"}, ["TK-C002-CON"]),
        ({"busqueda": "bluey"}, ["TK-C001-ECO"]),
        ({"con_precio": True}, ["TK-C001-CON", "TK-C001-ECO"]),
    ],
)
async def test_cada_filtro_de_productos_se_aplica_y_el_retirado_nunca_sale(ambiente, filtro, esperado):
    """Filtrar por concepto, nivel, personaje (sin distinguir mayusculas), texto o precio acota la lista.

    El orden es concepto, nivel y nombre. `TK-C002-PRE` esta retirado y no
    aparece en ninguna combinacion, ni siquiera sin filtros.
    """
    repo, _ = ambiente
    total, filas, _ofertas = await _productos(repo, **filtro)
    assert _skus(filas) == esperado
    assert total == len(esperado)


async def test_sin_filtros_el_catalogo_son_los_cuatro_productos_activos(ambiente):
    """Sin filtros salen los cuatro productos activos y el retirado (`TK-C002-PRE`) nunca se cuela."""
    repo, _ = ambiente
    total, filas, _ = await _productos(repo)
    assert total == 4
    assert "TK-C002-PRE" not in _skus(filas)


async def test_el_precio_desde_es_el_vigente_mas_bajo_y_cuenta_solo_ofertas_activas(ambiente):
    """ECO cuesta 4500 (la mas barata de dos tiendas); CON 9900 (el tramo cerrado de 100 no cuenta);
    el producto cuya unica oferta esta apagada no tiene precio."""
    repo, _ = ambiente
    _, filas, _ = await _productos(repo)
    por_sku = {f.sku_interno: (f.centavos, f.tiendas) for f in filas}
    assert por_sku["TK-C001-ECO"] == (450000, 2)
    assert por_sku["TK-C001-CON"] == (990000, 1)
    assert por_sku["TK-C001-PRE"] == (None, None)
    assert por_sku["TK-C002-CON"] == (None, None)


async def test_con_ofertas_trae_las_ofertas_vivas_por_producto(ambiente):
    """`con_ofertas` expande la pagina: ECO trae sus dos tiendas; la oferta apagada y los productos sin
    ofertas no aparecen; y el tramo vigente es el que se adjunta."""
    repo, ids = ambiente
    _, _, ofertas = await _productos(repo, con_ofertas=True)
    assert set(ofertas) == {ids["eco"], ids["con"]}
    assert {o.slug: o.valor_centavos for o in ofertas[ids["eco"]]} == {
        "exito": 450000,
        "panamericana": 500000,
    }
    assert [o.valor_centavos for o in ofertas[ids["con"]]] == [990000]
    assert all(o.vigente_hasta is None for lista in ofertas.values() for o in lista)


async def test_sin_con_ofertas_no_se_consultan_ofertas(ambiente):
    """El valor por omision es no expandir: el mapa de ofertas va vacio."""
    repo, _ = ambiente
    _, filas, ofertas = await _productos(repo)
    assert filas and ofertas == {}


async def test_con_ofertas_y_pagina_vacia_no_consulta_nada(ambiente):
    """Una busqueda sin resultados con `con_ofertas` devuelve vacio y no falla (`IN ()` sin ids)."""
    repo, _ = ambiente
    total, filas, ofertas = await _productos(repo, busqueda="no existe", con_ofertas=True)
    assert (total, filas, ofertas) == (0, [], {})


async def test_listar_listas_filtra_por_ano_colegio_y_revision(ambiente):
    """Solo cuentan las listas activas con version vigente; cada filtro se suma a los demas."""
    repo, _ = ambiente

    async def listar(**filtros):
        base = {"colegio_id": None, "grado": None, "anio_lectivo": None, "revisada": None}
        total, filas = await repo.listar_listas(**{**base, **filtros}, pagina=1, por_pagina=50)
        return total, sorted((f.grado, str(f.colegio_id)[:2], f.renglones) for f in filas)

    todas = await listar()
    assert todas[0] == 3
    assert (await listar(anio_lectivo=2025)) == (1, [("Quinto", "66", 0)])
    assert (await listar(anio_lectivo=2026))[0] == 2
    assert (await listar(colegio_id=OTRO_COLEGIO)) == (1, [("Cuarto", "77", 0)])
    assert (await listar(revisada=True)) == (1, [("Cuarto", "66", 2)])
    assert (await listar(revisada=False))[0] == 2
    assert (await listar(grado="Cuarto", anio_lectivo=2026, revisada=False)) == (1, [("Cuarto", "77", 0)])
