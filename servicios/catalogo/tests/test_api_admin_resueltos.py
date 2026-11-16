"""La ruta rapida de una version revisada: renglones resueltos con sus candidatos."""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
# ruff: noqa: F811

from __future__ import annotations

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    COLEGIO,
    _con_cuadernos_extra,
    _marcar_uno_por_estudiante,
    _version_revisada_con,
    _version_revisada_con_renglones,
    cliente,
)
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
)

CAMPOS_CANDIDATO = {
    "sku",
    "nombre",
    "nivel",
    "precio_cop",
    "producto_id",
    "marca",
    "personaje",
    "imagen_url",
    "unidad_base",
    "unidades_por_empaque",
    "atributos",
    "cumple",
}


class TestResueltosLaRutaRapida:
    async def test_una_version_revisada_trae_items_concepto_y_candidatos(self, cliente):
        vid = cliente.ids["cerrada"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/resueltos")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["revisada"] is True
        assert cuerpo["grado"] == "Quinto"
        assert cuerpo["anio_lectivo"] == 2026
        assert cuerpo["colegio_id"] == str(COLEGIO)

        # Orden por `orden`: primero el cuaderno resuelto, luego la agenda.
        assert [i["orden"] for i in cuerpo["items"]] == [1, 2]
        cuaderno = cuerpo["items"][0]
        assert cuaderno["concepto_codigo"] == "C001"
        assert cuaderno["concepto_nombre"] == "cuaderno"
        assert cuaderno["texto_original"] == "1 cuaderno cosido"
        assert cuaderno["cantidad"] == 1
        # Los candidatos curados: uno por nivel, con precio.
        candidatos = cuaderno["candidatos"]
        assert {c["nivel"] for c in candidatos} == {"economico", "confiable", "premium"}
        eco = next(c for c in candidatos if c["nivel"] == "economico")
        assert eco["precio_cop"] == 4500
        assert eco["sku"] == "TK-C001-ECO"
        assert eco["cumple"] is True

    async def test_el_renglon_de_compra_directa_no_trae_candidatos(self, cliente):
        vid = cliente.ids["cerrada"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()
        agenda = cuerpo["items"][1]
        assert agenda["concepto_codigo"] is None
        assert agenda["concepto_nombre"] is None
        assert agenda["candidatos"] == []
        assert agenda["instruccion_colegio"] == "Se paga en la tesoreria del colegio."

    async def test_los_candidatos_tienen_las_llaves_del_dataclass(self, cliente):
        vid = cliente.ids["cerrada"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()
        candidatos = cuerpo["items"][0]["candidatos"]
        assert candidatos
        for candidato in candidatos:
            assert set(candidato.keys()) == CAMPOS_CANDIDATO
            assert isinstance(candidato["unidades_por_empaque"], int)
            assert candidato["unidades_por_empaque"] >= 1
            assert candidato["precio_cop"] is None or isinstance(candidato["precio_cop"], int)
            assert isinstance(candidato["atributos"], dict)

    async def test_un_concepto_sin_atributos_que_filtren_ofrece_todos_sus_productos_lisos(self, cliente):
        # Antes salia uno por nivel (tres a lo sumo) aunque el concepto tuviera
        # cuarenta: el kit nunca veia el resto del catalogo.
        await _con_cuadernos_extra(cliente)
        vid = cliente.ids["cerrada"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()
        skus = {c["sku"] for c in cuerpo["items"][0]["candidatos"]}
        assert {"TK-C001-ECO", "TK-C001-CON", "TK-C001-PRE", "TK-REV-RAYADO"} <= skus
        # El de personaje no entra mientras haya lisos.
        assert "TK-REV-CARS" not in skus

    async def test_un_renglon_que_exige_un_atributo_solo_ofrece_los_que_lo_cumplen(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno rayado de 100 hojas")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert [c["sku"] for c in item["candidatos"]] == ["TK-REV-RAYADO"]
        assert item["atributos_impuestos"] == {"rayado": "rayado"}
        assert all(c["cumple"] for c in item["candidatos"])

    async def test_si_ningun_producto_cumple_no_hay_candidatos(self, cliente):
        # Un hueco, no un sustituto: el kit recomendaba un oleo para un acrilico.
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno ferrocarril")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert item["candidatos"] == []
        assert item["atributos_impuestos"] == {"rayado": "ferrocarril"}

    async def test_el_personaje_entra_solo_si_es_el_unico_que_cumple(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno doble linea")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert [c["sku"] for c in item["candidatos"]] == ["TK-REV-CARS"]

    async def test_lo_que_el_revisor_corrigio_en_la_curaduria_manda_sobre_lo_leido(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno ferrocarril", atributos={"rayado": "rayado"})
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert [c["sku"] for c in item["candidatos"]] == ["TK-REV-RAYADO"]

    async def test_un_renglon_con_varios_valores_se_marca_para_revisar(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno rayado o cuadriculado")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert item["atributos_impuestos"] == {}
        assert item["atributos_por_revisar"] == ["rayado"]

    async def test_dice_si_el_concepto_es_uno_por_estudiante(self, cliente):
        await _marcar_uno_por_estudiante(cliente, "colores")
        vid = await _version_revisada_con_renglones(
            cliente, [("Caja de colores", "colores"), ("colores", "colores")]
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["uno_por_estudiante"] for i in items] == [True, True]
        # Lo que se junta solo no se marca como repetido: no hay nada que revisar.
        assert [i["posible_repetido_de"] for i in items] == [None, None]

    async def test_un_consumible_casi_igual_a_otro_se_marca_como_posible_repetido(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente, [("Pegante en barra", "colores"), ("cinta", "colores"), ("pegante en barra", "colores")]
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["posible_repetido_de"] for i in items] == [None, None, 1]

    async def test_dos_colores_de_la_misma_pintura_no_son_repetidos(self, cliente):
        async with app.state.motor.sesion() as db:
            conexion = await db.connection()
            tabla = Base.metadata.tables["concepto"]
            await conexion.execute(
                tabla.update()
                .where(tabla.c.id == cliente.ids["colores"])
                .values(atributos_discriminantes=["color"])
            )
            await db.commit()
        vid = await _version_revisada_con_renglones(
            cliente,
            [
                ("Pinturas acrilicas tubo de 45 cc: cian", "colores"),
                ("Pinturas acrilicas tubo de 45 cc: magenta", "colores"),
            ],
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["posible_repetido_de"] for i in items] == [None, None]

    async def test_un_cuaderno_por_materia_no_es_un_repetido(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente,
            [
                ("cuaderno cuadriculado 100 hojas", "cuaderno"),
                ("cuaderno cuadriculado 100 hojas", "cuaderno"),
            ],
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["posible_repetido_de"] for i in items] == [None, None]

    async def test_una_version_sin_revisar_es_409(self, cliente):
        vid = cliente.ids["abierta"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/resueltos")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_no_revisada"
