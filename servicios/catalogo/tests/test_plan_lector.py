from __future__ import annotations

import csv
import json
from pathlib import Path

DATOS = Path(__file__).resolve().parents[3] / "datos"


def _leer(ruta: str) -> list[dict[str, str]]:
    with (DATOS / ruta).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _isbn13_valido(isbn: str) -> bool:
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    suma = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(isbn[:12]))
    return (10 - suma % 10) % 10 == int(isbn[12])


def test_c134_se_busca_en_el_catalogo_y_filtra_por_isbn():
    c134 = next(c for c in _leer("catalogo/conceptos.csv") if c["codigo"] == "C134")
    assert c134["tipo_item"] == "libro_libre"
    assert "isbn13" in c134["atributos_discriminantes"]


def test_cada_linea_con_isbn_tiene_su_edicion_en_el_catalogo():
    productos = {
        json.loads(p["atributos"] or "{}").get("isbn13") or p["ean"]
        for p in _leer("catalogo/productos_canonicos.csv")
    }
    productos |= {libro["isbn13"] for libro in _leer("catalogo/libros_firecrawl.csv")}
    pedidos = []
    for linea in _leer("curaduria/listas_revisadas.csv"):
        if linea["concepto"] != "C134" or not linea["atributos"]:
            continue
        isbn = json.loads(linea["atributos"]).get("isbn13")
        if isbn:
            pedidos.append(isbn)
    assert pedidos, "ninguna linea del plan lector lleva ISBN"
    for isbn in pedidos:
        assert _isbn13_valido(isbn), f"{isbn} no es un ISBN-13 valido"
        assert isbn in productos, f"la lista pide {isbn} y el catalogo no tiene esa edicion"


def test_lo_que_no_tiene_edicion_dice_que_se_compra_en_libreria():
    sin_edicion = [
        fila
        for fila in _leer("curaduria/listas_revisadas.csv")
        if fila["concepto"] == "C134" and not fila["atributos"]
    ]
    assert sin_edicion
    for linea in sin_edicion:
        assert linea["tipo_item"] == "otro", linea["texto_original"][:50]
        assert "librería" in linea["instruccion_colegio"], linea["texto_original"][:50]


def test_cada_edicion_cargada_tiene_url_precio_e_imagen():
    for libro in _leer("catalogo/libros_firecrawl.csv"):
        if libro["tienda_slug"] != "buscalibre" or libro["concepto_codigo"] != "C134":
            continue
        assert _isbn13_valido(libro["isbn13"]), libro["titulo"]
        assert libro["url_origen"].startswith("https://www.buscalibre.com.co/"), libro["titulo"]
        assert int(libro["precio_cop"]) > 0, libro["titulo"]
        assert libro["imagen_url"].startswith("https://"), libro["titulo"]
        assert libro["observado_en"] == "2026-11-01", libro["titulo"]


def test_un_libro_ya_cubierto_por_otra_linea_del_grado_no_se_ofrece_como_pendiente_de_libreria():
    por_grado: dict[str, list[dict[str, str]]] = {}
    for linea in _leer("curaduria/listas_revisadas.csv"):
        if linea["concepto"] == "C134" and "gateway" in linea["texto_original"].lower():
            por_grado.setdefault(linea["grado"], []).append(linea)
    revisados = 0
    for grado, lineas in por_grado.items():
        if not any(linea["tipo_item"] == "libro_libre" and linea["atributos"] for linea in lineas):
            continue
        for linea in lineas:
            revisados += 1
            assert linea["tipo_item"] != "otro", f"{grado} #{linea['orden']} repite una edicion ya resuelta"
    assert revisados >= 3
