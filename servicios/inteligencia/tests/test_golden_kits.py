"""NFR-PRE-02, PRE-03 y PRE-04: lo que el kit hace con cada renglon de los dorados.

El catalogo falso publica la lista de cada variante aceptada con la cantidad
que leyo la percepcion y sin tipo curado, para que decida el parseo. A cada
renglon le responde lo que `esperado/Gnn.json` dice que el emparejamiento tiene
que dar, con productos sacados de `datos/catalogo/` (los CSV que carga el
catalogo) y, en los tres huecos, con el mismo motivo que da el catalogo real.

Lo que se mide es lo que viene despues: la optimizacion y la respuesta. Tienen
que salir los perfiles que pide la lista (sin preferencias, Ahorrador y Premium:
ADR 0030), ningun SKU ni `producto_canonico_id` fuera del catalogo, una linea
por renglon en cada kit, la aritmetica del empaque y los huecos sin producto y
con un motivo.
"""

from __future__ import annotations

import csv
import json
import math
import uuid
from pathlib import Path

import pytest
from conftest import COLEGIO, CatalogoFalso, opcion, reconocido, renglon
from sqlalchemy import select
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoResolucion
from tukit_inteligencia.modelos.base import PerfilKit

RAIZ = Path(__file__).resolve().parents[3]
GOLDEN = RAIZ / "datos" / "golden"
CATALOGO = RAIZ / "datos" / "catalogo"
ESPERADOS = {
    ruta.stem: json.loads(ruta.read_text()) for ruta in sorted((GOLDEN / "esperado").glob("G*.json"))
}
ACEPTADAS = sorted(v for v, e in ESPERADOS.items() if e["aceptada"])
NIVELES = ("economico", "confiable", "premium")

# Lo que responde el catalogo real a los tres huecos de la lista base
# (`tukit_catalogo.consulta.emparejar` sobre los CSV de `datos/catalogo/`).
MOTIVOS_DEL_CATALOGO = {
    "hueco_catalogo": "Entendimos arena decorativa y el catalogo no tiene producto.",
    "abstencion": (
        "El renglon pide compas con tipo=precision y ninguno de los 3 productos lo declara. No ofrezco otro."
    ),
}


def _filas(nombre: str) -> list[dict[str, str]]:
    with (CATALOGO / nombre).open(newline="", encoding="utf-8") as archivo:
        return [fila for fila in csv.DictReader(archivo) if fila.get("activo", "true") == "true"]


def _productos_por_concepto() -> dict[str, list[dict]]:
    """Los productos activos de cada concepto, con el precio vigente mas bajo en pesos."""
    codigos = {f["id"]: f["codigo"] for f in _filas("conceptos.csv")}
    ofertas = {f["id"]: f["producto_canonico_id"] for f in _filas("ofertas_tienda.csv")}
    centavos: dict[str, int] = {}
    for fila in _filas("precios_oferta.csv"):
        if fila["vigente_hasta"] or fila["oferta_id"] not in ofertas:
            continue
        producto = ofertas[fila["oferta_id"]]
        centavos[producto] = min(
            centavos.get(producto, int(fila["valor_centavos"])), int(fila["valor_centavos"])
        )
    por_concepto: dict[str, list[dict]] = {}
    for fila in _filas("productos_canonicos.csv"):
        por_concepto.setdefault(codigos.get(fila["concepto_id"], ""), []).append(
            {
                "producto_id": fila["id"],
                "sku": fila["sku_interno"],
                "nombre": fila["nombre"],
                "marca": fila["marca"] or None,
                "nivel": fila["nivel"],
                "personaje": fila["personaje"] or None,
                "unidades_por_empaque": int(fila.get("unidades_por_empaque") or 1),
                "precio": centavos[fila["id"]] // 100 if fila["id"] in centavos else None,
            }
        )
    return por_concepto


PRODUCTOS = _productos_por_concepto()
SKUS_DEL_CATALOGO = {p["sku"] for lista in PRODUCTOS.values() for p in lista}
IDS_DEL_CATALOGO = {p["producto_id"] for lista in PRODUCTOS.values() for p in lista}


def _opciones(codigo: str) -> list[dict]:
    """Una opcion por nivel: la mas barata con precio, como las que ve el optimizador."""
    salida = []
    for nivel in NIVELES:
        del_nivel = [p for p in PRODUCTOS.get(codigo, []) if p["nivel"] == nivel and p["precio"] is not None]
        if not del_nivel:
            continue
        p = min(del_nivel, key=lambda p: (p["precio"], p["sku"]))
        salida.append(
            opcion(
                p["sku"],
                nivel,
                p["precio"],
                nombre=p["nombre"],
                marca=p["marca"],
                personaje=p["personaje"],
                unidades_por_empaque=p["unidades_por_empaque"],
                producto_id=p["producto_id"],
            )
        )
    return salida


