"""Extrae los ordenamientos de la pregunta P21 de la encuesta a acudientes.

Entrada: el Excel exportado de la encuesta (columna "Ordena de mayor a menor
importancia..."). Salida: `datos/p21_rankings.csv`, una fila por respuesta con
los cuatro criterios de mayor a menor importancia. No guarda estrato, correo ni
ninguna otra columna: solo el orden de los criterios.

Uso: python extraer_p21.py RUTA_AL_XLSX   (requiere openpyxl)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import openpyxl

PREFIJOS = {
    "Que tenga las marcas exactas": "marca_exigida",
    "Calidad y durabilidad": "calidad",
    "Precio total": "precio",
    "Que tenga las marcas/personajes": "personaje",
}
COLUMNA_P21 = 21
SALIDA = Path(__file__).resolve().parent / "datos" / "p21_rankings.csv"


def criterio(texto: str) -> str:
    for prefijo, nombre in PREFIJOS.items():
        if texto.startswith(prefijo):
            return nombre
    raise ValueError(texto)


def main(ruta: str) -> int:
    filas = list(openpyxl.load_workbook(ruta).active.iter_rows(values_only=True))[1:]
    ordenes = []
    for fila in filas:
        valor = fila[COLUMNA_P21]
        if not valor:
            continue
        orden = [criterio(x.strip()) for x in valor.split(";") if x.strip()]
        if len(orden) == 4 and len(set(orden)) == 4:
            ordenes.append(orden)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pos1", "pos2", "pos3", "pos4"])
        w.writerows(ordenes)
    print(f"{len(filas)} filas, {len(ordenes)} ordenamientos completos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
