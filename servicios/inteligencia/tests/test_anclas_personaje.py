from __future__ import annotations

import logging
import uuid

import pytest
from _ayudas_inteligencia import (
    COLEGIO,
    CatalogoDosPersonajes,
    catalogo_realista,
    catalogo_verificado,
    crear_y_procesar,
)
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion
from tukit_inteligencia.optimizador import CONCEPTOS_ANCLA, Candidato, KitArmado, LineaKit, anclar_personaje
from tukit_inteligencia.remoto import elegir_producto_de_personaje


def _linea(orden: int, concepto: str | None, personaje: str | None, precio: int) -> LineaKit:
    elegido = Candidato(
        sku=f"SKU-{orden}",
        nombre=f"Producto {orden}",
        nivel="confiable",
        precio_cop=precio,
        personaje=personaje,
    )
    return LineaKit(
        hijo="hijo-1",
        orden=orden,
        descripcion=f"item {orden}",
        tipo="util",
        estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
        cantidad_pedida=1,
        unidad_base="unidad",
        unidades_por_empaque=1,
        unidades_a_comprar=1,
        informativa=False,
        elegido=elegido,
        precio_unitario_cop=precio,
        subtotal_cop=precio,
        concepto_codigo=concepto,
    )


def _kit_con_conceptos() -> KitArmado:
    lineas = (
        _linea(1, "C005", "pikachu", 1000),
        _linea(2, "C086", "pikachu", 40000),
        _linea(3, "C020", None, 500),
        _linea(4, "C001", "pikachu", 6000),
        _linea(5, "C011", "pikachu", 9000),
        _linea(6, "C009", "pikachu", 15000),
    )
    total = sum(x.subtotal_cop or 0 for x in lineas)
    return KitArmado(
        perfil="Fan",
        total_cop=total,
        objetivos={"costo": total, "fidelidad": 1.0, "disponibilidad": 1.0},
        lineas=lineas,
        consolidaciones=(),
    )


class TestAnclarPersonaje:
    def _conceptos(self, lineas: tuple[LineaKit, ...]) -> list[str | None]:
        return [linea.orden for linea in lineas]

    def test_sube_los_cuatro_anclas_al_tope_en_orden_canonico(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, "pikachu")

        primeros_cuatro = [linea.orden for linea in anclado.lineas[:4]]
        assert primeros_cuatro == [4, 6, 5, 2]
        assert [linea.orden for linea in anclado.lineas[4:]] == [1, 3]

    def test_no_cambia_totales_ni_consolidaciones(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, "pikachu")

        assert anclado.total_cop == kit.total_cop
        assert anclado.consolidaciones == kit.consolidaciones
        assert len(anclado.lineas) == len(kit.lineas)
        assert {linea.orden for linea in anclado.lineas} == {linea.orden for linea in kit.lineas}

    def test_el_personaje_se_compara_normalizado(self):
        anclado = anclar_personaje(_kit_con_conceptos(), "Pi-ka chu")
        assert [linea.orden for linea in anclado.lineas[:4]] == [4, 6, 5, 2]

    def test_personaje_none_no_toca_el_kit(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, None)
        assert anclado is kit

    def test_sin_ancla_del_personaje_pedido_devuelve_igual(self):
        kit = _kit_con_conceptos()
        anclado = anclar_personaje(kit, "batman")
        assert [linea.orden for linea in anclado.lineas] == [linea.orden for linea in kit.lineas]


@pytest.fixture(autouse=True)
def _avisos_de_ancla_limpios():
    trabajos._ANCLAS_AVISADAS.clear()
    yield
    trabajos._ANCLAS_AVISADAS.clear()


class TestAnclasPorHijo:
    async def test_un_hijo_cuatro_anclas_estables(self):
        primera = await trabajos.anclas_por_hijo(catalogo_realista(), {"hijo-1": "spiderman"})
        segunda = await trabajos.anclas_por_hijo(catalogo_realista(), {"hijo-1": "spiderman"})
        skus = {c: [p["sku"] for p in ps] for c, ps in primera["hijo-1"].items()}
        assert set(skus) == set(CONCEPTOS_ANCLA)
        assert skus == {c: [p["sku"] for p in ps] for c, ps in segunda["hijo-1"].items()}

    async def test_ancla_no_surtida_se_registra(self, caplog):
        with caplog.at_level(logging.WARNING, logger="tukit_inteligencia.trabajos"):
            r = await trabajos.anclas_por_hijo(catalogo_realista(), {"hijo-1": "batman"})
        assert r == {}
        assert "batman" in caplog.text
        assert "C001" in caplog.text

    async def test_mismo_personaje_se_consulta_una_vez(self):
        catalogo = catalogo_realista()
        r = await trabajos.anclas_por_hijo(catalogo, {"hijo-1": "spiderman", "hijo-2": "Spiderman"})
        assert catalogo.llamadas.count("producto_de_personaje") == 4
        assert r["hijo-1"] is r["hijo-2"]

    async def test_spider_man_y_spiderman_comparten_la_consulta(self):
        catalogo = catalogo_realista()
        r = await trabajos.anclas_por_hijo(catalogo, {"hijo-1": "Spider-Man", "hijo-2": "spiderman"})
        assert catalogo.llamadas.count("producto_de_personaje") == 4
        assert r["hijo-1"] is r["hijo-2"]


