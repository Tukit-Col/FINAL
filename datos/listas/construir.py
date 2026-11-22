"""Arma los CSV de listas oficiales que los cargadores siembran.

Decisiones:
- El corpus original (`Arquitectura/Corpus_ItemLista_v2.csv`, los renglones transcritos de los PDF
  de 17 colegios) vive fuera del monorepo; los CSV que genera si entran, porque el monorepo no
  depende de ninguna ruta fuera de el: un cargador que leyera esa ruta correria en una sola maquina
  y fallaria en silencio (sembraria cero filas) en integracion continua y en un clon nuevo.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CORPUS_POR_OMISION = AQUI.parents[2] / "Arquitectura" / "Corpus_ItemLista_v2.csv"

NOMBRES_POR_CODIGO: dict[str, str] = {
    "2.1": "Colegio Matilde",
    "2.3": "Colegio San Jose de Fontibon",
    "2.4": "Colegio San Pedro",
    "2.9": "Colegio Modelia",
    "2.10": "Jardin Osito de Miel",
    "2.11": "Colegio Bahia Solano",
    "2.12": "Colegio Alamei",
    "2.13": "Colegio CACS",
}

SEDE_UNICA = "Sede unica"

MODOS_SURTIBLES = frozenset({"mercado_abierto", "libro_libre"})

MODO_CUANDO_EL_PDF_NO_LO_DICE = "mercado_abierto"

INSTRUCCION_POR_MODO: dict[str, str] = {
    "plataforma": (
        "El colegio indica que se adquiere por plataforma externa. "
        "Sigue el enlace o las instrucciones que el colegio publico en su lista."
    ),
    "venta_directa_editorial": (
        "El colegio indica que la editorial lo vende directamente a las familias, "
        "por lo general en una jornada de venta en el plantel."
    ),
    "edicion_exclusiva": (
        "El colegio indica que es una edicion exclusiva para la institucion: "
        "solo se consigue por el canal que el colegio senale."
    ),
    "diferido": (
        "El colegio indica que se pide mas adelante en el ano lectivo. Todavia no hay que comprarlo."
    ),
}

ENLACE = re.compile(r"https?://[^\s,;)\]}'\"]+")


def nombre_presentable(codigo: str) -> str:
    return NOMBRES_POR_CODIGO.get(codigo, f"Colegio {codigo}")


def normalizar_modo(crudo: str) -> str:
    limpio = (crudo or "").strip()
    if not limpio or limpio == "desconocido":
        return MODO_CUANDO_EL_PDF_NO_LO_DICE
    return limpio


def corregir_modo(tipo: str, modo: str) -> str:
    if tipo == "util" and modo == "plataforma":
        return MODO_CUANDO_EL_PDF_NO_LO_DICE
    return modo


def instruccion(modo: str) -> str:
    if modo in MODOS_SURTIBLES:
        return ""
    return INSTRUCCION_POR_MODO.get(
        modo, "El colegio indica que este renglon no se compra en el mercado abierto."
    )


def url_externa(texto: str) -> str:
    encontrado = ENLACE.search(texto or "")
    if not encontrado:
        return ""
    return encontrado.group(0).rstrip(".")


def cantidad_valida(crudo: str) -> int:
    try:
        cantidad = int(float((crudo or "").strip()))
    except ValueError:
        return 1
    return cantidad if cantidad > 0 else 1


def leer_corpus(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def armar_colegios(filas: list[dict[str, str]]) -> list[dict[str, str]]:
    codigos: list[str] = []
    vistos: set[str] = set()
    for fila in filas:
        codigo = fila["colegio_id"].strip()
        if codigo and codigo not in vistos:
            vistos.add(codigo)
            codigos.append(codigo)
    return [
        {"codigo": c, "nombre": nombre_presentable(c), "sede_nombre": SEDE_UNICA}
        for c in sorted(codigos, key=_orden_codigo)
    ]


def _orden_codigo(codigo: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in codigo.split("."))
    except ValueError:
        return (999,)


def armar_items(filas: list[dict[str, str]]) -> list[dict[str, str]]:
    contador: dict[tuple[str, str], int] = defaultdict(int)
    items: list[dict[str, str]] = []
    for fila in filas:
        colegio = fila["colegio_id"].strip()
        grado = fila["grado"].strip()
        texto = fila["texto_original"].strip()
        if not colegio or not grado or not texto:
            continue
        contador[(colegio, grado)] += 1
        tipo = (fila.get("tipo_item") or "").strip()
        modo = corregir_modo(tipo, normalizar_modo(fila.get("modo_adquisicion", "")))
        items.append(
            {
                "colegio_codigo": colegio,
                "grado": grado,
                "orden": str(contador[(colegio, grado)]),
                "texto_original": texto,
                "cantidad": str(cantidad_valida(fila.get("cantidad", ""))),
                "tipo_item": tipo,
                "modo_adquisicion": modo,
                "categoria": (fila.get("categoria") or "").strip(),
                "instruccion_colegio": instruccion(modo),
                "url_externa": url_externa(texto),
            }
        )
    return items


def escribir(ruta: Path, columnas: list[str], filas: list[dict[str, str]]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--corpus", type=Path, default=CORPUS_POR_OMISION)
    analizador.add_argument("--salida", type=Path, default=AQUI)
    args = analizador.parse_args()

    if not args.corpus.exists():
        print(f"No encuentro el corpus en {args.corpus}")
        print("Es material de la tesis y vive fuera del monorepo: pasalo con --corpus.")
        return 2

    filas = leer_corpus(args.corpus)
    colegios = armar_colegios(filas)
    items = armar_items(filas)

    args.salida.mkdir(parents=True, exist_ok=True)
    escribir(args.salida / "colegios.csv", ["codigo", "nombre", "sede_nombre"], colegios)
    escribir(
        args.salida / "items_lista.csv",
        [
            "colegio_codigo",
            "grado",
            "orden",
            "texto_original",
            "cantidad",
            "tipo_item",
            "modo_adquisicion",
            "categoria",
            "instruccion_colegio",
            "url_externa",
        ],
        items,
    )

    listas = {(i["colegio_codigo"], i["grado"]) for i in items}
    no_surtibles = [i for i in items if i["modo_adquisicion"] not in MODOS_SURTIBLES]
    sin_nombre = [c for c in colegios if c["codigo"] not in NOMBRES_POR_CODIGO]

    print(f"corpus                        {len(filas):5} filas  ({args.corpus})")
    print(f"colegios.csv                  {len(colegios):5}")
    print(f"items_lista.csv               {len(items):5}")
    print(f"listas (colegio x grado)      {len(listas):5}")
    print(f"renglones que Tukit no surte  {len(no_surtibles):5}  todos con instruccion")
    print(f"colegios sin nombre curado    {len(sin_nombre):5}  {[c['codigo'] for c in sin_nombre]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
