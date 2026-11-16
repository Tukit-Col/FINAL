"""La curva riesgo-cobertura de la configuracion actual reproduce lo aceptado en tau = 0,75."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import punto_operacion as po  # noqa: E402


def test_curva_sintetica_con_empates() -> None:
    # 4 renglones aceptables: puntajes 0.9 (ok), 0.8 (mal), 0.8 (ok), 0.7 (ok)
    p = np.array([0, 1, 1, 2])
    y = np.array([0, 0, 1, 2])
    s = np.array([0.9, 0.8, 0.8, 0.7])
    g = po.Grupos(p, s, y, corte=0.5)
    wg, cg = g.sumas(np.ones(4))
    assert list(wg) == [1, 2, 1] and list(cg) == [1, 1, 1]
    pre = po.precision_en(wg, cg, 4.0, np.array([0.25, 0.75, 1.0]))
    assert np.allclose(pre, [1.0, 2 / 3, 0.75])
    # AURC exacta contra integracion numerica fina (riesgo medio en (0, 1])
    xs = (np.arange(200000) + 0.5) / 200000
    num = float(np.mean(1 - po.precision_en(wg, cg, 4.0, xs)))
    assert abs(po.aurc(wg, cg, 4.0, 0.0, 1.0) - num) < 1e-4


def test_actual_reproduce_aceptados_y_precision_en_tau_075() -> None:
    import barrido as b
    import clasificacion as k

    if not (k.DATOS / "renglones_etiquetados.csv").exists() or not (k.DATOS / "vectores_renglones.npz").exists():
        pytest.skip("faltan los datos exportados o los vectores en cache")
    cx = b.Contexto()
    p, s = cx.puntuar(k.ACTUAL)
    g = po.Grupos(p, s, cx.y, k.ACTUAL["corte"])
    wg, cg = g.sumas(np.ones(len(cx.y)))
    # aceptados con tau = 0,75: los bloques con puntaje >= 0,75
    sel = g.valores >= 0.75 - 1e-9
    aceptados, correctos = int(wg[sel].sum()), int(cg[sel].sum())
    assert aceptados == 2599 and correctos == 2526
    assert round(100 * correctos / aceptados, 1) == 97.2
    # la curva, leida en esa misma cobertura, da esa precision
    pre = po.precision_en(wg, cg, float(len(cx.y)), np.array([aceptados / len(cx.y)]))[0]
    assert abs(pre - correctos / aceptados) < 1e-9
    # y coincide con las metricas del barrido
    m = k.metricas(p, s, cx.y, k.ACTUAL["corte"], 0.75)
    assert abs(m["aceptada"] - aceptados / len(cx.y)) < 1e-12 and abs(m["precision_aceptada"] - correctos / aceptados) < 1e-12
