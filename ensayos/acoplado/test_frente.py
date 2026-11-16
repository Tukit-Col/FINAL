"""La PD 4-D (estado: niveles, con precio, con personaje) == frente exacto por enumeracion en 3 instancias chicas."""

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench_laya"))
from comun import HIJO, cargar_json, decidibles, objetivos, personaje_de_lista, renglones_de  # noqa: E402
from frente import no_dominados, pd_frente_4d, vec  # noqa: E402
from tukit_inteligencia.optimizador import _admisibles  # noqa: E402


def _chicas(k=3, max_espacio=6000):
    import math

    salida = []
    for inst in cargar_json("instancias.json.gz")["instancias"]:
        dec = decidibles(renglones_de(inst))
        if 3 <= len(dec) <= 8 and 50 <= math.prod(len(_admisibles(r)) for r in dec) <= max_espacio:
            salida.append(dec)
        if len(salida) == k:
            break
    return salida


def test_pd_frente_igual_enumeracion():
    chicas = _chicas()
    assert len(chicas) == 3
    for dec in chicas:
        pers = personaje_de_lista(dec)
        prefs = {"personaje_por_hijo": {HIJO: [pers]}} if pers else {}
        todos = []
        for combo in itertools.product(*[_admisibles(r) for r in dec]):
            asig = {str(r.orden): c.sku for r, c in zip(dec, combo, strict=True)}
            todos.append(vec(objetivos(dec, asig, prefs)))
        exacto = no_dominados(todos)
        pd = no_dominados([vec(objetivos(dec, a, prefs)) for a in pd_frente_4d(dec, prefs)])
        assert pd == exacto
