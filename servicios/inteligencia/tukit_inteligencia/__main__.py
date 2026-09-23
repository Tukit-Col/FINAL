"""Herramientas de linea de comandos del servicio de Inteligencia.

    python -m tukit_inteligencia parsear "Diccionario: el disponible en casa"
    python -m tukit_inteligencia percibir lista.pdf
    python -m tukit_inteligencia esquema

El emparejamiento contra la base curada no vive aqui. Catalogo es otro
servicio y este no lo importa: el ensayo que los junta esta en
`ensayos/fase1.py`, y en produccion va por HTTP (ver `remoto.py`).

`esquema` es un subcomando y no el `python -m tukit_<servicio>` pelado que
usan Identidad y Catalogo, porque este modulo ya tenia una interfaz de
comandos antes de que el servicio tuviera tablas. Romperla para ganar
uniformidad habria costado mas que la uniformidad; el ejecutor de tareas lo
invoca con el subcomando y la diferencia queda en una linea del Makefile.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .parseo import parsear_renglon
from .percepcion import percibir


def _demanda(texto: str, cantidad: int | None) -> dict:
    demanda = parsear_renglon(texto, cantidad=cantidad)
    datos = asdict(demanda)
    datos["busca_en_catalogo"] = demanda.busca_en_catalogo
    return datos


def _comando_parsear(argumentos: argparse.Namespace) -> int:
    print(json.dumps(_demanda(argumentos.texto, argumentos.cantidad), ensure_ascii=False, indent=2))
    return 0


def _comando_percibir(argumentos: argparse.Namespace) -> int:
    from .gemini import pedir_pagina
    from .paginas import renderizar

    contenido = Path(argumentos.archivo).read_bytes()
    resultado = percibir(contenido, renderizar=renderizar, leer=pedir_pagina)
    cuerpo = {
        "aceptada": resultado.aceptada,
        "error": resultado.error,
        "mensaje": resultado.mensaje,
        "grados": list(resultado.grados),
        "paginas": resultado.paginas,
        "degradaciones": list(resultado.degradaciones),
        "items": [
            _demanda(item.descripcion, item.cantidad) | {"confianza": item.confianza}
            for item in resultado.items
        ],
    }
    print(json.dumps(cuerpo, ensure_ascii=False, indent=2))
    return 0 if resultado.aceptada else 2


def _comando_esquema(_argumentos: argparse.Namespace) -> int:
    from tukit_comun.esquema import materializar

    from .modelos import Base

    materializar("inteligencia", Base)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fase 1: leer una lista y parsearla a demanda.")
    sub = parser.add_subparsers(dest="comando", required=True)

    parsear = sub.add_parser("parsear", help="Parsea un renglon, sin modelo y sin base.")
    parsear.add_argument("texto")
    parsear.add_argument("--cantidad", type=int, default=None)
    parsear.set_defaults(funcion=_comando_parsear)

    percibir = sub.add_parser("percibir", help="Lee un PDF o una imagen con Gemini y parsea cada renglon.")
    percibir.add_argument("archivo")
    percibir.set_defaults(funcion=_comando_percibir)

    esquema = sub.add_parser("esquema", help="Materializa las 9 tablas del servicio en su base.")
    esquema.set_defaults(funcion=_comando_esquema)

    argumentos = parser.parse_args(argv)
    return argumentos.funcion(argumentos)


if __name__ == "__main__":
    sys.exit(main())
