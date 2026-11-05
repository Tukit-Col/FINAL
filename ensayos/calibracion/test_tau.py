"""La matriz de confusion y la curva ROC del umbral tau cuadran con un caso hecho a mano."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import tau  # noqa: E402


def test_matriz_y_f1_en_un_caso_conocido() -> None:
    parecido = np.array([0.9, 0.8, 0.8, 0.6, 0.5, 0.4])
    y = np.array([True, True, False, True, False, False])
    m = tau.matriz_confusion(parecido, y, 0.75)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 2)
    assert m["precision"] == 2 / 3 and m["recall"] == 2 / 3
    assert abs(m["f1"] - 2 / 3) < 1e-12


def test_roc_va_de_cero_a_uno_y_su_area_es_el_auc() -> None:
    parecido = np.array([0.9, 0.8, 0.8, 0.6, 0.5, 0.4])
    y = np.array([True, True, False, True, False, False])
    puntos = tau.curva_roc(parecido, y)
    assert (puntos[0]["fpr"], puntos[0]["tpr"]) == (0.0, 0.0)
    assert (puntos[-1]["fpr"], puntos[-1]["tpr"]) == (1.0, 1.0)
    fpr = np.array([p["fpr"] for p in puntos])
    tpr = np.array([p["tpr"] for p in puntos])
    area = float(np.sum((fpr[1:] - fpr[:-1]) * (tpr[1:] + tpr[:-1]) / 2))
    assert abs(area - tau.auc(parecido, y)) < 1e-12
