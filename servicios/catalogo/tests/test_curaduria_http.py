from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    PropuestaProducto,
    Tienda,
)
from tukit_comun.bd import MotorServicio


def _siembra(sesion) -> dict[str, str]:
    cuaderno = Concepto(codigo="C001", nombre_canonico="cuaderno", categoria="Cuadernos")
    sesion.add(cuaderno)
    sesion.flush()

    tienda = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    sesion.add(tienda)
    sesion.flush()

    pendiente = PropuestaProducto(
        concepto_id=cuaderno.id,
        texto_origen="cuaderno",
        tienda_id=tienda.id,
        referencia_externa="EX-CUAD-1",
        nombre="Cuaderno cuadriculado 100h",
        marca="Norma",
        precio_centavos=550000,
        nivel_sugerido="confiable",
        estado="pendiente",
        version_lista_id=None,
    )
    sesion.add(pendiente)
    sesion.flush()
    return {
        "concepto_c001": "C001",
        "concepto_c001_id": str(cuaderno.id),
        "tienda_exito_id": str(tienda.id),
        "propuesta_pendiente": str(pendiente.id),
    }


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, str] = {}
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


async def test_lista_propuestas_pendientes(cliente):
    r = await cliente.get("/v1/admin/catalogo/propuestas")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] >= 1
    p = cuerpo["propuestas"][0]
    assert set(p) >= {"id", "id_corto", "nombre", "precio", "nivel_sugerido", "concepto"}
    assert len(p["id_corto"]) == 8
    assert p["precio"] == 5500
    assert p["concepto"] == {"codigo": "C001", "nombre": "cuaderno"}
    assert p["atributos_verificados"] == {}
    assert isinstance(p["atributos_al_aprobar"], dict)


def _encolar_en_motor_de_prueba(monkeypatch):
    from tukit_catalogo import descubrir
    from tukit_catalogo.admin_http import PROPUESTA, _motor

    async def _falso_encolar(propuestas):
        if not propuestas:
            return 0
        insertadas = 0
        async with _motor().engine.begin() as conexion:
            for prop in propuestas:
                ya = (
                    await conexion.execute(
                        PROPUESTA.select().where(
                            PROPUESTA.c.tienda_id == prop["tienda_id"],
                            PROPUESTA.c.referencia_externa == prop["referencia_externa"],
                        )
                    )
                ).first()
                if ya is not None:
                    continue
                await conexion.execute(PROPUESTA.insert().values(**prop))
                insertadas += 1
        return insertadas

    monkeypatch.setattr(descubrir, "_encolar", _falso_encolar)


async def test_buscar_en_tienda_devuelve_candidatos(cliente, monkeypatch):
    from tukit_catalogo import admin, tiendas

    o = tiendas.Oferta(
        tienda="exito",
        nombre="Cuaderno 100h",
        precio_cop=5000,
        disponible=True,
        imagen_url=None,
        url="http://x",
        sku="SKU9",
        ean=None,
        marca="Norma",
        especificaciones={},
    )
    monkeypatch.setattr(admin.tiendas, "buscar", lambda slug, consulta, cuantos=24: [o])
    r = await cliente.get("/v1/admin/catalogo/tiendas/exito/buscar?consulta=cuaderno")
    assert r.status_code == 200
    cand = r.json()["candidatos"]
    assert cand and cand[0]["sku"] == "SKU9"
    assert cand[0]["precio"] == 5000 and cand[0]["slug"] == "exito"


async def test_buscar_en_tienda_desconocida_es_422(cliente):
    r = await cliente.get("/v1/admin/catalogo/tiendas/mercadolibre/buscar?consulta=x")
    assert r.status_code == 422 and r.json()["error"] == "tienda_desconocida"


async def test_encolar_util_cae_en_la_cola(cliente, monkeypatch):
    from tukit_catalogo import tiendas

    o = tiendas.Oferta(
        tienda="exito",
        nombre="Cuaderno",
        precio_cop=5000,
        disponible=True,
        imagen_url=None,
        url="http://x",
        sku="SKU9",
        ean=None,
        marca="Norma",
        especificaciones={},
    )
    monkeypatch.setattr(tiendas, "buscar", lambda slug, consulta, cuantos=24: [o])
    _encolar_en_motor_de_prueba(monkeypatch)
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "slug": "exito",
            "sku": "SKU9",
            "consulta": "cuaderno",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    cola = (await cliente.get("/v1/admin/catalogo/propuestas")).json()
    assert any(p["nombre"] == "Cuaderno" for p in cola["propuestas"])


