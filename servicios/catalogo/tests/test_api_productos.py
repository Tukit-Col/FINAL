"""La superficie de ESCRITURA de productos: editar, reclasificar y retirar.

El SPA de catalogo (P4c) y el refactor del empezar (P4b) necesitan cuatro cosas
que la API de LECTURA no daba: enumerar los personajes en existencia con su
conteo, editar un producto por su sku, reasignarle el concepto y retirarlo. Se
montan sobre la MISMA api publica que ya sirve `GET /v1/catalogo/productos`,
porque ahi viven los productos y de ahi los lee el SPA: la forma de lectura y la
de escritura tienen que coincidir clave por clave.

Las tres rutas que escriben NO llaman a Gemini en el camino de la peticion:
cuando cambia lo que alimenta el vector (nombre, atributos, concepto) solo se
invalida `texto_embedding=NULL`, y el siguiente `enriquecer` re-embebe. Se
prueba mirando la columna directo, no la respuesta.

Corren contra la app con `ASGITransport` y un SQLite en memoria inyectado a
mano, igual que `test_api_admin`.
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
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)
from tukit_comun.bd import MotorServicio

CURADOR = uuid.UUID("22222222-2222-5222-8222-222222222222")
PRODUCTO = Base.metadata.tables["producto_canonico"]


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """Dos conceptos y un puñado de productos con personaje, para ejercer todo.

    C001 (cuaderno) admite personaje y tiene un cuaderno de Spiderman con
    precio, un cuaderno liso con precio y un cuaderno de Frozen sin precio.
    C011 (colores) tiene una caja de Spiderman: dos personajes distintos, dos
    conceptos, para probar el enumerado. El producto con precio y ofertas es el
    que se usa para comprobar que la respuesta de escritura conserva
    `precio_desde` y `tiendas`.
    """
    cuaderno = Concepto(codigo="C001", nombre_canonico="cuaderno", categoria="Cuadernos")
    colores = Concepto(codigo="C011", nombre_canonico="colores", categoria="Arte")
    sesion.add_all([cuaderno, colores])
    sesion.flush()

    tienda = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    sesion.add(tienda)
    sesion.flush()

    productos: dict[str, ProductoCanonico] = {}
    especificacion = (
        # sku, concepto, nombre, nivel, personaje, precio (None = sin oferta)
        ("TK-C001-SPIDER", cuaderno.id, "Cuaderno Spiderman", "confiable", "Spiderman", 9900),
        ("TK-C001-LISO", cuaderno.id, "Cuaderno liso", "economico", None, 4500),
        ("TK-C001-FROZEN", cuaderno.id, "Cuaderno Frozen", "premium", "Frozen", None),
        ("TK-C011-SPIDER", colores.id, "Colores Spiderman", "confiable", "Spiderman", 12000),
        ("TK-C011-LISO", colores.id, "Colores lisos", "economico", None, 6000),
    )
    for sku, cid, nombre, nivel, personaje, precio in especificacion:
        producto = ProductoCanonico(
            concepto_id=cid,
            sku_interno=sku,
            nombre=nombre,
            marca="Norma",
            nivel=nivel,
            personaje=personaje,
            imagen_url=f"https://ejemplo.com/{sku}.jpg",
            atributos={"rayado": "cuadriculado"},
            unidades_por_empaque=1,
            quality_score="0.700",
            # La huella del embedding empieza puesta: el test de invalidacion
            # comprueba que la escritura la borra a NULL.
            texto_embedding=f"texto de {sku}",
            embedding_model="fake-embeder",
            curado_por=CURADOR,
        )
        sesion.add(producto)
        sesion.flush()
        productos[sku] = producto
        if precio is not None:
            oferta = OfertaTienda(
                producto_canonico_id=producto.id,
                tienda_id=tienda.id,
                referencia_externa=f"{tienda.slug}-{sku}",
                url=f"https://{tienda.slug}.com/{sku}",
                metodo_vinculacion="manual",
                disponible=True,
            )
            sesion.add(oferta)
            sesion.flush()
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id,
                    valor_centavos=precio * 100,
                    fuente="scraper",
                    vigente_desde=datetime(2026, 2, 1, tzinfo=UTC),
                )
            )
    sesion.flush()
    return {"cuaderno": cuaderno.id, "colores": colores.id}


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, uuid.UUID] = {}
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


async def _texto_embedding(sku: str) -> str | None:
    async with app.state.motor.engine.begin() as conexion:
        return await conexion.scalar(
            select(PRODUCTO.c.texto_embedding).where(PRODUCTO.c.sku_interno == sku)
        )


async def _activo(sku: str) -> bool | None:
    async with app.state.motor.engine.begin() as conexion:
        return await conexion.scalar(select(PRODUCTO.c.activo).where(PRODUCTO.c.sku_interno == sku))


class TestListarPersonajes:
    async def test_enumera_personajes_con_su_conteo(self, cliente):
        cuerpo = (await cliente.get("/v1/catalogo/personajes")).json()
        por_nombre = {p["nombre"]: p for p in cuerpo["personajes"]}
        # Spiderman aparece en dos productos (cuaderno y colores), Frozen en uno.
        assert por_nombre["Spiderman"]["productos"] == 2
        assert por_nombre["Frozen"]["productos"] == 1
        assert set(por_nombre) == {"Frozen", "Spiderman"}

    async def test_ordena_por_nombre(self, cliente):
        cuerpo = (await cliente.get("/v1/catalogo/personajes")).json()
        nombres = [p["nombre"] for p in cuerpo["personajes"]]
        assert nombres == sorted(nombres)

    async def test_trae_los_conceptos_de_cada_personaje(self, cliente):
        # El SPA necesita los codigos de concepto por personaje para su gate de
        # los cuatro anclas (C001/C009/C011/C086) sin una segunda llamada.
        cuerpo = (await cliente.get("/v1/catalogo/personajes")).json()
        por_nombre = {p["nombre"]: p for p in cuerpo["personajes"]}
        assert set(por_nombre["Spiderman"]["conceptos"]) == {"C001", "C011"}
        assert set(por_nombre["Frozen"]["conceptos"]) == {"C001"}

    async def test_no_cuenta_los_inactivos(self, cliente):
        await cliente.delete("/v1/catalogo/productos/TK-C001-FROZEN")
        cuerpo = (await cliente.get("/v1/catalogo/personajes")).json()
        assert "Frozen" not in {p["nombre"] for p in cuerpo["personajes"]}


class TestEditarProducto:
    async def test_edita_campos_y_devuelve_la_forma_publica(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER",
            json={"nombre": "Cuaderno Spiderman edicion", "marca": "Scribe", "es_propio": True},
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["sku"] == "TK-C001-SPIDER"
        assert cuerpo["nombre"] == "Cuaderno Spiderman edicion"
        assert cuerpo["marca"] == "Scribe"
        assert cuerpo["es_propio"] is True
        # La forma publica conserva precio_desde y tiendas del producto con oferta.
        assert cuerpo["precio_desde"] == 9900
        assert cuerpo["tiendas"] == 1
        assert cuerpo["concepto"]["codigo"] == "C001"

    async def test_cambiar_nombre_invalida_el_embedding(self, cliente):
        assert await _texto_embedding("TK-C001-SPIDER") is not None
        await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"nombre": "Otro nombre"}
        )
        assert await _texto_embedding("TK-C001-SPIDER") is None

    async def test_cambiar_atributos_invalida_el_embedding(self, cliente):
        await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"atributos": {"rayado": "rayado"}}
        )
        assert await _texto_embedding("TK-C001-SPIDER") is None

    async def test_editar_solo_marca_no_toca_el_embedding(self, cliente):
        # La marca no alimenta el vector: no hay por que gastar una re-embebida.
        await cliente.patch("/v1/catalogo/productos/TK-C001-SPIDER", json={"marca": "Scribe"})
        assert await _texto_embedding("TK-C001-SPIDER") == "texto de TK-C001-SPIDER"

    async def test_un_campo_inmutable_se_rechaza_nombrandolo(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"sku": "OTRO", "nombre": "x"}
        )
        assert respuesta.status_code == 400
        env = respuesta.json()
        assert env["error"] == "campo_no_editable"
        assert env["campo"] == "sku"

    async def test_el_concepto_no_se_edita_por_esta_ruta(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"concepto": "C011"}
        )
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "concepto"

    async def test_nivel_fuera_de_dominio_es_400(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"nivel": "carisimo"}
        )
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "nivel"

    async def test_unidad_base_fuera_de_dominio_es_400(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"unidad_base": "cajita"}
        )
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "unidad_base"

    async def test_empaque_cero_es_400(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"unidades_por_empaque": 0}
        )
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "unidades_por_empaque"

    async def test_quality_score_fuera_de_rango_es_400(self, cliente):
        respuesta = await cliente.patch(
            "/v1/catalogo/productos/TK-C001-SPIDER", json={"quality_score": 1.5}
        )
        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "quality_score"

    async def test_sku_inexistente_es_404(self, cliente):
        respuesta = await cliente.patch("/v1/catalogo/productos/NO-EXISTE", json={"marca": "x"})
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "producto_no_existe"


class TestReclasificar:
    async def test_reasigna_el_concepto_y_devuelve_la_forma_publica(self, cliente):
        respuesta = await cliente.post(
            "/v1/catalogo/productos/TK-C001-SPIDER/reclasificar", json={"concepto": "C011"}
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["concepto"]["codigo"] == "C011"
        assert cuerpo["sku"] == "TK-C001-SPIDER"
        assert cuerpo["precio_desde"] == 9900

    async def test_reclasificar_invalida_el_embedding(self, cliente):
        await cliente.post(
            "/v1/catalogo/productos/TK-C001-SPIDER/reclasificar", json={"concepto": "C011"}
        )
        assert await _texto_embedding("TK-C001-SPIDER") is None

    async def test_concepto_inexistente_es_404(self, cliente):
        respuesta = await cliente.post(
            "/v1/catalogo/productos/TK-C001-SPIDER/reclasificar", json={"concepto": "C999"}
        )
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "concepto_no_existe"

    async def test_producto_inexistente_es_404(self, cliente):
        respuesta = await cliente.post(
            "/v1/catalogo/productos/NO-EXISTE/reclasificar", json={"concepto": "C011"}
        )
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "producto_no_existe"


class TestRetirarProducto:
    async def test_es_soft_delete(self, cliente):
        assert await _activo("TK-C001-SPIDER") is True
        respuesta = await cliente.delete("/v1/catalogo/productos/TK-C001-SPIDER")
        assert respuesta.status_code == 204
        # No se borra: sigue en la tabla, solo inactivo (las ofertas no orfanan).
        assert await _activo("TK-C001-SPIDER") is False

    async def test_desaparece_de_la_lectura_publica(self, cliente):
        await cliente.delete("/v1/catalogo/productos/TK-C001-SPIDER")
        assert (await cliente.get("/v1/catalogo/productos/TK-C001-SPIDER")).status_code == 404

    async def test_retirar_dos_veces_sigue_siendo_204(self, cliente):
        assert (await cliente.delete("/v1/catalogo/productos/TK-C001-SPIDER")).status_code == 204
        assert (await cliente.delete("/v1/catalogo/productos/TK-C001-SPIDER")).status_code == 204

    async def test_sku_inexistente_es_404(self, cliente):
        respuesta = await cliente.delete("/v1/catalogo/productos/NO-EXISTE")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "producto_no_existe"
