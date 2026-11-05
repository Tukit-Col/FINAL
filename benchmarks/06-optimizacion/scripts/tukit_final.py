"""Acceso de solo lectura al optimizador de produccion de Tukit (repo FINAL).

El benchmark no copia el optimizador: lo importa tal cual desde un clon de
`Tukit-Col/FINAL`, para que "costo", "fidelidad", "disponibilidad" y "personaje"
signifiquen aqui exactamente lo mismo que en el sistema. La ruta del clon se
toma de la variable `TUKIT_FINAL` (por omision, el clon local del autor).

Importante: no se escribe nada en el clon. `PYTHONDONTWRITEBYTECODE` evita los
`__pycache__` que Python dejaria al importar.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

FINAL = Path(os.environ.get("TUKIT_FINAL", "/Users/jrozo/Downloads/tukit-vf/FINAL")).resolve()
CARPETA = Path(__file__).resolve().parents[1]
DATOS = CARPETA / "datos"
RESULTADOS = CARPETA / "resultados"
FIGURAS = CARPETA / "figuras"

for sub in ("servicios/inteligencia", "libs/py/tukit_comun"):
    ruta = str(FINAL / sub)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from tukit_inteligencia import optimizador as opt  # noqa: E402
from tukit_inteligencia.optimizador import Candidato, Renglon  # noqa: E402


def cargar_json(ruta: Path) -> Any:
    if ruta.suffix == ".gz":
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(datos, ensure_ascii=False, indent=1, default=str)
    if ruta.suffix == ".gz":
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
    """Las mismas lineas que `optimizar_frente`: no informativas y con admisibles."""
    return [r for r in renglones if not r.informativa and opt._admisibles(r)]


def instancias() -> list[dict[str, Any]]:
    return cargar_json(DATOS / "instancias.json.gz")["instancias"]


def escenarios() -> list[dict[str, Any]]:
    return cargar_json(DATOS / "escenarios.json.gz")["escenarios"]


def commit_final() -> str:
    cabeza = FINAL / ".git" / "HEAD"
    try:
        ref = cabeza.read_text().strip()
        if ref.startswith("ref: "):
            return (FINAL / ".git" / ref[5:]).read_text().strip()
        return ref
    except OSError:
        return "desconocido"
