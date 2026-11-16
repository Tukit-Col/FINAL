"""Editar, curar, agregar y quitar renglones de una version sin revisar.

Lo que protegen, mas alla de que las rutas respondan: que una version YA
REVISADA no se pueda editar (la puerta que `descubrir` cuida en el CLI vale
igual por HTTP).
"""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
# ruff: noqa: F811

from __future__ import annotations

import uuid

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    _con_cuadernos_extra,
    _version_revisada_con,
    cliente,
)
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
)


class TestEditarUnRenglon:
    async def test_editar_persiste_sobre_una_version_sin_revisar(self, cliente):
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][1]["item_id"]

        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}",
            json={"concepto_codigo": "C002", "cantidad": 3, "requiere_revision": False},
        )
        assert respuesta.status_code == 200

        despues = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        editado = despues["items"][1]
        assert editado["concepto"]["codigo"] == "C002"
        assert editado["cantidad"] == 3
        assert editado["requiere_revision"] is False

    async def test_editar_una_version_revisada_se_rechaza(self, cliente):
        vid = cliente.ids["cerrada"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][0]["item_id"]
        respuesta = await cliente.patch(f"/v1/admin/listas/{vid}/items/{item_id}", json={"cantidad": 9})
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_ya_revisada"

    async def test_quitar_un_concepto_sin_marcar_revision_se_rechaza(self, cliente):
        # El CHECK del modelo: un renglon sin concepto SIEMPRE requiere revision.
        # La API lo dice como error de dominio antes de que la base lo grite.
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][0]["item_id"]
        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}",
            json={"concepto_codigo": None, "requiere_revision": False},
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "renglon_sin_concepto_va_a_revision"
        # Y el renglon queda como estaba: con su concepto.
        despues = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]
        assert despues["concepto"] == revision["items"][0]["concepto"]


async def _cuaderno_filtra_por(cliente, discriminantes: list[str]) -> None:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tabla = Base.metadata.tables["concepto"]
        await conexion.execute(
            tabla.update()
            .where(tabla.c.id == cliente.ids["cuaderno"])
            .values(atributos_discriminantes=discriminantes)
        )
        await db.commit()


