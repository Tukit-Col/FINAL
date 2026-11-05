"""NFR-PRE-02, PRE-03 y PRE-04: el emparejamiento contra el oro de los dorados.

`datos/golden/esperado/oracle.json` dice que concepto espera un humano para
cada renglon de las listas de los dorados, y para ocho redacciones mas
dificiles. Aqui cada texto pasa por `consulta.emparejar` sobre el catalogo de
`datos/catalogo/` (los CSV que carga el catalogo) y sin embeddings: sin clave
no hay canal semantico, y eso es lo que corre hoy.

- exacto y facil: el top-1 se exige;
- dificil: la tasa de acierto se reporta, no se exige;
- hueco: ningun producto, y un motivo;
- informativo: se reporta, porque lo resuelve el parseo antes de llegar aqui.

En todos los casos, ninguna opcion puede traer un producto que no este en el
catalogo.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from tukit_catalogo.consulta import emparejar

RAIZ = Path(__file__).resolve().parents[3]
CATALOGO = RAIZ / "datos" / "catalogo"
ORO = json.loads((RAIZ / "datos" / "golden" / "esperado" / "oracle.json").read_text())["pares"]
HUECOS = {"sin_match", "hueco_catalogo", "abstencion"}


def _filas(nombre: str) -> list[dict[str, str]]:
    with (CATALOGO / nombre).open(newline="", encoding="utf-8") as archivo:
        return [fila for fila in csv.DictReader(archivo) if fila.get("activo", "true") == "true"]


def _lista(campo: str) -> list[str]:
    return [parte for parte in campo.split("|") if parte]


CONCEPTOS = [
    {
        "id": fila["id"],
        "codigo": fila["codigo"],
        "nombre": fila["nombre_canonico"],
        "sinonimos": _lista(fila["sinonimos"]),
        "discriminantes": tuple(_lista(fila["atributos_discriminantes"])),
        "embedding": None,
    }
    for fila in _filas("conceptos.csv")
]


def _precios() -> dict[str, int]:
    """El precio vigente mas bajo de cada producto, en pesos."""
    ofertas = {f["id"]: f["producto_canonico_id"] for f in _filas("ofertas_tienda.csv")}
    centavos: dict[str, int] = {}
    for fila in _filas("precios_oferta.csv"):
        if fila["vigente_hasta"] or fila["oferta_id"] not in ofertas:
            continue
        producto = ofertas[fila["oferta_id"]]
        valor = int(fila["valor_centavos"])
        centavos[producto] = min(centavos.get(producto, valor), valor)
    return {producto: valor // 100 for producto, valor in centavos.items()}


PRECIOS = _precios()
PRODUCTOS = [
    {
        "id": fila["id"],
        "concepto_id": fila["concepto_id"],
        "sku": fila["sku_interno"],
        "nombre": fila["nombre"],
        "nivel": fila["nivel"],
        "personaje": fila["personaje"] or None,
        "marca": fila["marca"] or None,
        "atributos": json.loads(fila["atributos"] or "{}"),
        "unidades_por_empaque": int(fila.get("unidades_por_empaque") or 1),
        "precio_cop": PRECIOS.get(fila["id"]),
    }
    for fila in _filas("productos_canonicos.csv")
]
SKUS = {p["sku"] for p in PRODUCTOS}
IDS = {p["id"] for p in PRODUCTOS}


def _pares(*niveles: str) -> list:
    return [pytest.param(par, id=par["texto"]) for par in ORO if par["nivel"] in niveles]


class TestElOroEsCoherente:
    def test_el_oro_cubre_los_cinco_niveles(self):
        assert {par["nivel"] for par in ORO} == {"exacto", "facil", "dificil", "hueco", "informativo"}
        assert len({par["texto"] for par in ORO}) == len(ORO)

    def test_cada_concepto_esperado_existe_en_el_catalogo(self):
        codigos = {c["codigo"] for c in CONCEPTOS}
        assert {par["concepto"] for par in ORO if par["concepto"]} <= codigos


@pytest.mark.nfr("NFR-PRE-02")
class TestTop1:
    @pytest.mark.parametrize("par", _pares("exacto", "facil"))
    def test_exacto_y_facil_dan_el_concepto_esperado(self, par):
        resultado = emparejar(par["texto"], CONCEPTOS, PRODUCTOS)

        assert (resultado.estado, resultado.concepto_codigo) == ("reconocido", par["concepto"])
        assert resultado.opciones

    def test_la_tasa_de_acierto_de_los_dificiles_se_reporta(self, record_property):
        dificiles = [par for par in ORO if par["nivel"] == "dificil"]

        fallados = [
            par["texto"]
            for par in dificiles
            if emparejar(par["texto"], CONCEPTOS, PRODUCTOS).concepto_codigo != par["concepto"]
        ]

        acertados = len(dificiles) - len(fallados)
        record_property("dificiles", len(dificiles))
        record_property("dificiles_acertados", acertados)
        record_property("tasa_acierto_dificil", round(acertados / len(dificiles), 4))
        record_property("dificiles_fallados", " | ".join(fallados))
        assert dificiles

    @pytest.mark.parametrize("par", _pares("informativo"))
    def test_lo_informativo_llega_al_catalogo_sin_producto(self, par, record_property):
        resultado = emparejar(par["texto"], CONCEPTOS, PRODUCTOS)

        record_property("estado", resultado.estado)
        assert resultado.estado == par["estado"]
        # Desde oe5 el diccionario de ingles «disponible en casa» se reconoce en C034, que trae
        # productos (oracle recalibrado en `construir.RECALIBRADO_CATALOGO`): no se compra porque
        # el parseo lo deja en `no_comprar` con cantidad 0. Sin producto solo se exige al hueco.
        if par["estado"] in HUECOS:
            assert resultado.opciones == ()


@pytest.mark.nfr("NFR-PRE-04")
class TestHuecos:
    @pytest.mark.parametrize("par", _pares("hueco"))
    def test_un_hueco_no_trae_producto_y_dice_por_que(self, par, record_property):
        resultado = emparejar(par["texto"], CONCEPTOS, PRODUCTOS)

        record_property("estado", resultado.estado)
        assert resultado.estado == par["estado"]
        assert resultado.estado in HUECOS
        assert resultado.opciones == ()
        assert resultado.motivo.strip()


@pytest.mark.nfr("NFR-PRE-03")
class TestNingunaOpcionFueraDelCatalogo:
    def test_ninguna_opcion_del_oro_sale_de_fuera_del_catalogo(self, record_property):
        opciones = [o for par in ORO for o in emparejar(par["texto"], CONCEPTOS, PRODUCTOS).opciones]

        fuera = sorted({o.sku for o in opciones if o.sku not in SKUS or o.producto_id not in IDS})
        record_property("opciones", len(opciones))
        record_property("opciones_fuera_del_catalogo", len(fuera))
        assert opciones
        assert fuera == []