async def test_encolar_util_concepto_inexistente_es_422(cliente, monkeypatch):
    from tukit_catalogo import tiendas

    o = tiendas.Oferta(
        tienda="exito",
        nombre="X",
        precio_cop=1,
        disponible=True,
        imagen_url=None,
        url="",
        sku="S",
        ean=None,
        marca=None,
        especificaciones={},
    )
    monkeypatch.setattr(tiendas, "buscar", lambda slug, consulta, cuantos=24: [o])
    _encolar_en_motor_de_prueba(monkeypatch)
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util",
        json={"concepto": "NOPE", "slug": "exito", "sku": "S", "consulta": "x", "nivel": "confiable"},
    )
    assert r.status_code == 422 and r.json()["error"] == "concepto_no_existe"


def _oferta_exito(nombre: str, sku: str, *, disponible: bool = True, precio: int = 48760):
    from tukit_catalogo import tiendas

    return tiendas.Oferta(
        tienda="exito",
        nombre=nombre,
        precio_cop=precio,
        disponible=disponible,
        imagen_url=None,
        url="http://x",
        sku=sku,
        ean=None,
        marca="Pilot",
        especificaciones={},
    )


async def test_encolar_util_acepta_lo_elegido_aunque_no_tenga_todas_las_palabras(cliente, monkeypatch):
    from tukit_catalogo import tiendas

    o = _oferta_exito("Pilot Pluma Pen 2.4 Caligrafia", "101539370")
    monkeypatch.setattr(tiendas, "buscar", lambda slug, consulta, cuantos=24: [o])
    _encolar_en_motor_de_prueba(monkeypatch)
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "slug": "exito",
            "sku": "101539370",
            "consulta": "Pluma para caligrafía",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    cola = (await cliente.get("/v1/admin/catalogo/propuestas")).json()
    assert any(p["nombre"] == "Pilot Pluma Pen 2.4 Caligrafia" for p in cola["propuestas"])


async def test_encolar_util_agotado_es_422_con_causa(cliente, monkeypatch):
    from tukit_catalogo import tiendas

    o = _oferta_exito("Pilot Pluma Pen 2.4 Caligrafia", "101539370", disponible=False)
    monkeypatch.setattr(tiendas, "buscar", lambda slug, consulta, cuantos=24: [o])
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "slug": "exito",
            "sku": "101539370",
            "consulta": "pluma",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 422 and r.json()["error"] == "candidato_no_disponible"
    assert "agotado" in r.json()["mensaje"]


async def test_encolar_libro_valida_isbn(cliente):
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/libro",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "isbn": "123",
            "titulo": "T",
            "precio": 30000,
            "slug": "panamericana",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 422 and r.json()["error"] == "isbn_invalido"


async def test_encolar_libro_precio_invalido_es_422(cliente):
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/libro",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "isbn": "9781234567897",
            "titulo": "El Principito",
            "precio": 0,
            "slug": "panamericana",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 422 and r.json()["error"] == "precio_invalido"


async def test_encolar_libro_cae_en_la_cola(cliente, monkeypatch):
    _encolar_en_motor_de_prueba(monkeypatch)
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/libro",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "isbn": "9781234567897",
            "titulo": "El Principito",
            "precio": 30000,
            "slug": "exito",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    cola = (await cliente.get("/v1/admin/catalogo/propuestas")).json()
    assert any(p["nombre"] == "El Principito" for p in cola["propuestas"])


async def test_encolar_util_manual_cae_en_la_cola(cliente, monkeypatch):
    _encolar_en_motor_de_prueba(monkeypatch)
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util-manual",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "nombre": "Cuaderno artesanal",
            "precio": 4200,
            "slug": "exito",
            "sku": "MANUAL-1",
            "url": "http://tienda/x",
            "marca": "Local",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    cola = (await cliente.get("/v1/admin/catalogo/propuestas")).json()
    fila = next(p for p in cola["propuestas"] if p["nombre"] == "Cuaderno artesanal")
    assert fila["precio"] == 4200


