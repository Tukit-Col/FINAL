"""Crear conceptos y aprender de las correcciones de la cola."""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
# ruff: noqa: F811

from __future__ import annotations

import pytest
from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    cliente,
)
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Concepto,
)


class TestCrearConcepto:
    async def test_autogenera_el_siguiente_codigo_y_parte_sinonimos(self, cliente):
        # La semilla tiene C001 y C002: el nuevo nace C003. Los sinonimos llegan
        # separados por "|" y se guardan como lista para que el matcher los use.
        respuesta = await cliente.post(
            "/v1/admin/catalogo/conceptos",
            json={
                "nombre_canonico": "plan lector digital",
                "categoria": "Diccionario / Biblia / Libros / Constitución",
                "sinonimos": "raz plus | plan lector virtual",
                "tipo_item": "licencia_digital",
            },
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["codigo"] == "C003"

        # El concepto quedo activo y con sus sinonimos: aparece en el vocabulario.
        from sqlalchemy import select
        from tukit_catalogo.admin_http import CONCEPTO, _motor

        async with _motor().engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(CONCEPTO.c.sinonimos, CONCEPTO.c.tipo_item).where(CONCEPTO.c.codigo == "C003")
                )
            ).one()
        assert list(fila.sinonimos) == ["raz plus", "plan lector virtual"]
        assert fila.tipo_item == "licencia_digital"

    async def test_guarda_los_atributos_que_filtran_y_los_que_informan(self, cliente):
        # El alta trae los dos papeles del atributo: el discriminante descarta
        # productos (un cuaderno cuadriculado no pasa por uno rayado) y el
        # descriptivo solo cuenta que se compra. Se normalizan a la forma del
        # corpus y un nombre repetido entre listas se queda solo como filtro,
        # porque la base prohibe que este en las dos.
        respuesta = await cliente.post(
            "/v1/admin/catalogo/conceptos",
            json={
                "nombre_canonico": "Bata de laboratorio",
                "categoria": "Uniformes",
                "atributos_discriminantes": ["Color", "manga larga"],
                "atributos_descriptivos": "talla | color",
            },
        )
        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["atributos_discriminantes"] == ["color", "manga_larga"]
        assert cuerpo["atributos_descriptivos"] == ["talla"]

        from sqlalchemy import select
        from tukit_catalogo.admin_http import CONCEPTO, _motor

        async with _motor().engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(CONCEPTO.c.atributos_discriminantes, CONCEPTO.c.atributos_descriptivos).where(
                        CONCEPTO.c.codigo == cuerpo["codigo"]
                    )
                )
            ).one()
        assert list(fila.atributos_discriminantes) == ["color", "manga_larga"]
        assert list(fila.atributos_descriptivos) == ["talla"]

    async def test_nombre_repetido_es_409(self, cliente):
        # "cuaderno" ya existe (C001): duplicarlo partiria el vocabulario, asi que
        # se rechaza y se invita a agregarle productos en vez de crear otro.
        respuesta = await cliente.post(
            "/v1/admin/catalogo/conceptos",
            json={"nombre_canonico": "Cuaderno", "categoria": "Cuadernos"},
        )
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "concepto_ya_existe"
        assert respuesta.json()["campo"] == "nombre_canonico"

    @pytest.mark.parametrize(
        ("cuerpo", "error", "campo"),
        [
            ({"categoria": "Arte"}, "nombre_invalido", "nombre_canonico"),
            ({"nombre_canonico": "algo"}, "categoria_invalida", "categoria"),
        ],
        ids=["sin_nombre", "sin_categoria"],
    )
    async def test_sin_nombre_o_categoria_es_422_nombrando_el_campo(self, cliente, cuerpo, error, campo):
        respuesta = await cliente.post("/v1/admin/catalogo/conceptos", json=cuerpo)
        assert respuesta.status_code == 422
        assert (respuesta.json()["error"], respuesta.json()["campo"]) == (error, campo)


class TestLaCorreccionVuelveAlCatalogo:
    """Lo que el equipo corrige en la cola no vuelve a fallar en la lista siguiente (13-nov)."""

    async def test_corregir_el_concepto_lo_aprende_como_sinonimo(self, cliente):
        from tukit_catalogo.descubrir import clasificar

        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        chaquiras = next(i for i in revision["items"] if i["texto_original"] == "chaquiras de colores")
        r = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{chaquiras['item_id']}",
            json={"concepto_codigo": "C002", "requiere_revision": False},
        )
        assert r.status_code == 200

        async with app.state.motor.sesion() as db:
            from sqlalchemy import select

            filas = (
                await db.execute(
                    select(Concepto.id, Concepto.nombre_canonico, Concepto.sinonimos, Concepto.codigo)
                )
            ).all()
        conceptos = [
            {"id": f.id, "nombre": f.nombre_canonico, "sinonimos": list(f.sinonimos or ())} for f in filas
        ]
        colores = next(f for f in filas if f.codigo == "C002")
        assert "chaquiras de colores" in (colores.sinonimos or [])
        # Una lista NUEVA con el mismo texto ya cae en el concepto corregido.
        concepto_id, _, puntaje = clasificar("2 chaquiras de colores", conceptos)
        assert concepto_id == colores.id and puntaje >= 0.5

    async def test_el_sinonimo_aprendido_quita_el_prefijo_de_kit(self, cliente):
        from tukit_catalogo.routers.admin import sinonimo_de_renglon

        assert (
            sinonimo_de_renglon("Kit de aseo personal: 1 caja de pañuelos faciales")
            == "caja de pañuelos faciales"
        )
        assert sinonimo_de_renglon("Una caja de pasteles secos") == "caja de pasteles secos"
        assert sinonimo_de_renglon("2 cuadernos cuadriculados") == "cuadernos cuadriculados"
        assert sinonimo_de_renglon("x") is None
        # Un titulo de libro o una frase larga son unicos: no generalizan y ensuciarian el concepto.
        assert sinonimo_de_renglon("Te amo, peladita. Albeiro Echavarría. Editorial Norma") is None
        assert (
            sinonimo_de_renglon(
                "Kit básico de componentes electrónicos que se emplea a lo largo del bachillerato"
            )
            is None
        )
        assert sinonimo_de_renglon("Broche de batería de 9V") == "broche de batería de 9v"

    async def test_cada_correccion_queda_registrada_con_antes_y_despues(self, cliente):
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item = revision["items"][0]
        await cliente.patch(f"/v1/admin/listas/{vid}/items/{item['item_id']}", json={"cantidad": 5})
        r = await cliente.get("/v1/admin/correcciones")
        assert r.status_code == 200
        cuerpo = r.json()
        fila = next(c for c in cuerpo["correcciones"] if c["item_id"] == item["item_id"])
        assert fila["campo"] == "cantidad"
        assert fila["valor_antes"] == 2 and fila["valor_despues"] == 5
        assert fila["texto_original"] == "2 cuadernos cuadriculados"
        assert cuerpo["por_campo"]["cantidad"] >= 1
