"""La superficie de lectura del catalogo, contra lo que el frontend va a leer.

Estas pruebas existen sobre todo por un modo de fallar concreto: un endpoint
que devuelve `{"total": 0, "conceptos": []}` responde 200 perfectamente. La
base migrada y sin sembrar se ve igual de sana que la sembrada hasta que
alguien abre la pantalla, asi que cada caso siembra lo minimo y exige que la
respuesta lo traiga.

Se llama a la app con `ASGITransport`, en el mismo proceso y sin puerto. El
motor es SQLite en memoria y se le inyecta a mano, porque el arranque normal
abriria Postgres y una suite que necesita un motor vivo se termina saltando.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.api import app, pesos
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    Nivel,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
    VersionListaOficial,
)
from tukit_comun.bd import MotorServicio

CURADOR = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
COLEGIO = uuid.UUID("11111111-1111-5111-8111-111111111111")


def _siembra(sesion) -> None:
    """El catalogo minimo que hace falta para que la API tenga que decidir algo.

    Un concepto con tres niveles y dos tiendas con precios distintos, porque
    comparar precio entre tiendas es lo que el esquema anterior no podia
    expresar y es lo que la ficha del producto tiene que devolver.
    """
    cuaderno = Concepto(
        codigo="C001",
        nombre_canonico="cuaderno",
        categoria="Cuadernos",
        sinonimos=["cuaderno cuadriculado"],
        atributos_discriminantes=["rayado"],
        frecuencia_demanda=17,
    )
    block = Concepto(codigo="C003", nombre_canonico="block", categoria="Blocks", frecuencia_demanda=9)
    sesion.add_all([cuaderno, block])
    sesion.flush()

    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    pana = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
    sesion.add_all([exito, pana])
    sesion.flush()

    productos = []
    for nivel, sku, precio_exito in (
        (Nivel.ECONOMICO, "TK-C001-ECO", 4500),
        (Nivel.CONFIABLE, "TK-C001-CON", 9900),
        (Nivel.PREMIUM, "TK-C001-PRE", 18900),
    ):
        producto = ProductoCanonico(
            concepto_id=cuaderno.id,
            sku_interno=sku,
            nombre=f"Cuaderno {nivel.value}",
            marca="Norma",
            nivel=nivel.value,
            imagen_url=f"https://ejemplo.com/{sku}.jpg",
            atributos={"rayado": "cuadriculado"},
            unidades_por_empaque=1,
            curado_por=CURADOR,
        )
        sesion.add(producto)
        sesion.flush()
        productos.append((producto, precio_exito))

    personaje = ProductoCanonico(
        concepto_id=cuaderno.id,
        sku_interno="TK-C001-ECO-BLUEY",
        nombre="Cuaderno Bluey",
        nivel=Nivel.ECONOMICO.value,
        personaje="bluey",
        curado_por=CURADOR,
    )
    sesion.add(personaje)
    sesion.flush()

    for producto, precio_exito in productos:
        for tienda, valor in ((exito, precio_exito), (pana, precio_exito + 1100)):
            oferta = OfertaTienda(
                producto_canonico_id=producto.id,
                tienda_id=tienda.id,
                referencia_externa=f"{tienda.slug}-{producto.sku_interno}",
                url=f"https://{tienda.slug}.com/{producto.sku_interno}",
                metodo_vinculacion="manual",
                disponible=True,
            )
            sesion.add(oferta)
            sesion.flush()
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id,
                    valor_centavos=valor * 100,
                    fuente="scraper",
                    vigente_desde=datetime.now(UTC),
                )
            )

    lista = ListaOficial(colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026)
    sesion.add(lista)
    sesion.flush()
    version = VersionListaOficial(lista_id=lista.id, numero=1, vigente=True)
    sesion.add(version)
    sesion.flush()
    sesion.add_all(
        [
            ItemListaOficial(
                version_id=version.id,
                orden=1,
                texto_original="2 cuadernos cuadriculados grandes",
                cantidad=2,
                concepto_id=cuaderno.id,
            ),
            ItemListaOficial(
                version_id=version.id,
                orden=2,
                texto_original="Plan lector virtual RAZ-PLUS",
                cantidad=1,
                tipo_item="licencia_digital",
                modo_adquisicion="plataforma",
                instruccion_colegio="Se adquiere con QUOVIX.",
                requiere_revision=True,
            ),
        ]
    )
    sesion.flush()


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


class TestElDineroSaleEnPesosEnteros:
    def test_centavos_a_pesos(self):
        assert pesos(1890000) == 18900

    def test_nulo_es_no_se_conoce_y_no_cero(self):
        """La distincion es del contrato: un producto sin precio observado no
        se puede sumar a un total, y un cero lo sumaria sin ruido."""
        assert pesos(None) is None

    async def test_ningun_precio_de_la_respuesta_viene_en_centavos(self, cliente):
        ficha = (await cliente.get("/v1/catalogo/productos/TK-C001-ECO")).json()
        assert ficha["precio_desde"] == 4500
        assert [o["precio"] for o in ficha["ofertas"]] == [4500, 5600]


class TestNavegarElCatalogo:
    async def test_los_conceptos_traen_cuantos_productos_y_niveles_tienen(self, cliente):
        cuerpo = (await cliente.get("/v1/catalogo/conceptos")).json()

        assert cuerpo["total"] == 2
        # Por demanda y no alfabetico: el orden de una pantalla de catalogo
        # tiene que ser el de lo que los colegios de verdad piden.
        assert [c["codigo"] for c in cuerpo["conceptos"]] == ["C001", "C003"]
        cuaderno = cuerpo["conceptos"][0]
        assert cuaderno["productos"] == 4
        assert cuaderno["niveles_disponibles"] == 3

    async def test_se_pueden_pedir_solo_los_conceptos_con_hueco(self, cliente):
        cuerpo = (await cliente.get("/v1/catalogo/conceptos?con_producto=false")).json()
        assert [c["codigo"] for c in cuerpo["conceptos"]] == ["C003"]

    async def test_el_concepto_trae_sus_productos_en_orden_de_nivel(self, cliente):
        cuerpo = (await cliente.get("/v1/catalogo/conceptos/C001")).json()
        niveles = [p["nivel"] for p in cuerpo["productos"]]
        assert niveles == ["economico", "economico", "confiable", "premium"]

    async def test_un_concepto_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get("/v1/catalogo/conceptos/C999")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "concepto_no_existe"

    async def test_los_filtros_de_producto_se_combinan(self, cliente):
        con_personaje = (await cliente.get("/v1/catalogo/productos?con_personaje=true")).json()
        assert [p["sku"] for p in con_personaje["productos"]] == ["TK-C001-ECO-BLUEY"]

        premium = (await cliente.get("/v1/catalogo/productos?nivel=premium")).json()
        assert [p["sku"] for p in premium["productos"]] == ["TK-C001-PRE"]

        con_precio = (await cliente.get("/v1/catalogo/productos?con_precio=true")).json()
        assert con_precio["total"] == 3

    async def test_un_nivel_inventado_es_400_y_no_una_lista_vacia(self, cliente):
        """Devolver cero resultados para un valor imposible esconde el error
        del cliente detras de una respuesta que parece correcta."""
        respuesta = await cliente.get("/v1/catalogo/productos?nivel=carisimo")
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "nivel"

    async def test_la_ficha_ordena_las_ofertas_por_precio(self, cliente):
        ficha = (await cliente.get("/v1/catalogo/productos/TK-C001-CON")).json()
        assert [o["tienda"] for o in ficha["ofertas"]] == ["exito", "panamericana"]
        assert ficha["ofertas"][0]["url"].startswith("https://exito.com/")

    async def test_las_tiendas_dicen_cuantas_ofertas_tienen(self, cliente):
        cuerpo = (await cliente.get("/v1/catalogo/tiendas")).json()
        assert {t["slug"]: t["ofertas"] for t in cuerpo["tiendas"]} == {
            "exito": 3,
            "panamericana": 3,
        }

    async def test_la_pagina_tiene_tope(self, cliente):
        assert (await cliente.get("/v1/catalogo/productos?por_pagina=9999")).status_code == 400


class TestLasListasOficiales:
    async def test_se_filtran_por_colegio_y_grado(self, cliente):
        cuerpo = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Cuarto")).json()

        assert cuerpo["total"] == 1
        lista = cuerpo["listas"][0]
        assert lista["items"] == 2
        # Sin revisar no es un defecto: es la puerta que habilita salir a una
        # tienda por lo que la lista pide y el catalogo no tiene.
        assert lista["revisada"] is False

    async def test_el_detalle_resuelve_el_tipo_del_renglon_contra_su_concepto(self, cliente):
        listado = (await cliente.get("/v1/listas")).json()
        detalle = (await cliente.get(f"/v1/listas/{listado['listas'][0]['lista_id']}")).json()

        cuaderno, licencia = detalle["items"]
        # El renglon no declara tipo, asi que hereda el de su concepto.
        assert cuaderno["tipo_item_declarado"] is None
        assert cuaderno["tipo_item"] == "util"
        assert cuaderno["surtible"] is True
        assert cuaderno["concepto"]["codigo"] == "C001"

        assert licencia["tipo_item"] == "licencia_digital"
        assert licencia["surtible"] is False
        assert licencia["instruccion_colegio"] == "Se adquiere con QUOVIX."

    async def test_una_lista_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.get(f"/v1/listas/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "lista_no_existe"


class TestEmparejar:
    async def test_devuelve_una_opcion_por_nivel_con_lo_que_hace_falta_para_comprar(self, cliente):
        respuesta = await cliente.post(
            "/v1/catalogo/emparejar", json={"renglones": ["2 cuadernos cuadriculados"]}
        )
        emparejado = respuesta.json()["emparejamientos"][0]

        assert emparejado["estado"] == "reconocido"
        assert emparejado["concepto_codigo"] == "C001"
        opcion = emparejado["opciones"][0]
        # Sin estos tres, quien arma el kit tendria que volver a consultar el
        # producto por su sku, una llamada por renglon de la lista.
        assert opcion["unidades_por_empaque"] == 1
        assert opcion["imagen_url"].endswith(".jpg")
        assert opcion["producto_id"] is not None

    async def test_sin_renglones_es_un_error_con_campo(self, cliente):
        respuesta = await cliente.post("/v1/catalogo/emparejar", json={"renglones": []})
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "renglones"

    async def test_una_lista_absurda_se_rechaza_antes_de_cargar_el_indice(self, cliente):
        respuesta = await cliente.post("/v1/catalogo/emparejar", json={"renglones": ["x"] * 501})
        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "demasiados_renglones"


class TestElNavegadorPuedeLeerLaRespuesta:
    async def test_hay_cabecera_de_cors_para_el_front_local(self, cliente):
        respuesta = await cliente.get("/salud", headers={"Origin": "http://localhost:3000"})
        assert respuesta.headers["access-control-allow-origin"] == "http://localhost:3000"
