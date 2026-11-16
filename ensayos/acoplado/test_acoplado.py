"""PD con costo fijo por tienda == enumeracion exacta en 3 instancias chicas."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acoplado import enumeracion, pd_exacta  # noqa: E402
from comun import cargar_json, decidibles, renglones_de  # noqa: E402


def _chicas(k=3, max_lineas=7, max_espacio=20000):
    import math

    from tukit_inteligencia.optimizador import _admisibles

    salida = []
    for inst in cargar_json("instancias.json.gz")["instancias"]:
        dec = decidibles(renglones_de(inst))
        if 3 <= len(dec) <= max_lineas and math.prod(len(_admisibles(r)) for r in dec) <= max_espacio:
            salida.append((inst["id"], dec[:max_lineas]))
        if len(salida) == k:
            break
    return salida


@pytest.mark.parametrize("T", [1, 3, 8])
def test_pd_igual_enumeracion(T):
    chicas = _chicas()
    assert len(chicas) == 3
    from comun import costo_linea
    from tukit_inteligencia.optimizador import _admisibles

    for _id, dec in chicas:
        base = sum(min(costo_linea(r, c) for c in _admisibles(r)) for r in dec)
        for presupuesto in (base + 12_000, int(base * 1.4) + 20_000, 10**9):
            exacto = enumeracion(dec, presupuesto, T)
            pd, _ = pd_exacta(dec, presupuesto, T)
            if exacto is None:
                assert pd is None
            else:
                assert pd is not None and (pd[0], pd[1]) == exacto
