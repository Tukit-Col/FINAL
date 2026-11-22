# ruff: noqa: F811

from __future__ import annotations

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    _bandeja_de,
    _con_cuadernos_extra,
    _version_revisada_con_renglones,
    cliente,
)
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    PropuestaProducto,
)


async def _aviso_de_repetido(cliente, version_id) -> dict | None:
    avisos = (await cliente.get(f"/v1/admin/listas/{version_id}/avisos")).json()["avisos"]
    return next((a for a in avisos if a["tipo"] == "posible_repetido"), None)


class TestAvisosDeUnaListaRevisada:

    async def test_avisa_el_repetido_el_atributo_ambiguo_y_lo_que_no_tiene_producto(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con_renglones(
            cliente,
            [
                ("Pegante en barra", "colores"),
                ("pegante en barra", "colores"),
                ("cuaderno rayado o cuadriculado", "cuaderno"),
                ("cuaderno ferrocarril", "cuaderno"),
            ],
        )
        avisos = (await cliente.get(f"/v1/admin/listas/{vid}/avisos")).json()["avisos"]
        por_tipo = {(a["tipo"], a["orden"]): a for a in avisos}

        repetido = por_tipo[("posible_repetido", 2)]
        assert repetido["repite_a"] == 1
        assert repetido["texto_repetido"] == "Pegante en barra"
        assert por_tipo[("revisar_atributo", 3)]["atributo"] == "rayado"
        sin = por_tipo[("sin_producto", 4)]
        assert sin["exige"] == {"rayado": "ferrocarril"}
        assert sin["concepto_codigo"] == "C001"

    async def test_un_aviso_descartado_no_vuelve(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente, [("Pegante en barra", "colores"), ("pegante en barra", "colores")]
        )
        aviso = await _aviso_de_repetido(cliente, vid)
        respuesta = await cliente.post(
            f"/v1/admin/listas/{vid}/avisos/descartar",
            json={"item_id": aviso["item_id"], "clave": aviso["clave"]},
        )
        assert respuesta.status_code == 200
        assert await _aviso_de_repetido(cliente, vid) is None

    async def test_es_el_mismo_publica_una_version_donde_no_se_compra(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente, [("Pegante en barra", "colores"), ("pegante en barra", "colores")]
        )
        aviso = await _aviso_de_repetido(cliente, vid)
        respuesta = await cliente.post(
            f"/v1/admin/listas/{vid}/items/{aviso['item_id']}/no-comprar", json={"repite_a": 1}
        )
        assert respuesta.status_code == 201
        nueva = respuesta.json()["version_id"]

        items = (await cliente.get(f"/v1/admin/listas/{nueva}/resueltos")).json()["items"]
        segundo = next(i for i in items if i["orden"] == 2)
        assert segundo["tipo_item"] == "no_comprar"
        assert "linea 1" in segundo["instruccion_colegio"]
        eventos = [f for f in await _bandeja_de(cliente) if f.tipo == "lista_aprobada"]
        assert str(eventos[-1].agregado_id) == nueva
        assert await _aviso_de_repetido(cliente, nueva) is None

    async def test_solo_se_corrige_la_version_vigente(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente, [("Pegante en barra", "colores"), ("pegante en barra", "colores")]
        )
        aviso = await _aviso_de_repetido(cliente, vid)
        await cliente.post(
            f"/v1/admin/listas/{vid}/items/{aviso['item_id']}/no-comprar", json={"repite_a": 1}
        )
        otra_vez = await cliente.post(
            f"/v1/admin/listas/{vid}/items/{aviso['item_id']}/no-comprar", json={"repite_a": 1}
        )
        assert otra_vez.status_code == 409
        assert otra_vez.json()["error"] == "version_no_vigente"


def test_renglones_que_solo_cambian_de_color_no_son_repetidos():
    from types import SimpleNamespace

    from tukit_catalogo.routers.admin import _posibles_repetidos

    base = "carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Colores: {}"
    filas = [
        SimpleNamespace(orden=i, concepto_codigo="C011", tipo_item="util", texto_original=base.format(c))
        for i, c in enumerate(["Amarillo", "Azul", "Rojo", "Verde"], start=1)
    ]
    assert _posibles_repetidos(filas, {}) == {}
    filas.append(
        SimpleNamespace(orden=9, concepto_codigo="C011", tipo_item="util", texto_original=base.format("Azul"))
    )
    assert _posibles_repetidos(filas, {}) == {9: 2}


class TestAprobarCierraLosAvisosAbiertos:
    async def test_aprobar_cierra_los_avisos_que_habia_y_los_registra(self, cliente):
        vid = cliente.ids["abierta"]
        await cliente.post(
            f"/v1/admin/listas/{vid}/items",
            json={"texto_original": "2 cuadernos cuadriculados", "concepto_codigo": "C001"},
        )
        async with app.state.motor.sesion() as db:
            from sqlalchemy import update

            await db.execute(update(PropuestaProducto).values(estado="rechazada"))
            await db.commit()
        antes = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        r = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert r.status_code == 200, r.text
        assert (await cliente.get(f"/v1/admin/listas/{vid}/avisos")).json()["avisos"] == []
        assert antes["total_items"] >= 3

    async def test_una_lista_revisada_no_muestra_avisos_abiertos(self, cliente):
        vid = cliente.ids["cerrada"]
        r = await cliente.get(f"/v1/admin/listas/{vid}/avisos")
        assert r.status_code == 200
        assert r.json()["avisos"] == []
