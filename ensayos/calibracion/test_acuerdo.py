"""acuerdo.py con anotadores sinteticos (etiqueta del sistema + 8 % de ruido) en una carpeta temporal."""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import acuerdo as ac  # noqa: E402
import clasificacion as k  # noqa: E402


def test_kappa_a_mano() -> None:
    a = ["x", "x", "y", "y"]
    b = ["x", "y", "y", "y"]
    # po = .75, pe = .5*.25 + .5*.75 = .5 -> kappa = .5
    assert abs(ac.kappa(a, b) - 0.5) < 1e-12


def test_flujo_con_anotadores_sinteticos(tmp_path: Path) -> None:
    shutil.copy(ac.MUESTRA / "muestra.csv", tmp_path / "muestra.csv")
    filas = list(csv.DictReader((tmp_path / "muestra.csv").open(encoding="utf-8")))
    assert list(filas[0]) == ["id", "colegio", "grado", "texto_original"]
    sis = ac.salida_sistema(filas)
    codigos = sorted({v["circular"] for v in sis.values()} | {"C016", "C009", "NINGUNO"})
    for nombre, sem in (("A", 1), ("B", 2)):
        rng = np.random.default_rng(sem)
        with (tmp_path / f"anotador_{nombre}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "concepto_codigo", "comentario"])
            for f in filas:
                c = sis[f["id"]]["circular"]
                if rng.random() < 0.08:
                    c = str(rng.choice([x for x in codigos if x != c]))
                w.writerow([f["id"], "" if c == "NINGUNO" else c, ""])
    salida = tmp_path / "acuerdo.json"
    r1 = ac.correr(tmp_path, salida)
    assert (tmp_path / "adjudicacion.csv").exists()  # pide adjudicar los desacuerdos
    assert r1["oro"]["sin_oro_pendientes"] == r1["acuerdo_A_B"]["desacuerdos"] > 0
    # tercera persona sintetica: adjudica con la etiqueta circular
    filas_adj = list(csv.DictReader((tmp_path / "adjudicacion.csv").open(encoding="utf-8")))
    with (tmp_path / "adjudicacion.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "texto_original", "concepto_A", "concepto_B", "adjudicado"])
        for x in filas_adj:
            w.writerow([x["id"], x["texto_original"], x["concepto_A"], x["concepto_B"], sis[x["id"]]["circular"]])
    r = ac.correr(tmp_path, salida)
    assert r["oro"]["sin_oro_pendientes"] == 0 and r["oro"]["con_oro"] == len(filas)
    assert 0.8 < r["acuerdo_A_B"]["porcentaje"] < 0.97
    lo, hi = r["acuerdo_A_B"]["kappa_ic95"]
    assert lo <= r["acuerdo_A_B"]["kappa_cohen"] <= hi and r["acuerdo_A_B"]["kappa_cohen"] > 0.8
    # el oro sintetico es casi la etiqueta circular: las dos medidas del sistema deben quedar cerca
    s = r["sistema"]
    assert s["inflacion_por_circularidad"]["exactitud"]["circular_menos_oro"] < 0.05
    assert abs(s["contra_oro_independiente"]["exactitud"]["valor"] - s["contra_etiquetas_del_sistema_circulares"]["exactitud"]["valor"]) < 0.05
    assert json.loads(salida.read_text(encoding="utf-8"))["n"] == len(filas)
    # nada de pruebas dentro de muestra_ciega/
    assert not (k.MUESTRA_CIEGA / "adjudicacion.csv").exists()
