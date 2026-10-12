"""Acomoda las etiquetas de nivel para que el precio las ordene.

El nivel no es decorativo: el comentario de `Nivel` dice que un kit economico
se compone de productos ECONOMICO. Si dentro de un concepto el producto
etiquetado premium resulta mas barato que el economico, el papa que elige
"economico" paga mas que el que elige "premium". La promesa de los tres kits
queda al reves y nada en el sistema lo nota, porque hasta ahora ningun test
comparaba precio contra nivel.

La reparacion es deliberadamente minima: se PERMUTAN las etiquetas que el
concepto ya tiene, en orden de precio. No se inventan niveles ni se reparten
por terciles, asi que cuantos economicos/confiables/premium hay por concepto
no cambia; solo cambia cual producto lleva cual etiqueta. Cualquier cosa mas
ambiciosa reescribiria decisiones de curaduria que no tomo este script.

Corre sobre los CSV y no sobre la base, porque el cargador trata los CSV como
la fuente: un arreglo hecho solo en Postgres se perderia en la siguiente carga.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from .modelos.base import CALIDAD_POR_NIVEL, Nivel

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"

# De mas barato a mas caro. Es el orden que el precio tiene que reproducir.
ORDEN = [Nivel.ECONOMICO.value, Nivel.CONFIABLE.value, Nivel.PREMIUM.value]


def _leer(nombre: str) -> list[dict[str, str]]:
    with (DATOS / f"{nombre}.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def precio_minimo_por_producto() -> dict[str, int]:
    """El precio con que se compara un producto es el mas bajo que se le vio.

    Se toma el minimo y no el promedio porque es el que el papa pagaria: si la
    misma referencia esta en dos tiendas, compramos en la barata.
    """
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
    """`TK-<concepto>-<NIV>[-<PERSONAJE>]`, igual que lo armo el curador."""
    partes = ["TK", codigo, nivel[:3].upper()]
    if personaje:
        partes.append(personaje.upper())
    return "-".join(partes)


def reacomodar(productos: list[dict[str, str]], precios: dict[str, int]) -> dict[str, str]:
    """Devuelve producto_id -> nivel nuevo, solo para los que hay que mover.

    Un concepto solo se toca si su orden actual esta roto. Asi el diff dice
    exactamente donde estaba el defecto y no se mezcla con ruido.
    """
    # Se agrupa por concepto Y personaje, no solo por concepto. Los productos
    # con personaje son una escalera paralela: el cuaderno de Bluey economico y
    # el de Bluey premium compiten entre si, no contra el cuaderno sin
    # personaje. Mezclarlos ademas choca el sku, porque `TK-<concepto>-<NIV>`
    # solo puede repetirse si el personaje lo distingue.
    #
    # Solo entran los REPRESENTANTES. Desde que la cola de revision aprueba
    # varias referencias por celda, una escalera tiene un representante por nivel
    # (lo que el kit muestra) mas profundidad de compra detras. Esa profundidad
    # entro con `nivel_sugerido=None` -su etiqueta es un 'confiable' por defecto,
    # no una promesa-, asi que permutar etiquetas contra ella mezclaria un relleno
    # con la escalera curada y podria arrancarle el nivel al representante para
    # darselo a una alternativa que el kit ni siquiera propone. El nivel ordena lo
    # que el papa recibe, y eso es el representante.
    por_escalera = defaultdict(list)
    for p in productos:
        vivo = p["activo"].lower() in {"true", "1", "t"}
        es_rep = p["es_representante_canonico"].lower() in {"true", "1", "t"}
        if vivo and es_rep and p["id"] in precios:
            por_escalera[p["concepto_id"], p["personaje"]].append(p)

    cambios: dict[str, str] = {}
    for (concepto, personaje), grupo in por_escalera.items():
        # Un producto SOLO en su escalera de personaje no tiene con quien
        # compararse, asi que conserva la etiqueta con que nacio y esa etiqueta
        # no significa nada. Ahi estaba el ultimo caso torcido: el planeador de
        # Stitch a $34.900 marcado economico cuando la agenda de marca premium
        # valia $26.600. Para que la etiqueta no mienta, se lee de la banda de
        # precio de los productos de marca del mismo concepto.
        if personaje and len(grupo) == 1:
            banda = _banda_de_marca(grupo[0], por_escalera.get((concepto, ""), []), precios)
            if banda is not None and banda != grupo[0]["nivel"]:
                cambios[grupo[0]["id"]] = banda
            continue

        # El desempate por id mantiene la salida estable entre corridas.
        en_orden = sorted(grupo, key=lambda p: (precios[p["id"]], p["id"]))
        etiquetas = sorted((p["nivel"] for p in grupo), key=ORDEN.index)
        for p, etiqueta in zip(en_orden, etiquetas, strict=True):
            if p["nivel"] != etiqueta:
                cambios[p["id"]] = etiqueta
    return cambios


def _banda_de_marca(
    suelto: dict[str, str], marca: list[dict[str, str]], precios: dict[str, int]
) -> str | None:
    """En que nivel cae este precio segun la escalera de los productos de marca.

    Devuelve None si el concepto no tiene productos de marca con precio: sin
    referencia no hay banda, y poner una etiqueta al azar es justo el problema
    que esta funcion vino a resolver.
    """
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
    # Por id de producto, no por sku: el sku viejo de un inactivo que cede el
    # suyo es justo el que toma otro, y por sku seria ambiguo.
    renombres: dict[str, str] = {}
    for pid, nivel in cambios.items():
        p = por_id[pid]
        viejo = p["sku_interno"]
        # El tier aprobado en revision (`TK-REV-<referencia>`) es otra cosa: su
        # SKU nombra la referencia de tienda, no `<concepto>-<nivel>`, asi que no
        # se re-acuna al mover el nivel -partirlo por '-' daria `TK-REV-CON` y
        # chocaria-. Y su `quality_score` es el 0,85 fijo que marca 'lo miro una
        # persona en la cola', que tampoco se deriva del nivel. Solo se corrige
        # la etiqueta de nivel, que es lo que este modulo vino a ordenar.
        es_revision = viejo.startswith("TK-REV-")
        nuevo = viejo if es_revision else sku(viejo.split("-")[1], nivel, p["personaje"])
        print(f"  {viejo:24} {p['nivel']:>9} -> {nivel:<9} ${precios[pid] // 100:>8,}  {p['nombre'][:34]}")
        p["nivel"] = nivel
        if not es_revision:
            p["quality_score"] = f"{CALIDAD_POR_NIVEL[Nivel(nivel)]:.3f}"
        p["sku_interno"] = nuevo
        if viejo != nuevo:
            renombres[pid] = nuevo

    # Un producto desactivado conserva su sku semilla y puede chocar con el que
    # la permutacion le asigna a uno vivo (el galon de vinilo desactivado tenia
    # `TK-C020-PRE` y el tarro de un kilo paso a premium). El vivo gana: el
    # inactivo pasa a `<sku>-RET`, que dice que salio del surtido.
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
    # La procedencia repite el sku para que una fila se pueda rastrear sin
    # join. Si no se actualiza aqui, queda apuntando a un sku que ya no existe.
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
