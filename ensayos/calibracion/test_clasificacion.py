"""`clasificacion` puntua igual que `descubrir.clasificar`: con las constantes actuales, en 20 renglones."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import clasificacion as k  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (k.DATOS / "renglones_etiquetados.csv").exists() or not (k.DATOS / "vectores_renglones.npz").exists(),
    reason="faltan los datos exportados (exportar_etiquetas.py) o los vectores en cache",
)


def test_puntuar_reproduce_descubrir_clasificar_en_20_renglones() -> None:
    d = k.cargar()
    r = k.construir_rasgos(d)
    idx, s = k.puntuar(r, k.ACTUAL)
    concs = []
    for i, c in enumerate(d.conceptos):
        e = dict(c)
        e["embedding"] = d.cent[i].tolist() if d.tiene_cent[i] else None
        concs.append(e)
    pos = {c["id"]: i for i, c in enumerate(concs)}
    for f in np.random.default_rng(7).choice(len(d.filas), 20, replace=False):
        u = d.filas[f]["u"]
        cid, _, puntaje = k.D.clasificar(d.corr[u], concs, embedding_renglon=d.vectores[u].tolist())
        assert (pos[cid] if cid is not None else -1) == int(idx[u]), d.textos[u]
        assert abs(puntaje - float(s[u])) < 1e-6