async def test_encolar_util_manual_precio_invalido_es_422(cliente):
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util-manual",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "nombre": "Cuaderno",
            "precio": 0,
            "slug": "exito",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 422 and r.json()["error"] == "precio_invalido"


async def test_encolar_util_manual_sin_nombre_es_422(cliente):
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util-manual",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "nombre": "   ",
            "precio": 4200,
            "slug": "exito",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 422 and r.json()["error"] == "nombre_invalido"


async def test_encolar_util_manual_tienda_desconocida_es_422(cliente):
    r = await cliente.post(
        "/v1/admin/catalogo/propuestas/util-manual",
        json={
            "concepto": cliente.ids["concepto_c001"],
            "nombre": "Cuaderno",
            "precio": 4200,
            "slug": "mercadolibre",
            "nivel": "confiable",
        },
    )
    assert r.status_code == 422 and r.json()["error"] == "tienda_desconocida"


async def test_aprobar_propuesta_traduce_el_codigo(cliente, monkeypatch):
    from tukit_catalogo import descubrir

    async def _falso_resolver(id_corto, aprobar, nivel, motivo, no_surtir=False, overrides=None):
        assert aprobar is True and nivel == "confiable"
        return 0

    monkeypatch.setattr(descubrir, "resolver", _falso_resolver)
    prop_id = cliente.ids["propuesta_pendiente"]
    r = await cliente.post(f"/v1/admin/catalogo/propuestas/{prop_id}/aprobar", json={"nivel": "confiable"})
    assert r.status_code == 200 and r.json()["estado"] == "aprobada"


async def test_aprobar_propuesta_reenvia_correcciones_a_resolver(cliente, monkeypatch):
    from tukit_catalogo import descubrir

    visto: dict = {}

    async def _falso_resolver(id_corto, aprobar, nivel, motivo, no_surtir=False, overrides=None):
        visto["overrides"] = overrides
        return 0

    monkeypatch.setattr(descubrir, "resolver", _falso_resolver)
    prop_id = cliente.ids["propuesta_pendiente"]
    r = await cliente.post(
        f"/v1/admin/catalogo/propuestas/{prop_id}/aprobar",
        json={
            "nivel": "premium",
            "marca": "  Faber  ",
            "imagen_url": "",
            "personaje": "Frozen",
            "atributos": {"hojas": 100},
        },
    )
    assert r.status_code == 200 and r.json()["estado"] == "aprobada"
    ov = visto["overrides"]
    assert ov == {
        "marca": "Faber",
        "imagen_url": None,
        "personaje": "Frozen",
        "atributos": {"hojas": 100},
    }
    assert "nombre" not in ov


async def test_aprobar_propuesta_sin_correcciones_no_manda_overrides(cliente, monkeypatch):
    from tukit_catalogo import descubrir

    visto: dict = {}

    async def _falso_resolver(id_corto, aprobar, nivel, motivo, no_surtir=False, overrides=None):
        visto["overrides"] = overrides
        return 0

    monkeypatch.setattr(descubrir, "resolver", _falso_resolver)
    prop_id = cliente.ids["propuesta_pendiente"]
    r = await cliente.post(f"/v1/admin/catalogo/propuestas/{prop_id}/aprobar", json={"nivel": "confiable"})
    assert r.status_code == 200
    assert visto["overrides"] is None


async def test_aprobar_propuesta_que_falla_es_409(cliente, monkeypatch):
    from tukit_catalogo import descubrir

    async def _falso_resolver(id_corto, aprobar, nivel, motivo, no_surtir=False, overrides=None):
        return 2

    monkeypatch.setattr(descubrir, "resolver", _falso_resolver)
    prop_id = cliente.ids["propuesta_pendiente"]
    r = await cliente.post(f"/v1/admin/catalogo/propuestas/{prop_id}/aprobar", json={"nivel": "confiable"})
    assert r.status_code == 409 and r.json()["error"] == "no_se_pudo_aprobar"
