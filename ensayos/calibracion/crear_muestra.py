"""Prepara la muestra ciega de anotacion (reproducible, semilla fija).
Uso: uv run python ensayos/calibracion/crear_muestra.py"""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import clasificacion as k  # noqa: E402
import particion as p  # noqa: E402

SEMILLA = 20261115
N = 240
MINIMO = 15
EXCEPCION = {"COLEGIO MADRE MATILDE": ["Sexto", "Tercero", "Once"]}
MUESTRA = k.MUESTRA_CIEGA
NINGUNO = "NINGUNO"


def cuotas(tam: dict[str, int], cap: dict[str, int], n: int, minimo: int) -> dict[str, int]:
    q = {c: min(minimo, cap[c]) for c in tam}
    for _ in range(20):
        libres = [
            c for c in tam if q[c] < cap[c] and q[c] > minimo - 1 and tam[c] * n / sum(tam.values()) > minimo
        ]
        resto = n - sum(q.values())
        if resto == 0 or not libres:
            break
        w = sum(tam[c] for c in libres)
        for c in libres:
            q[c] = min(cap[c], q[c] + int(resto * tam[c] / w))
        if n - sum(q.values()) == resto:
            c = max(libres, key=lambda c: cap[c] - q[c])
            q[c] += 1
    return q


def main() -> int:
    filas = []
    for x in csv.DictReader((k.DATOS / "renglones_etiquetados.csv").open(encoding="utf-8")):
        filas.append(x)
    clave = collections.Counter((x["colegio"], x["grado"], x["texto_original"]) for x in filas)
    listas = sorted({f"{x['colegio']}|{x['grado']}" for x in filas})
    prueba = [str(l) for l in p.partir(listas, p.SEMILLA_BASE)["prueba"]]
    for col, grados in EXCEPCION.items():
        prueba += [f"{col}|{g}" for g in grados]
    tam = collections.Counter(x["colegio"] for x in filas)
    elegibles = collections.defaultdict(list)
    for x in filas:
        if (
            f"{x['colegio']}|{x['grado']}" in prueba
            and clave[(x["colegio"], x["grado"], x["texto_original"])] == 1
        ):
            elegibles[x["colegio"]].append(x)
    cap = {c: len(elegibles[c]) for c in tam}
    q = cuotas(dict(tam), cap, N, MINIMO)
    rng = np.random.default_rng(SEMILLA)
    elegidas = []
    for c in sorted(tam):
        ix = rng.choice(len(elegibles[c]), q[c], replace=False)
        elegidas += [elegibles[c][i] for i in sorted(ix)]
    orden = rng.permutation(len(elegidas))
    elegidas = [elegidas[i] for i in orden]
    MUESTRA.mkdir(parents=True, exist_ok=True)
    ids = [f"M{i + 1:03d}" for i in range(len(elegidas))]
    with (MUESTRA / "muestra.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "colegio", "grado", "texto_original"])
        for i, x in zip(ids, elegidas, strict=True):
            w.writerow([i, x["colegio"], x["grado"], x["texto_original"]])
    for a in "AB":
        with (MUESTRA / f"anotador_{a}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "concepto_codigo", "comentario"])
            for i in ids:
                w.writerow([i, "", ""])
    cat = json.load((k.DATOS / "catalogo_conceptos.json").open(encoding="utf-8"))["conceptos"]
    with (MUESTRA / "conceptos.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["codigo", "nombre", "sinonimos_o_ejemplos"])
        for c in sorted(cat, key=lambda c: c["nombre"].lower()):
            ej = []
            for s in c["sinonimos"]:
                if s.strip().lower() != c["nombre"].strip().lower() and s not in ej:
                    ej.append(s)
            w.writerow([c["codigo"], c["nombre"], " | ".join(ej[:5])])
        w.writerow(
            [NINGUNO, "ninguno / no esta en el catalogo", "usar si ningun concepto describe el renglon"]
        )
    doc = {
        "semilla": SEMILLA,
        "total": len(elegidas),
        "particion_base": {"semilla": p.SEMILLA_BASE, "listas_prueba": sorted(prueba)},
        "excepcion": {
            "colegio": list(EXCEPCION)[0],
            "listas": EXCEPCION["COLEGIO MADRE MATILDE"],
            "motivo": "sin listas en la prueba de la semilla base; se usan las que mas veces fueron prueba en 20 semillas (4, 4 y 3 de 20); pudieron ser entrenamiento en otras",
        },
        "tamano_colegio": dict(tam),
        "elegibles_por_colegio": cap,
        "cuota_por_colegio": q,
        "excluidos_por_texto_repetido": int(sum(v for v in clave.values() if v > 1)),
        "limites": "n por colegio de 15 a unas 85; los IC por colegio son anchos. La muestra no cubre todos los grados.",
    }
    (k.SALIDA / "muestreo.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(q, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
