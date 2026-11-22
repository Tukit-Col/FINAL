"""Piezas compartidas del benchmark Laya vs NSGA-II (lado del proyecto, con pymoo).

Todo lo que mide se apoya en las funciones del optimizador de produccion
(`_admisibles`, `_objetivos_de_asignacion`, `armar_kit`, `recomendar`), para que
"costo", "fidelidad" y "personaje" signifiquen aqui exactamente lo mismo que en
el pipeline. Una asignacion es `{orden (str): sku}` sobre las lineas decidibles
del unico hijo de la lista.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
# Los datos de entrada (instancias, escenarios, corridas) viven con el codigo;
# los resultados que el informe cita (metricas, tablas, figuras, tiempos) van a
# la documentacion, junto al informe que los lee.
CARPETA = Path(__file__).resolve().parent
SALIDA = RAIZ / "ensayos" / "bench_laya" / "salidas"
for sub in ("servicios/inteligencia", "libs/py/tukit_comun"):
    if str(RAIZ / sub) not in sys.path:
        sys.path.insert(0, str(RAIZ / sub))

from tukit_inteligencia.optimizador import (  # noqa: E402
    ORDEN_NIVEL,
    Candidato,
    Renglon,
    _admisibles,
    _objetivos_de_asignacion,
    unidades_a_comprar,
)

HIJO = "hijo-1"
TOPE_NIVEL = len(ORDEN_NIVEL) - 1


def cargar_json(nombre: str, carpeta: Path = CARPETA) -> Any:
    """Lee un JSON; si el nombre termina en `.gz`, comprimido."""
    ruta = carpeta / nombre
    if ruta.suffix == ".gz":
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_json(nombre: str, datos: Any, carpeta: Path = CARPETA) -> None:
    """Escribe un JSON; si el nombre termina en `.gz`, comprimido."""
    carpeta.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(datos, ensure_ascii=False, indent=1, default=str)
    ruta = carpeta / nombre
    if ruta.suffix == ".gz":
        # mtime=0: el mismo resultado da el mismo archivo, byte a byte.
        with gzip.GzipFile(ruta, "wb", mtime=0) as f:
            f.write(texto.encode("utf-8"))
    else:
        ruta.write_text(texto, encoding="utf-8")


def renglones_de(instancia: dict[str, Any]) -> list[Renglon]:
    salida = []
    for r in instancia["renglones"]:
        datos = dict(r)
        datos["candidatos"] = tuple(Candidato(**c) for c in r["candidatos"])
        salida.append(Renglon(**datos))
    return salida


def decidibles(renglones: list[Renglon]) -> list[Renglon]:
    """Las lineas donde hay que elegir producto: las mismas que `optimizar_frente`."""
    return [r for r in renglones if not r.informativa and _admisibles(r)]


def costo_linea(renglon: Renglon, c: Candidato) -> int:
    return (c.precio_cop or 0) * unidades_a_comprar(renglon.cantidad, c.unidades_por_empaque)


def tiene_personaje(c: Candidato, pedidos: set[str]) -> bool:
    return bool(c.personaje) and (not pedidos or c.personaje.lower() in pedidos)


def objetivos(
    dec: list[Renglon], asignacion: dict[str, str], preferencias: dict[str, Any]
) -> dict[str, float]:
    """Los cuatro ejes del frente para una asignacion, con la funcion de produccion."""
    elegidos = []
    for r in dec:
        sku = asignacion.get(str(r.orden))
        adm = _admisibles(r)
        elegido = next((c for c in r.candidatos if c.sku == sku), None) or adm[0]
        elegidos.append(elegido)
    costo, fid, disp, pers = _objetivos_de_asignacion(dec, elegidos, preferencias)
    return {"costo": costo, "fidelidad": fid, "disponibilidad": disp, "personaje": pers}


def domina(a: dict[str, float], b: dict[str, float]) -> bool:
    no_peor = (
        a["costo"] <= b["costo"]
        and a["fidelidad"] >= b["fidelidad"]
        and a["disponibilidad"] >= b["disponibilidad"]
        and a["personaje"] >= b["personaje"]
    )
    estricto = (
        a["costo"] < b["costo"]
        or a["fidelidad"] > b["fidelidad"]
        or a["disponibilidad"] > b["disponibilidad"]
        or a["personaje"] > b["personaje"]
    )
    return no_peor and estricto


# ------------------------------------------------------------ optimos exactos
#
# Los cuatro ejes son sumas/promedios por linea, asi que los extremos se
# resuelven linea por linea y el de presupuesto es una mochila de eleccion
# multiple, exacta por programacion dinamica sobre la suma de niveles (entera y
# chica: 0..2n). Los desempates replican `_proyectar`.


def optimo_ahorrador(dec: list[Renglon]) -> dict[str, str]:
    return {
        str(r.orden): min(_admisibles(r), key=lambda c: (costo_linea(r, c), -c.rango_nivel, c.sku)).sku
        for r in dec
    }


def optimo_premium(dec: list[Renglon]) -> dict[str, str]:
    return {
        str(r.orden): min(_admisibles(r), key=lambda c: (-c.rango_nivel, costo_linea(r, c), c.sku)).sku
        for r in dec
    }


def optimo_fan(dec: list[Renglon], pedidos: set[str]) -> dict[str, str]:
    return {
        str(r.orden): min(
            _admisibles(r),
            key=lambda c: (not tiene_personaje(c, pedidos), costo_linea(r, c), -c.rango_nivel, c.sku),
        ).sku
        for r in dec
    }


def optimo_presupuesto(dec: list[Renglon], presupuesto: int) -> dict[str, str] | None:
    """Maxima fidelidad con costo <= presupuesto; a igual fidelidad, menor costo."""
    # mejor[s] = (costo minimo para suma de niveles s, asignacion)
    mejor: dict[int, tuple[int, list[str]]] = {0: (0, [])}
    for r in dec:
        nuevo: dict[int, tuple[int, list[str]]] = {}
        for s, (costo, elec) in mejor.items():
            for c in _admisibles(r):
                s2 = s + min(c.rango_nivel, TOPE_NIVEL)
                c2 = costo + costo_linea(r, c)
                if s2 not in nuevo or c2 < nuevo[s2][0]:
                    nuevo[s2] = (c2, elec + [c.sku])
        mejor = nuevo
    factibles = [(s, c, e) for s, (c, e) in mejor.items() if c <= presupuesto]
    if not factibles:
        return None
    s, c, e = max(factibles, key=lambda t: (t[0], -t[1]))
    return {str(r.orden): sku for r, sku in zip(dec, e, strict=True)}


def personaje_de_lista(dec: list[Renglon]) -> str | None:
    """El personaje mas frecuente entre los candidatos de la lista (el que un papa podria pedir)."""
    cuenta: dict[str, int] = {}
    for r in dec:
        vistos = {c.personaje.lower() for c in _admisibles(r) if c.personaje}
        for p in vistos:
            cuenta[p] = cuenta.get(p, 0) + 1
    if not cuenta:
        return None
    return max(sorted(cuenta), key=lambda p: cuenta[p])