async def test_los_avisos_de_ancla_tienen_tope():
    catalogo = catalogo_realista()
    for i in range(trabajos._TOPE_ANCLAS_AVISADAS):
        await trabajos.anclas_por_hijo(catalogo, {"hijo-1": f"inventado{i}"})
    assert len(trabajos._ANCLAS_AVISADAS) == trabajos._TOPE_ANCLAS_AVISADAS


class TestElegirProductoDePersonaje:

    def test_elegir_producto_de_personaje_es_determinista(self):
        a = {"sku": "B", "nivel": "confiable", "precio_desde": 100}
        b = {"sku": "A", "nivel": "confiable", "precio_desde": 100}
        assert elegir_producto_de_personaje([a, b])["sku"] == "A"
        assert elegir_producto_de_personaje([b, a])["sku"] == "A"
        assert elegir_producto_de_personaje([]) is None

    def test_prefiere_con_precio_y_confiable(self):
        sin_precio = {"sku": "A", "nivel": "confiable", "precio_desde": None}
        premium = {"sku": "B", "nivel": "premium", "precio_desde": 10}
        economico = {"sku": "C", "nivel": "economico", "precio_desde": 5}
        confiable_caro = {"sku": "D", "nivel": "confiable", "precio_desde": 900}
        confiable_barato = {"sku": "E", "nivel": "confiable", "precio_desde": 800}
        assert elegir_producto_de_personaje([sin_precio, premium])["sku"] == "B"
        assert elegir_producto_de_personaje([premium, economico])["sku"] == "C"
        assert elegir_producto_de_personaje([economico, confiable_caro])["sku"] == "D"
        assert elegir_producto_de_personaje([confiable_caro, confiable_barato])["sku"] == "E"


class TestPersonajeLlegaAlFan:
    async def test_el_fan_trae_spiderman_en_sus_anclas_aunque_resueltos_no_lo_tenga(self, motor):
        catalogo = catalogo_realista()
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}, "pesos": {"personaje": 1}}
        trabajo_id, _ = await crear_y_procesar(motor, catalogo, preferencias=prefs)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert "producto_de_personaje" in catalogo.llamadas
        fan = next(k for k in vista["kits"] if k["perfil"] == "Fan")

        anclas = {
            li["concepto"]: li["producto_elegido"]
            for li in fan["lineas"]
            if li.get("concepto") in {"C001", "C009"} and li.get("producto_elegido")
        }
        assert anclas, "el Fan debe tener las anclas con producto elegido"
        assert all(p["personaje"] == "spiderman" for p in anclas.values())
        assert all(p["sku"].startswith("SPIDEY-") for p in anclas.values())

        ahorrador = next(k for k in vista["kits"] if k["perfil"] == "Ahorrador")
        assert all((li.get("producto_elegido") or {}).get("personaje") is None for li in ahorrador["lineas"])

    async def test_sin_personaje_pedido_no_hay_fan_ni_se_pide_personaje(self, motor):
        catalogo = catalogo_realista()
        trabajo_id, _ = await crear_y_procesar(motor, catalogo, preferencias={})
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)

        assert "producto_de_personaje" not in catalogo.llamadas
        assert all(k["perfil"] != "Fan" for k in vista["kits"])


class TestDosHijosEndToEnd:
    async def test_cada_hijo_recibe_su_personaje_en_el_fan(self, motor):
        base = catalogo_verificado(personaje=None)
        catalogo = CatalogoDosPersonajes(revisada=True, items_resueltos=base.items_resueltos)
        prefs = {
            "personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["frozen"]},
            "pesos": {"personaje": 1},
        }
        respuesta = await trabajos.crear(
            motor,
            hijos=[
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Cuarto"},
            ],
            preferencias=prefs,
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=catalogo)
        vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
        fan = next(k for k in vista["kits"] if k["perfil"] == "Fan")

        personajes = {
            (li["hijo"], (li.get("producto_elegido") or {}).get("personaje"))
            for li in fan["lineas"]
            if li.get("concepto") in {"C001", "C009"}
        }
        assert ("hijo-1", "spiderman") in personajes
        assert ("hijo-2", "frozen") in personajes
        assert ("hijo-1", "frozen") not in personajes
        assert ("hijo-2", "spiderman") not in personajes
        assert vista["personajes_por_hijo"] == {"hijo-1": ["spiderman"], "hijo-2": ["frozen"]}
        assert isinstance(fan["personaje_sin_encaje"], list)
        assert "personaje_sin_encaje" not in fan["objetivos"]
