"""Decide, midiendo, cual atributo filtra y cual solo describe.

El catalogo declara por concepto que atributos importan. La pregunta que este
modulo responde es cual de ellos puede usarse como CONDICION para descartar un
producto, y la respuesta no se opina: se cuenta. Un atributo puede filtrar si
alguna lista de colegio lo pide; si en 4.719 renglones reales nadie lo
menciona, exigirlo solo descarta candidatos validos.

El caso que lo dejo claro es la bata de laboratorio. El catalogo exige `talla`,
y es un dato sensato de una bata, pero ninguna lista la pide porque la talla
depende del nino. Con `talla` como condicion, pedir `bata blanca de
laboratorio` no resuelve nada: ninguna bata del catalogo declara su talla, asi
que se descartan todas y el renglon se va a revision sin motivo. Al revés
tambien falla: `rayado` lo especifican 353 renglones y decide si un cuaderno
sirve, asi que tratarlo como decorativo hace que un cuaderno de cuadricula
pase por uno de doble linea.

La particion se deriva y no se escribe a mano, y eso es lo que la hace
defendible. Se puede volver a correr cuando entren colegios nuevos, y la
respuesta cambiara si cambia lo que los colegios piden, que es precisamente
como deberia comportarse.

    python -m tukit_catalogo.demanda_atributos            # informe, sin tocar nada
    python -m tukit_catalogo.demanda_atributos --escribir # reparte en el CSV
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path
from typing import Any

from .enriquecer import extraer_atributos

RAIZ = Path(__file__).resolve().parents[3]
CONCEPTOS = RAIZ / "datos" / "catalogo" / "conceptos.csv"
CORPUS = RAIZ.parent / "Arquitectura" / "Corpus_ItemLista_v2.csv"
INFORME = RAIZ / "datos" / "catalogo" / "demanda_atributos.json"

# Cuantos renglones tienen que pedir un atributo para que se le permita
# descartar productos. Uno basta: un atributo que una sola lista especifica
# sigue siendo un atributo que un colegio escribio, y el coste de tratarlo
# como condicion es bajo cuando el producto lo declara. Lo que se quiere
# separar es lo que NADIE pide, que es distinto de lo que se pide poco.
MINIMO = 1


def _lista(bruto: str | None) -> list[str]:
    return [p for p in (bruto or "").split("|") if p]


def _conceptos() -> list[dict[str, Any]]:
    with CONCEPTOS.open(encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def medir(conceptos: list[dict[str, Any]]) -> collections.Counter:
    """Cuantas veces cada concepto ve especificado cada uno de sus atributos.

    Se mide sobre el CSV y no sobre la base para que el resultado dependa
    solo de archivos versionados: el corpus, el catalogo y este codigo. Una
    medicion que dependa del estado de una base no se puede repetir.
    """
    from .descubrir import clasificar

    para_clasificar = [
        {
            "id": c["codigo"],
            "nombre": c["nombre_canonico"],
            "sinonimos": _lista(c.get("sinonimos")),
        }
        for c in conceptos
    ]
    requeridos = {c["codigo"]: tuple(_lista(c.get("atributos_requeridos"))) for c in conceptos}

    pide: collections.Counter = collections.Counter()
    with CORPUS.open(encoding="utf-8") as archivo:
        for renglon in csv.DictReader(archivo):
            texto = renglon["texto_original"]
            codigo, _nombre, parecido = clasificar(texto, para_clasificar)
            if parecido < 0.5 or codigo is None:
                continue
            for atributo in extraer_atributos(texto, requeridos[codigo]):
                pide[(codigo, atributo)] += 1
    return pide


def repartir(
    conceptos: list[dict[str, Any]], pide: collections.Counter
) -> tuple[list[dict[str, Any]], int, int]:
    discriminan = describen = 0
    for concepto in conceptos:
        codigo = concepto["codigo"]
        atributos = _lista(concepto.get("atributos_requeridos"))
        duros = [a for a in atributos if pide[(codigo, a)] >= MINIMO]
        blandos = [a for a in atributos if a not in duros]
        concepto["atributos_discriminantes"] = "|".join(duros)
        concepto["atributos_descriptivos"] = "|".join(blandos)
        concepto.pop("atributos_requeridos", None)
        discriminan += len(duros)
        describen += len(blandos)
    return conceptos, discriminan, describen


def _escribir(conceptos: list[dict[str, Any]], pide: collections.Counter) -> None:
    columnas = [
        "id",
        "codigo",
        "nombre_canonico",
        "sinonimos",
        "categoria",
        "tipo_item",
        "atributos_discriminantes",
        "atributos_descriptivos",
        "admite_personaje",
        "frecuencia_demanda",
        "activo",
    ]
    with CONCEPTOS.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows({c: concepto.get(c, "") for c in columnas} for concepto in conceptos)

    # El conteo se guarda al lado del reparto. Sin el, la particion es una
    # lista de atributos que alguien decidio y no se puede discutir; con el,
    # cada atributo trae el numero de renglones que lo pidieron.
    INFORME.write_text(
        json.dumps(
            {
                "minimo_para_discriminar": MINIMO,
                "corpus": CORPUS.name,
                "demanda": {f"{cod}.{attr}": n for (cod, attr), n in sorted(pide.items())},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--escribir", action="store_true", help="reparte en conceptos.csv")
    args = analizador.parse_args()

    conceptos = _conceptos()
    if "atributos_requeridos" not in (conceptos[0] if conceptos else {}):
        print("conceptos.csv ya esta repartido en discriminantes y descriptivos.")
        return 0

    pide = medir(conceptos)
    _repartidos, duros, blandos = repartir(conceptos, pide)

    print(f"Medido contra {CORPUS.name}\n")
    print(f"  atributos que alguna lista pide (discriminan)  {duros}")
    print(f"  atributos que nadie pide (solo describen)      {blandos}")
    print("\nlos mas pedidos:")
    for (codigo, atributo), veces in pide.most_common(12):
        print(f"  {codigo} {atributo:16} {veces:>4} renglones")

    if not args.escribir:
        print("\nNada escrito. Repite con --escribir para repartirlo en el CSV.")
        return 0

    _escribir(_repartidos, pide)
    print(f"\nEscrito {CONCEPTOS.name} y {INFORME.name}")
    print("Ahora:  make bd-cargar  para llevarlo a la base")
    return 0


if __name__ == "__main__":
    sys.exit(main())