class TestCurarLosAtributosDeUnRenglon:
    """Curar lo que se exige desde la pantalla de revision, no desde el CSV.

    La revision muestra lo leido del texto y lo curado por separado (con la
    misma regla de la ruta rapida), y el PATCH guarda la curaduria solo con
    claves que el concepto de verdad filtra.
    """

    async def test_la_revision_separa_lo_leido_de_lo_curado(self, cliente):
        await _cuaderno_filtra_por(cliente, ["rayado", "hojas"])
        vid = cliente.ids["abierta"]
        cuaderno, sin_concepto = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"]
        assert cuaderno["atributos_discriminantes"] == ["rayado", "hojas"]
        assert cuaderno["atributos_leidos"] == {"rayado": "cuadriculado"}
        assert cuaderno["atributos"] == {}
        assert cuaderno["atributos_exigidos"] == {"rayado": "cuadriculado"}
        assert cuaderno["atributos_deducidos"] == []
        # Sin concepto no hay nada que exigir ni que curar.
        assert sin_concepto["atributos_discriminantes"] == []
        assert sin_concepto["atributos_exigidos"] == {}

    async def test_el_mas_de_uno_deducido_se_marca_como_deducido(self, cliente):
        # `chaquiras` en plural con cantidad uno: el texto no dice cuantas, la
        # ruta rapida exige "mas de uno". El revisor tiene que saber que eso no
        # lo escribio el colegio.
        async with app.state.motor.sesion() as db:
            conexion = await db.connection()
            tabla = Base.metadata.tables["concepto"]
            await conexion.execute(
                tabla.update()
                .where(tabla.c.id == cliente.ids["colores"])
                .values(atributos_discriminantes=["unidades"])
            )
            await db.commit()
        vid = cliente.ids["abierta"]
        item_id = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][1]["item_id"]
        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}",
            json={"concepto_codigo": "C002", "requiere_revision": False},
        )
        assert respuesta.status_code == 200
        chaquiras = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][1]
        assert chaquiras["atributos_leidos"] == {"unidades": 2}
        assert chaquiras["atributos_deducidos"] == ["unidades"]

    async def test_curar_cambia_un_valor_quita_otro_con_asterisco_y_agrega_uno(self, cliente):
        await _cuaderno_filtra_por(cliente, ["rayado", "hojas"])
        vid = cliente.ids["abierta"]
        item_id = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]["item_id"]

        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}", json={"atributos": {"rayado": "*", "hojas": 100}}
        )
        assert respuesta.status_code == 200

        cuaderno = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]
        assert cuaderno["atributos"] == {"rayado": "*", "hojas": 100}
        # Lo leido no cambia: es el texto. Lo exigido si.
        assert cuaderno["atributos_leidos"] == {"rayado": "cuadriculado"}
        assert cuaderno["atributos_exigidos"] == {"hojas": 100}

    async def test_quitar_la_curaduria_vuelve_a_lo_leido(self, cliente):
        await _cuaderno_filtra_por(cliente, ["rayado", "hojas"])
        vid = cliente.ids["abierta"]
        item_id = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]["item_id"]
        url = f"/v1/admin/listas/{vid}/items/{item_id}"
        assert (await cliente.patch(url, json={"atributos": {"rayado": "*"}})).status_code == 200
        assert (await cliente.patch(url, json={"atributos": {}})).status_code == 200

        cuaderno = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]
        assert cuaderno["atributos_exigidos"] == {"rayado": "cuadriculado"}

    async def test_una_clave_que_el_concepto_no_filtra_se_rechaza(self, cliente):
        # La ruta rapida la ignoraria en silencio: el revisor creeria haberla curado.
        await _cuaderno_filtra_por(cliente, ["rayado"])
        vid = cliente.ids["abierta"]
        item_id = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]["item_id"]
        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}", json={"atributos": {"color": "rojo"}}
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "atributo_no_exigible"
        assert "color" in respuesta.json()["mensaje"]

    async def test_lo_que_el_renglon_ya_traia_no_se_rechaza_si_no_se_toco(self, cliente):
        # Curado antes para otro concepto: devolver el mapa entero no debe fallar.
        await _cuaderno_filtra_por(cliente, ["rayado"])
        vid = cliente.ids["abierta"]
        item_id = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]["item_id"]
        async with app.state.motor.sesion() as db:
            conexion = await db.connection()
            tabla = Base.metadata.tables["item_lista_oficial"]
            await conexion.execute(
                tabla.update().where(tabla.c.id == uuid.UUID(item_id)).values(atributos={"color": "rojo"})
            )
            await db.commit()
        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}",
            json={"atributos": {"color": "rojo", "rayado": "*"}},
        )
        assert respuesta.status_code == 200
        cuaderno = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]
        assert cuaderno["atributos"] == {"color": "rojo", "rayado": "*"}
        # Pero cambiarle el valor si es curar algo que no filtra.
        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}", json={"atributos": {"color": "azul"}}
        )
        assert respuesta.status_code == 422

    async def test_un_valor_que_no_es_simple_se_rechaza(self, cliente):
        await _cuaderno_filtra_por(cliente, ["rayado"])
        vid = cliente.ids["abierta"]
        item_id = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]["item_id"]
        for malo in ({"rayado": ["a", "b"]}, ["rayado"]):
            respuesta = await cliente.patch(
                f"/v1/admin/listas/{vid}/items/{item_id}", json={"atributos": malo}
            )
            assert respuesta.status_code == 422
            assert respuesta.json()["error"] == "atributos_invalido"

    async def test_lo_exigido_de_la_revision_es_lo_que_usa_la_ruta_rapida(self, cliente):
        # La misma regla, no una copia: sobre una version revisada coinciden.
        await _con_cuadernos_extra(cliente, discriminantes=["rayado", "hojas"])
        vid = await _version_revisada_con(
            cliente, "cuaderno ferrocarril de 100 hojas", atributos={"rayado": "rayado", "hojas": "*"}
        )
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"][0]
        resuelto = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert revision["atributos_leidos"] == {"rayado": "ferrocarril", "hojas": 100}
        assert revision["atributos_exigidos"] == resuelto["atributos_impuestos"] == {"rayado": "rayado"}


class TestAgregarYQuitarRenglon:
    async def test_agregar_toma_el_siguiente_orden(self, cliente):
        vid = cliente.ids["abierta"]
        respuesta = await cliente.post(
            f"/v1/admin/listas/{vid}/items",
            json={"texto_original": "1 borrador", "cantidad": 1, "concepto_codigo": "C001"},
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["orden"] == 3

    async def test_quitar_saca_el_renglon(self, cliente):
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][0]["item_id"]
        assert (await cliente.delete(f"/v1/admin/listas/{vid}/items/{item_id}")).status_code == 204
        despues = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert len(despues["items"]) == 1

    async def test_agregar_en_una_version_revisada_se_rechaza(self, cliente):
        vid = cliente.ids["cerrada"]
        respuesta = await cliente.post(
            f"/v1/admin/listas/{vid}/items",
            json={"texto_original": "1 regla", "concepto_codigo": "C001"},
        )
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_ya_revisada"
        textos = [
            i["texto_original"]
            for i in (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"]
        ]
        assert "1 regla" not in textos