def _respuesta(texto: str, emparejamiento: dict) -> dict | None:
    estado = emparejamiento["estado"]
    if estado == "reconocido":
        return reconocido(texto, emparejamiento["concepto"], _opciones(emparejamiento["concepto"]))
    if estado in MOTIVOS_DEL_CATALOGO:
        return {
            "texto": texto,
            "estado": estado,
            "concepto_codigo": emparejamiento["concepto"],
            "concepto_nombre": emparejamiento["concepto"].lower(),
            "parecido": 1.0,
            "atributos_impuestos": {},
            "motivo": MOTIVOS_DEL_CATALOGO[estado],
            "opciones": [],
        }
    return None  # sin_match: la respuesta por omision de `CatalogoFalso`


def _catalogo(variante: str) -> CatalogoFalso:
    esperado = ESPERADOS[variante]
    respuestas = {}
    for fila in esperado["renglones"]:
        respuesta = _respuesta(fila["texto"], fila["emparejamiento"])
        if respuesta is not None:
            respuestas[fila["texto"]] = respuesta
    return CatalogoFalso(
        grado="Tercero",
        renglones=[
            renglon(n, item["descripcion"], cantidad=item["cantidad"], tipo_item=None, modo_adquisicion=None)
            for n, item in enumerate(esperado["items"], start=1)
        ],
        respuestas=respuestas,
    )


async def _kits(motor, variante: str) -> tuple[dict, list]:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Tercero"}],
        preferencias={},
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo(variante))
    vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
    async with motor.engine.connect() as conexion:
        filas = (
            await conexion.execute(
                select(
                    trabajos.LINEA.c.sku, trabajos.LINEA.c.producto_canonico_id, trabajos.LINEA.c.alternativas
                )
                .select_from(trabajos.LINEA.join(trabajos.KIT, trabajos.KIT.c.id == trabajos.LINEA.c.kit_id))
                .where(trabajos.KIT.c.trabajo_id == trabajo_id)
            )
        ).all()
    return vista, filas


def _por_orden(variante: str) -> dict[int, dict]:
    return {fila["orden"]: fila for fila in ESPERADOS[variante]["renglones"]}


def _lineas(vista: dict):
    for kit in vista["kits"]:
        for linea in kit["lineas"]:
            yield kit, linea


@pytest.mark.parametrize("variante", ACEPTADAS)
class TestLosTresKits:
    @pytest.mark.nfr("NFR-PRE-02")
    async def test_salen_los_tres_perfiles_y_uno_solo_recomendado(self, motor, variante):
        vista, _ = await _kits(motor, variante)

        # Kits a pedido (ADR 0030, efb0827): sin personaje ni `prioridad=equilibrio`
        # ni tope, solo salen los dos extremos.
        perfiles = sorted(k["perfil"] for k in vista["kits"])
        assert perfiles == sorted([PerfilKit.AHORRADOR.value, PerfilKit.PREMIUM.value])
        assert vista["recomendado"]["perfil"] in perfiles

    @pytest.mark.nfr("NFR-PRE-02")
    async def test_cada_renglon_de_la_lista_tiene_su_linea_en_cada_kit(
        self, motor, variante, record_property
    ):
        esperados = _por_orden(variante)

        vista, _ = await _kits(motor, variante)

        sin_origen = [
            (k["perfil"], linea["orden"])
            for k, linea in _lineas(vista)
            if esperados.get(linea["orden"], {}).get("texto") != linea["descripcion"]
        ]
        record_property("lineas", sum(1 for _ in _lineas(vista)))
        record_property("lineas_sin_origen", len(sin_origen))
        assert sin_origen == []
        for kit in vista["kits"]:
            assert [(linea["hijo"], linea["orden"]) for linea in kit["lineas"]] == [
                ("hijo-1", orden) for orden in sorted(esperados)
            ]
        item_por_orden = {}
        for _, linea in _lineas(vista):
            assert item_por_orden.setdefault(linea["orden"], linea["item_id"]) == linea["item_id"]

    @pytest.mark.nfr("NFR-PRE-02")
    async def test_la_linea_lleva_el_concepto_que_el_dorado_espera(self, motor, variante):
        esperados = _por_orden(variante)

        vista, _ = await _kits(motor, variante)

        for _, linea in _lineas(vista):
            emparejamiento = esperados[linea["orden"]]["emparejamiento"]
            if emparejamiento["estado"] == "reconocido":
                assert linea["concepto"] == emparejamiento["concepto"]
                assert linea["estado_resolucion"] == EstadoResolucion.RESUELTO_AUTO.value

    @pytest.mark.nfr("NFR-PRE-02")
    async def test_la_cantidad_y_el_empaque_dan_lo_que_se_compra(self, motor, variante):
        esperados = _por_orden(variante)

        vista, _ = await _kits(motor, variante)

        for kit in vista["kits"]:
            for linea in kit["lineas"]:
                assert linea["cantidad_pedida"] == esperados[linea["orden"]]["parseo"]["cantidad"]
                producto = linea.get("producto_elegido")
                if producto is None:
                    assert (linea["unidades_a_comprar"], linea["subtotal_linea"]) == (0, None)
                    continue
                unidades = math.ceil(linea["cantidad_pedida"] / linea["unidades_por_empaque"])
                assert linea["unidades_a_comprar"] == unidades
                assert linea["subtotal_linea"] == producto["precio"] * unidades
            assert kit["total"] == sum(linea["subtotal_linea"] or 0 for linea in kit["lineas"])

    @pytest.mark.nfr("NFR-PRE-02")
    async def test_lo_informativo_se_muestra_y_no_se_cobra(self, motor, variante):
        informativos = {
            o for o, f in _por_orden(variante).items() if f["emparejamiento"]["nivel"] == "informativo"
        }

        vista, _ = await _kits(motor, variante)

        for kit in vista["kits"]:
            marcadas = {linea["orden"] for linea in kit["lineas"] if linea["informativa"]}
            assert marcadas == informativos
            assert kit["informativas"] == len(informativos)
            for linea in kit["lineas"]:
                if linea["informativa"]:
                    assert "producto_elegido" not in linea
                    assert linea["mensaje"]


