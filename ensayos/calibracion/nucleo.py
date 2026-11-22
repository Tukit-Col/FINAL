"""Piezas compartidas de los ensayos de calibracion del optimizador."""

from __future__ import annotations

import json
import math
import platform
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = Path(__file__).resolve().parent
SALIDA = RAIZ / "ensayos" / "calibracion" / "salidas"
BENCH = RAIZ / "ensayos" / "bench_laya"
for ruta in (str(RAIZ / "servicios" / "inteligencia"), str(RAIZ / "libs" / "py" / "tukit_comun"), str(BENCH)):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from comun import cargar_json, decidibles  # noqa: E402  (bench_laya)
from tukit_inteligencia.optimizador import (  # noqa: E402
    Renglon,
    SolucionFrente,
    _admisibles,
    _no_dominadas,
    _objetivos_de_asignacion,
    _solucion,
)

SEMILLA_BASE = 20261101


def instancias() -> list[dict[str, Any]]:
    return cargar_json("instancias.json.gz")["instancias"]


def guardar(nombre: str, datos: Any) -> Path:
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return ruta


def hardware() -> dict[str, str]:
    def sysctl(clave: str) -> str:
        try:
            return subprocess.run(
                ["sysctl", "-n", clave], capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            return "?"

    import pymoo

    return {
        "cpu": sysctl("machdep.cpu.brand_string"),
        "nucleos": sysctl("hw.ncpu"),
        "memoria_bytes": sysctl("hw.memsize"),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pymoo": pymoo.__version__,
        "so": platform.platform(),
    }


def opciones_de(dec: list[Renglon]) -> list[list]:
    return [_admisibles(r) for r in dec]


def espacio_de(opciones: list[list]) -> int:
    return math.prod(len(o) for o in opciones)


def subproblema(
    renglones: list[Renglon], bits: int, rng: random.Random
) -> tuple[list[Renglon], list[list]] | None:
    dec = decidibles(renglones)
    dec = [r for r in dec if len(_admisibles(r)) > 1]
    rng.shuffle(dec)
    elegidas: list[Renglon] = []
    espacio = 1
    for r in dec:
        k = len(_admisibles(r))
        if espacio * k >= 2 ** (bits + 1):
            continue
        elegidas.append(r)
        espacio *= k
        if espacio >= 2**bits:
            break
    if espacio < 2**bits:
        return None
    elegidas.sort(key=lambda r: r.orden)
    return elegidas, opciones_de(elegidas)


def frente_exacto_por_podas(
    dec: list[Renglon], opciones: list[list], preferencias: dict[str, Any]
) -> list[SolucionFrente]:
    from tukit_inteligencia.optimizador import (  # noqa: F401
        ORDEN_NIVEL,
        Candidato,
        _personajes_de,
        unidades_a_comprar,
    )

    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    parciales: list[tuple[int, float, int, int, tuple[int, ...]]] = [(0, 0.0, 0, 0, ())]
    for r, ops in zip(dec, opciones, strict=True):
        pedidos = {p.lower() for p in _personajes_de(preferencias, r.hijo)}
        nuevos = []
        for costo, fid, disp, pers, idx in parciales:
            for j, c in enumerate(ops):
                u = unidades_a_comprar(r.cantidad, c.unidades_por_empaque)
                nuevos.append(
                    (
                        costo + (c.precio_cop * u if c.precio_cop is not None else 0),
                        fid + c.rango_nivel / tope_nivel,
                        disp + (1 if c.precio_cop is not None else 0),
                        pers + (1 if c.personaje and (not pedidos or c.personaje.lower() in pedidos) else 0),
                        idx + (j,),
                    )
                )
        parciales = _podar(nuevos)
    soluciones = [
        _solucion(dec, [ops[j] for ops, j in zip(opciones, idx, strict=True)], preferencias)
        for *_, idx in parciales
    ]
    return _no_dominadas(soluciones)


def _podar(
    puntos: list[tuple[int, float, int, int, tuple[int, ...]]],
) -> list[tuple[int, float, int, int, tuple[int, ...]]]:
    unicos: dict[tuple[int, float, int, int], tuple[int, ...]] = {}
    for costo, fid, disp, pers, idx in puntos:
        unicos.setdefault((costo, round(fid, 9), disp, pers), idx)
    claves = sorted(unicos, key=lambda k: (k[0], -k[1], -k[2], -k[3]))
    matriz = np.array([[k[0], -k[1], -k[2], -k[3]] for k in claves], dtype=float)
    vivos = np.ones(len(claves), dtype=bool)
    for i in range(len(claves)):
        if not vivos[i]:
            continue
        dom = np.all(matriz[:i] <= matriz[i], axis=1) & np.any(matriz[:i] < matriz[i], axis=1) & vivos[:i]
        if dom.any():
            vivos[i] = False
            continue
        posteriores = matriz[i + 1 :]
        domina = np.all(matriz[i] <= posteriores, axis=1) & np.any(matriz[i] < posteriores, axis=1)
        vivos[i + 1 :] &= ~domina
    return [(k[0], k[1], k[2], k[3], unicos[k]) for k, v in zip(claves, vivos, strict=True) if v]


def limites_costo(dec: list[Renglon], opciones: list[list]) -> tuple[int, int]:
    from tukit_inteligencia.optimizador import unidades_a_comprar

    def c(r: Renglon, cand) -> int:
        return (cand.precio_cop or 0) * unidades_a_comprar(r.cantidad, cand.unidades_por_empaque)

    lo = sum(min(c(r, x) for x in ops) for r, ops in zip(dec, opciones, strict=True))
    hi = sum(max(c(r, x) for x in ops) for r, ops in zip(dec, opciones, strict=True))
    return lo, hi


REFERENCIA = 1.1


def hipervolumen(frente: list[SolucionFrente], lo: int, hi: int) -> float:
    from pymoo.indicators.hv import HV

    if not frente:
        return 0.0
    ancho = max(1, hi - lo)
    puntos = np.array(
        [[(s.costo - lo) / ancho, 1 - s.fidelidad, 1 - s.disponibilidad, 1 - s.personaje] for s in frente]
    )
    return float(HV(ref_point=np.full(4, REFERENCIA))(puntos))


def objetivos_de(dec: list[Renglon], opciones: list[list], idx: tuple[int, ...], prefs: dict[str, Any]):
    elegidos = [ops[j] for ops, j in zip(opciones, idx, strict=True)]
    return _objetivos_de_asignacion(dec, elegidos, prefs)
