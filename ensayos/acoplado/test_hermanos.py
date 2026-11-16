"""PD con consolidacion == enumeracion en 3 hogares chicos; costo == armar_kit del sistema."""

import collections
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hermanos import Hogar, armar_hogar, enumeracion_hogar, pd_hogar  # noqa: E402
from comun import cargar_json  # noqa: E402
from tukit_inteligencia.optimizador import _admisibles  # noqa: E402

CASOS = [((40, 41), 4), ((10, 11, 12), 3), ((100, 101), 4)]


def _hogar(pares, por_hijo):
    ins = cargar_json("instancias.json.gz")["instancias"]
    rs = armar_hogar([ins[i] for i in pares])
    dec = [r for r in rs if not r.informativa and len(_admisibles(r)) >= 2]
    por = collections.defaultdict(set)
    for r in dec:
        por[r.concepto_codigo].add(r.hijo)
    cuenta, sel = collections.Counter(), []
    for r in dec:
        if len(por[r.concepto_codigo]) >= 2 and not r.no_consolidable and cuenta[r.hijo] < por_hijo:
            sel.append(r)
            cuenta[r.hijo] += 1
    return Hogar(sel)


@pytest.mark.parametrize("pares,por_hijo", CASOS)
def test_pd_igual_enumeracion(pares, por_hijo):
    h = _hogar(pares, por_hijo)
    assert h.K > 0
    base = sum(min(c[6] for c in f) for f in h.cand)
    for tope in (int(base * 1.2), int(base * 1.8), 10**9):
        e = enumeracion_hogar(h, "presupuesto", tope)
        p, _ = pd_hogar(h, "presupuesto", tope, reconstruir=True)
        assert (e is None) == (p is None)
        if e:
            assert (p[0], p[1]) == e
            assert h.costo(p[2]) == p[1] and h.nivel(p[2]) == p[0]
    e = enumeracion_hogar(h, "costo", 10**9)
    p, _ = pd_hogar(h, "costo", 10**9, reconstruir=True)
    assert p[1] == e[1] == h.costo(p[2])


def test_consolidacion_ahorra_y_coincide_con_el_sistema():
    h = _hogar(*CASOS[1])
    rng = random.Random(1)
    ahorro = 0
    for _ in range(60):
        idx = [rng.randrange(len(f)) for f in h.cand]
        ahorro += h.costo_sin_consolidar(idx) - h.costo(idx)
        assert h.costo(idx) == h.total_armar_kit(idx)
    assert ahorro > 0
