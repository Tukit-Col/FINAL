"""NFR-MAN-01: `nivelar` sobre los CSV: lo que lee, lo que imprime y, sobre todo, lo que escribe.

`test_nivelar` fija la regla pura (`reacomodar`: permutar etiquetas, respetar al
personaje). Falta el borde con el disco, que es donde un error cuesta caro: el
script reescribe `productos_canonicos.csv` y `productos_procedencia.csv`, que son
la FUENTE del cargador, y si renombra un SKU en una y no en la otra deja una fila
de procedencia apuntando a un producto que ya no existe.

Todas las pruebas redirigen `nivelar.DATOS` a un directorio temporal con CSV
ficticios: ninguna toca `datos/catalogo` del repo. Lo que se vigila:

  - el ensayo (sin `--escribir`) imprime el diff y NO escribe nada;
  - al escribir, el nivel, el SKU y la calidad se re-acunan juntos, y la
    procedencia sigue al SKU nuevo;
  - el SKU de un producto aprobado en revision (`TK-REV-*`) y su calidad fija no
    se tocan, solo su etiqueta de nivel;
  - una permutacion que chocaria un SKU aborta con codigo 1 y sin escribir;
  - un catalogo ya ordenado no produce cambios.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest
from tukit_catalogo import nivelar

pytestmark = pytest.mark.nfr("NFR-MAN-01")

COLUMNAS_PRODUCTO = [
    "id",
    "concepto_id",
    "sku_interno",
    "nombre",
    "marca",
    "nivel",
    "personaje",
    "quality_score",
    "activo",
    "es_representante_canonico",
]
COLUMNAS_PROCEDENCIA = ["producto_id", "sku_interno", "fichero_fuente"]


def _producto(pid, concepto, sku, nivel, *, personaje="", calidad="0.700", representante="true", nombre=None):
    return {
        "id": pid,
        "concepto_id": concepto,
        "sku_interno": sku,
        "nombre": nombre or f"Producto ficticio {pid}",
        "marca": "Marca Ficticia",
        "nivel": nivel,
        "personaje": personaje,
        "quality_score": calidad,
        "activo": "true",
        "es_representante_canonico": representante,
    }


def _escribir(directorio: Path, nombre: str, filas: list[dict[str, str]]) -> None:
    with (directorio / f"{nombre}.csv").open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


def _leer(directorio: Path, nombre: str) -> list[dict[str, str]]:
    with (directorio / f"{nombre}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _ofertas_y_precios(directorio: Path, precios_por_producto: dict[str, int]) -> None:
    """Una oferta con un precio por producto: lo justo para que `nivelar` tenga con que ordenar."""
    ofertas = [
        {"id": f"o-{pid}", "producto_canonico_id": pid, "tienda_id": "t1"} for pid in precios_por_producto
    ]
    precios = [
        {"id": f"pr-{pid}", "oferta_id": f"o-{pid}", "valor_centavos": str(valor)}
        for pid, valor in precios_por_producto.items()
    ]
    _escribir(directorio, "ofertas_tienda", ofertas)
    _escribir(directorio, "precios_oferta", precios)


def _correr(monkeypatch, *argumentos: str) -> int:
    monkeypatch.setattr(sys, "argv", ["nivelar", *argumentos])
    return nivelar._principal()


@pytest.fixture()
def datos(tmp_path, monkeypatch) -> Path:
    """Un directorio de datos vacio al que `nivelar` queda apuntando."""
    directorio = tmp_path / "catalogo"
    directorio.mkdir()
    monkeypatch.setattr(nivelar, "DATOS", directorio)
    return directorio


def _catalogo_al_reves(directorio: Path) -> None:
    """C001: el premium es el mas barato y el economico el mas caro; C002 tiene un Bluey suelto."""
    productos = [
        _producto("p1", "k1", "TK-C001-PRE", "premium", calidad="0.950"),
        _producto("p2", "k1", "TK-C001-ECO", "economico", calidad="0.400"),
        _producto("p3", "k1", "TK-C001-CON", "confiable", calidad="0.700"),
    ]
    _escribir(directorio, "productos_canonicos", productos)
    _escribir(
        directorio,
        "productos_procedencia",
        [
            {"producto_id": "p1", "sku_interno": "TK-C001-PRE", "fichero_fuente": "fuente-a.json"},
            {"producto_id": "p2", "sku_interno": "TK-C001-ECO", "fichero_fuente": "fuente-b.json"},
            {"producto_id": "p3", "sku_interno": "TK-C001-CON", "fichero_fuente": "fuente-c.json"},
        ],
    )
    _ofertas_y_precios(directorio, {"p1": 1200000, "p2": 3000000, "p3": 2000000})


def test_leer_devuelve_las_filas_como_texto_y_respeta_las_tildes(datos):
    """Los CSV se leen en UTF-8 y todo valor queda como texto (los numeros se convierten donde se usan)."""
    _escribir(datos, "tiendas", [{"id": "t1", "nombre": "Papeleria Lápiz Ñandú", "activa": "true"}])
    assert nivelar._leer("tiendas") == [{"id": "t1", "nombre": "Papeleria Lápiz Ñandú", "activa": "true"}]


def test_el_precio_minimo_es_el_mas_bajo_entre_ofertas_y_tramos(datos):
    """El papa compra en la tienda barata: gana el menor de todos los precios que se le vieron.

    `p1` tiene dos ofertas (la segunda con dos tramos); `p2` tiene una oferta sin
    ningun precio y `p3` no tiene oferta: ninguno de los dos entra al mapa.
    """
    _escribir(
        datos,
        "ofertas_tienda",
        [
            {"id": "o1", "producto_canonico_id": "p1"},
            {"id": "o2", "producto_canonico_id": "p1"},
            {"id": "o3", "producto_canonico_id": "p2"},
        ],
    )
    _escribir(
        datos,
        "precios_oferta",
        [
            {"id": "x1", "oferta_id": "o1", "valor_centavos": "900000"},
            {"id": "x2", "oferta_id": "o2", "valor_centavos": "1200000"},
            {"id": "x3", "oferta_id": "o2", "valor_centavos": "750000"},
        ],
    )
    assert nivelar.precio_minimo_por_producto() == {"p1": 750000}


def test_el_ensayo_imprime_el_diff_y_no_escribe_nada(datos, monkeypatch, capsys):
    """Sin `--escribir` se ve que cambiaria (SKU, nivel viejo y nuevo, precio) y los CSV quedan intactos."""
    _catalogo_al_reves(datos)
    antes = {n: (datos / f"{n}.csv").read_bytes() for n in ("productos_canonicos", "productos_procedencia")}

    codigo = _correr(monkeypatch)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "TK-C001-PRE" in salida
    assert "premium -> economico" in salida
    assert "economico -> premium" in salida
    assert "$  12,000" in salida  # 1.200.000 centavos
    assert "2 productos reetiquetados, 2 sku nuevos" in salida
    assert "Ensayo. Con --escribir se guarda." in salida
    assert "Escrito." not in salida
    despues = {n: (datos / f"{n}.csv").read_bytes() for n in antes}
    assert despues == antes


def test_escribir_reacuna_nivel_sku_y_calidad_y_la_procedencia_sigue_al_sku(datos, monkeypatch, capsys):
    """Con `--escribir` se intercambian las etiquetas que ya existian y todo lo derivado se mueve con ellas.

    El premium barato pasa a economico (SKU `...-ECO`, calidad 0,400) y el economico
    caro a premium (SKU `...-PRE`, calidad 0,950); el confiable no se toca. La
    procedencia repite el SKU y debe seguir el cambio, o apuntaria a un SKU
    que ya no existe. Las demas columnas quedan como estaban.
    """
    _catalogo_al_reves(datos)

    codigo = _correr(monkeypatch, "--escribir")

    assert codigo == 0
    assert "Escrito." in capsys.readouterr().out
    por_id = {p["id"]: p for p in _leer(datos, "productos_canonicos")}
    assert (por_id["p1"]["nivel"], por_id["p1"]["sku_interno"], por_id["p1"]["quality_score"]) == (
        "economico",
        "TK-C001-ECO",
        "0.400",
    )
    assert (por_id["p2"]["nivel"], por_id["p2"]["sku_interno"], por_id["p2"]["quality_score"]) == (
        "premium",
        "TK-C001-PRE",
        "0.950",
    )
    assert (por_id["p3"]["nivel"], por_id["p3"]["sku_interno"]) == ("confiable", "TK-C001-CON")
    assert por_id["p1"]["nombre"] == "Producto ficticio p1"
    assert por_id["p1"]["marca"] == "Marca Ficticia"
    procedencia = {r["producto_id"]: r for r in _leer(datos, "productos_procedencia")}
    assert {pid: r["sku_interno"] for pid, r in procedencia.items()} == {
        "p1": "TK-C001-ECO",
        "p2": "TK-C001-PRE",
        "p3": "TK-C001-CON",
    }
    assert procedencia["p1"]["fichero_fuente"] == "fuente-a.json"
    # Los SKU siguen siendo unicos: sin esto el cargador no podria upsertar por SKU.
    skus = [p["sku_interno"] for p in por_id.values()]
    assert len(set(skus)) == len(skus)


def test_el_sku_de_revision_conserva_su_nombre_y_su_calidad_fija(datos, monkeypatch, capsys):
    """Un `TK-REV-*` nombra la referencia de tienda, no `<concepto>-<nivel>`: solo cambia su nivel.

    Re-acunarlo partiria el SKU por `-` y daria `TK-REV-CON`, que chocaria; y su
    0,850 marca "lo miro una persona en la cola", no se deriva del nivel.
    """
    productos = [
        _producto("r1", "k4", "TK-C004-PRE", "premium", calidad="0.950"),
        _producto("r2", "k4", "TK-REV-ABC123", "economico", calidad="0.850"),
    ]
    _escribir(datos, "productos_canonicos", productos)
    _escribir(
        datos,
        "productos_procedencia",
        [{"producto_id": "r2", "sku_interno": "TK-REV-ABC123", "fichero_fuente": "cola.json"}],
    )
    _ofertas_y_precios(datos, {"r1": 500000, "r2": 900000})

    assert _correr(monkeypatch, "--escribir") == 0

    assert "2 productos reetiquetados, 1 sku nuevos" in capsys.readouterr().out
    por_id = {p["id"]: p for p in _leer(datos, "productos_canonicos")}
    assert (por_id["r2"]["nivel"], por_id["r2"]["sku_interno"], por_id["r2"]["quality_score"]) == (
        "premium",
        "TK-REV-ABC123",
        "0.850",
    )
    assert (por_id["r1"]["nivel"], por_id["r1"]["sku_interno"]) == ("economico", "TK-C004-ECO")
    assert _leer(datos, "productos_procedencia")[0]["sku_interno"] == "TK-REV-ABC123"


def test_el_producto_de_personaje_conserva_el_personaje_en_el_sku_nuevo(datos, monkeypatch):
    """Un Bluey solo en su escalera toma la banda de la marca y su SKU nuevo sigue llevando el personaje."""
    productos = [
        _producto("m1", "k5", "TK-C005-ECO", "economico", calidad="0.400"),
        _producto("m2", "k5", "TK-C005-PRE", "premium", calidad="0.950"),
        _producto("b1", "k5", "TK-C005-ECO-BLUEY", "economico", personaje="bluey", calidad="0.400"),
    ]
    _escribir(datos, "productos_canonicos", productos)
    _escribir(
        datos,
        "productos_procedencia",
        [{"producto_id": "b1", "sku_interno": "TK-C005-ECO-BLUEY", "fichero_fuente": "bluey.json"}],
    )
    _ofertas_y_precios(datos, {"m1": 1000000, "m2": 5000000, "b1": 6000000})

    assert _correr(monkeypatch, "--escribir") == 0

    por_id = {p["id"]: p for p in _leer(datos, "productos_canonicos")}
    assert (por_id["b1"]["nivel"], por_id["b1"]["sku_interno"], por_id["b1"]["quality_score"]) == (
        "premium",
        "TK-C005-PRE-BLUEY",
        "0.950",
    )
    assert _leer(datos, "productos_procedencia")[0]["sku_interno"] == "TK-C005-PRE-BLUEY"
    # Los dos de marca ya estaban ordenados y no se tocan.
    assert (por_id["m1"]["sku_interno"], por_id["m2"]["sku_interno"]) == ("TK-C005-ECO", "TK-C005-PRE")


def test_un_catalogo_ya_ordenado_no_cambia_nada(datos, monkeypatch, capsys):
    """Si el precio ya ordena los niveles, el script lo dice y no reescribe ni siquiera con `--escribir`."""
    productos = [
        _producto("a", "k6", "TK-C006-ECO", "economico", calidad="0.400"),
        _producto("b", "k6", "TK-C006-PRE", "premium", calidad="0.950"),
    ]
    _escribir(datos, "productos_canonicos", productos)
    _ofertas_y_precios(datos, {"a": 100000, "b": 900000})
    antes = (datos / "productos_canonicos.csv").read_bytes()

    assert _correr(monkeypatch, "--escribir") == 0

    assert "El precio ya ordena los niveles en todos los conceptos." in capsys.readouterr().out
    assert (datos / "productos_canonicos.csv").read_bytes() == antes
    assert not (datos / "productos_procedencia.csv").exists()


def test_una_permutacion_que_choca_un_sku_aborta_sin_escribir(datos, monkeypatch, capsys):
    """Si re-acunar un SKU lo dejaria igual a otro que ya existe, se aborta con codigo 1 y no se escribe.

    `r1` (premium, el mas barato) pasaria a `TK-C007-ECO`, que ya lleva `d1`, una
    alternativa de profundidad que `nivelar` no toca. Escribirlo dejaria dos
    productos con el mismo SKU y el cargador perderia uno.
    """
    productos = [
        _producto("r1", "k7", "TK-C007-PRE", "premium", calidad="0.950"),
        _producto("r2", "k7", "TK-C007-REF-9", "economico", calidad="0.400"),
        _producto("d1", "k7", "TK-C007-ECO", "confiable", representante="false"),
    ]
    _escribir(datos, "productos_canonicos", productos)
    _ofertas_y_precios(datos, {"r1": 100000, "r2": 900000, "d1": 500000})
    antes = (datos / "productos_canonicos.csv").read_bytes()

    codigo = _correr(monkeypatch, "--escribir")

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "ABORTADO: la permutacion choca el sku ['TK-C007-ECO']" in salida
    assert "Escrito." not in salida
    assert (datos / "productos_canonicos.csv").read_bytes() == antes


def test_guardar_conserva_el_orden_de_columnas_sin_lineas_en_blanco(datos):
    """El CSV reescrito mantiene el orden de las columnas, va en UTF-8 y no deja renglones vacios."""
    filas = [
        {"id": "1", "nombre": "Cuaderno Ñandú", "nivel": "economico"},
        {"id": "2", "nombre": "Colores, caja x12", "nivel": "premium"},
    ]

    nivelar._guardar("productos_canonicos", filas)

    texto = (datos / "productos_canonicos.csv").read_text(encoding="utf-8")
    assert texto.splitlines() == [
        "id,nombre,nivel",
        "1,Cuaderno Ñandú,economico",
        '2,"Colores, caja x12",premium',
    ]
    assert _leer(datos, "productos_canonicos") == filas