@pytest.mark.parametrize("variante", ACEPTADAS)
@pytest.mark.nfr("NFR-PRE-03")
class TestNingunProductoFueraDelCatalogo:
    async def test_ningun_sku_de_los_kits_falta_en_el_catalogo(self, motor, variante, record_property):
        vista, _ = await _kits(motor, variante)

        skus = set()
        for _, linea in _lineas(vista):
            if "producto_elegido" in linea:
                skus.add(linea["producto_elegido"]["sku"])
            skus.update(a["sku"] for a in linea["alternativas"])
        fuera = sorted(skus - SKUS_DEL_CATALOGO)
        record_property("skus_en_kits", len(skus))
        record_property("skus_fuera_del_catalogo", len(fuera))
        assert skus
        assert fuera == []

    async def test_cada_linea_con_producto_apunta_a_un_producto_canonico_del_catalogo(
        self, motor, variante, record_property
    ):
        _, filas = await _kits(motor, variante)

        con_producto = [f for f in filas if f.sku]
        fuera = [f.sku for f in con_producto if str(f.producto_canonico_id) not in IDS_DEL_CATALOGO]
        record_property("lineas_con_producto", len(con_producto))
        record_property("producto_canonico_id_fuera_del_catalogo", len(fuera))
        assert con_producto
        assert fuera == []


@pytest.mark.parametrize("variante", ACEPTADAS)
@pytest.mark.nfr("NFR-PRE-04")
class TestLosHuecos:
    """Los tres huecos: un concepto que no existe, uno sin productos y uno sin el atributo pedido."""

    @staticmethod
    def _huecos(vista: dict, variante: str):
        huecos = {o for o, f in _por_orden(variante).items() if f["emparejamiento"]["nivel"] == "hueco"}
        assert len(huecos) == 3
        return [(k, linea) for k, linea in _lineas(vista) if linea["orden"] in huecos]

    async def test_ningun_hueco_sale_con_un_producto(self, motor, variante, record_property):
        vista, _ = await _kits(motor, variante)

        huecos = self._huecos(vista, variante)
        con_producto = [(k["perfil"], linea["orden"]) for k, linea in huecos if "producto_elegido" in linea]
        record_property("lineas_hueco", len(huecos))
        record_property("huecos_con_producto", len(con_producto))
        assert con_producto == []
        assert all(linea["alternativas"] == [] for _, linea in huecos)

    async def test_cada_hueco_dice_por_que_no_hay_producto(self, motor, variante):
        esperados = _por_orden(variante)

        vista, _ = await _kits(motor, variante)

        for _, linea in self._huecos(vista, variante):
            estado = esperados[linea["orden"]]["emparejamiento"]["estado"]
            if estado == "sin_match":
                assert linea["estado_resolucion"] == EstadoResolucion.SIN_MATCH.value
                assert linea["mensaje"] == "No reconocemos que pide este renglon."
            else:
                assert linea["estado_resolucion"] == EstadoResolucion.HUECO_CATALOGO.value
                assert linea["mensaje"] == MOTIVOS_DEL_CATALOGO[estado]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-39: un hueco del catalogo nunca trae alternativa: `linea_kit.sustitutos` no se escribe ni "
            "sale en la respuesta, aunque la web lo pinta y el catalogo tiene `sustituibilidad_concepto`"
        ),
    )
    async def test_lo_que_el_catalogo_no_tiene_sale_como_no_tengo_con_alternativa(
        self, motor, variante, record_property
    ):
        vista, _ = await _kits(motor, variante)

        no_tengo = [
            linea
            for _, linea in self._huecos(vista, variante)
            if linea["estado_resolucion"] == EstadoResolucion.HUECO_CATALOGO.value
        ]
        con_alternativa = [linea for linea in no_tengo if linea.get("sustitutos") or linea["alternativas"]]
        record_property("lineas_no_tengo", len(no_tengo))
        record_property("lineas_no_tengo_con_alternativa", len(con_alternativa))
        assert no_tengo
        assert len(con_alternativa) == len(no_tengo)
