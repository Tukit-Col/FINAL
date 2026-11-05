"""Une las respuestas del formulario de cierre con la hoja de tareas de la ronda.

Uso: python docs/validacion/oe5/oe5_cierre/unir_cierre.py respuestas.csv
Salida: docs/validacion/oe5/oe5_cierre/datos_oe5.csv, lista para analisis_oe5.py.
Lee las columnas por posición, en el orden del formulario: marca de tiempo, código,
autorización, SUS 1-10, RTLX habitual 1-6, RTLX con TUKIT 1-6, NPS, por qué.
"""

import csv
import sys
from pathlib import Path

AQUI = Path(__file__).parent
TAREAS = AQUI.parent / "oe5_ronda2" / "datos_ronda2.csv"
NOMBRES = (
    [f"sus{i}" for i in range(1, 11)]
    + [f"tlx_trad_{i}" for i in range(1, 7)]
    + [f"tlx_tukit_{i}" for i in range(1, 7)]
    + ["nps"]
)


def main(ruta: str) -> int:
    with open(ruta, encoding="utf-8-sig") as a:
        filas = list(csv.reader(a))[1:]
    form = {}
    for f in filas:
        codigo = f[1].strip().upper()
        form[codigo] = dict(zip(NOMBRES, (v.strip() for v in f[3 : 3 + len(NOMBRES)])))  # la última respuesta gana
    with open(TAREAS, encoding="utf-8") as a:
        tareas = list(csv.DictReader(a))
    columnas = list(tareas[0]) + NOMBRES
    salida = AQUI / "datos_oe5.csv"
    with open(salida, "w", newline="", encoding="utf-8") as a:
        w = csv.DictWriter(a, fieldnames=columnas)
        w.writeheader()
        for t in tareas:
            w.writerow({**t, **form.get(t["codigo"], {})})
    faltan = [t["codigo"] for t in tareas if t["codigo"] not in form]
    print(f"{salida}: {len(tareas)} filas, formulario de {len(form)}; sin formulario: {faltan or 'ninguno'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
