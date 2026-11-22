from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from .modelos.base import CALIDAD_POR_NIVEL, Nivel

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"

ORDEN = [Nivel.ECONOMICO.value, Nivel.CONFIABLE.value, Nivel.PREMIUM.value]


def _leer(nombre: str) -> list[dict[str, str]]:
    with (DATOS / f"{nombre}.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def precio_minimo_por_producto() -> dict[str, int]:
    de_oferta = defaultdict(list)
    for p in _leer("precios_oferta"):
        de_oferta[p["oferta_id"]].append(int(p["valor_centavos"]))
    minimo: dict[str, int] = {}
    for o in _leer("ofertas_tienda"):
        valores = de_oferta.get(o["id"])
        if not valores:
            continue
        actual = minimo.get(o["producto_canonico_id"])
        candidato = min(valores)
        if actual is None or candidato < actual:
            minimo[o["producto_canonico_id"]] = candidato
    return minimo


def sku(codigo: str, nivel: str, personaje: str) -> str:
    partes = ["TK", codigo, nivel[:3].upper()]
    if personaje:
        partes.append(personaje.upper())
    return "-".join(partes)


def reacomodar(productos: list[dict[str, str]], precios: dict[str, int]) -> dict[str, str]:
    por_escalera = defaultdict(list)
    for p in productos:
        vivo = p["activo"].lower() in {"true", "1", "t"}
        es_rep = p["es_representante_canonico"].lower() in {"true", "1", "t"}
        if vivo and es_rep and p["id"] in precios:
            por_escalera[p["concepto_id"], p["personaje"]].append(p)

    cambios: dict[str, str] = {}
    for (concepto, personaje), grupo in por_escalera.items():
        if personaje and len(grupo) == 1:
            banda = _banda_de_marca(grupo[0], por_escalera.get((concepto, ""), []), precios)
            if banda is not None and banda != grupo[0]["nivel"]:
                cambios[grupo[0]["id"]] = banda
            continue

        en_orden = sorted(grupo, key=lambda p: (precios[p["id"]], p["id"]))
        etiquetas = sorted((p["nivel"] for p in grupo), key=ORDEN.index)
        for p, etiqueta in zip(en_orden, etiquetas, strict=True):
            if p["nivel"] != etiqueta:
                cambios[p["id"]] = etiqueta
    return cambios


def _banda_de_marca(
    suelto: dict[str, str], marca: list[dict[str, str]], precios: dict[str, int]
) -> str | None:
    if not marca:
        return None
    escalones = sorted((precios[p["id"]], p["nivel"]) for p in marca)
    valor = precios[suelto["id"]]
    nivel = escalones[0][1]
    for precio, etiqueta in escalones:
        if precio <= valor:
            nivel = etiqueta
    return nivel


def _principal() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--escribir", action="store_true", help="guarda los CSV")
    args = ap.parse_args()

    productos = _leer("productos_canonicos")
    precios = precio_minimo_por_producto()
    cambios = reacomodar(productos, precios)

    if not cambios:
        print("El precio ya ordena los niveles en todos los conceptos.")
        return 0

    por_id = {p["id"]: p for p in productos}
    renombres: dict[str, str] = {}
    for pid, nivel in cambios.items():
        p = por_id[pid]
        viejo = p["sku_interno"]
        es_revision = viejo.startswith("TK-REV-")
        nuevo = viejo if es_revision else sku(viejo.split("-")[1], nivel, p["personaje"])
        print(f"  {viejo:24} {p['nivel']:>9} -> {nivel:<9} ${precios[pid] // 100:>8,}  {p['nombre'][:34]}")
        p["nivel"] = nivel
        if not es_revision:
            p["quality_score"] = f"{CALIDAD_POR_NIVEL[Nivel(nivel)]:.3f}"
        p["sku_interno"] = nuevo
        if viejo != nuevo:
            renombres[pid] = nuevo

    vivos = {p["sku_interno"] for p in productos if p["activo"].lower() in {"true", "1", "t"}}
    for p in productos:
        if p["activo"].lower() not in {"true", "1", "t"} and p["sku_interno"] in vivos:
            retirado = f"{p['sku_interno']}-RET"
            renombres[p["id"]] = retirado
            print(f"  {p['sku_interno']:24} inactivo -> {retirado}")
            p["sku_interno"] = retirado

    vistos = [p["sku_interno"] for p in productos]
    if len(set(vistos)) != len(vistos):
        repetidos = {s for s in vistos if vistos.count(s) > 1}
        print(f"\nABORTADO: la permutacion choca el sku {sorted(repetidos)}")
        return 1

    print(f"\n{len(cambios)} productos reetiquetados, {len(renombres)} sku nuevos")
    if not args.escribir:
        print("Ensayo. Con --escribir se guarda.")
        return 0

    _guardar("productos_canonicos", productos)
    procedencia = _leer("productos_procedencia")
    for fila in procedencia:
        fila["sku_interno"] = renombres.get(fila["producto_id"], fila["sku_interno"])
    _guardar("productos_procedencia", procedencia)
    print("Escrito.")
    return 0


def _guardar(nombre: str, filas: list[dict[str, str]]) -> None:
    ruta = DATOS / f"{nombre}.csv"
    with ruta.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


if __name__ == "__main__":
    raise SystemExit(_principal())
