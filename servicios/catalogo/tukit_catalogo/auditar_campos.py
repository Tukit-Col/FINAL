"""Audita los campos del catalogo que el NSGA y la ficha necesitan completos.

Un producto con campo vacio no falla en ningun lado: el optimizador lo trata
como un dato mas y la ficha muestra un hueco. Este auditor lo vuelve visible.
Lee los CSV (la fuente que el cargador usa) y no escribe en ellos.

`personaje` no se audita: los productos neutros no lo llevan.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DATOS = Path(__file__).resolve().parents[3] / "datos" / "catalogo"
INFORME = Path(__file__).resolve().parents[3] / "docs" / "informes" / "auditoria-campos-catalogo.md"

CAMPOS_OBLIGATORIOS: tuple[str, ...] = (
    "nombre",
    "marca",
    "nivel",
    "imagen_url",
    "unidad_base",
    "unidades_por_empaque",
    "concepto_id",
)
# Los consume la ficha o la busqueda semantica, no el `Candidato` del NSGA:
# un hueco aqui es una advertencia, no un fallo de --estricto.
CAMPOS_RECOMENDADOS: tuple[str, ...] = ("descripcion", "texto_embedding", "embedding_model")


@dataclass(frozen=True)
class Hallazgo:
    producto_id: str
    campo: str
    motivo: str


def _vacio(valor: str | None) -> bool:
    return (valor or "").strip().lower() in ("", "nan")


def _activo(fila: dict[str, str]) -> bool:
    return (fila.get("activo") or "").strip().lower() not in ("false", "0")


def auditar(
    productos: list[dict[str, str]],
    precios_por_producto: set[str],
    activos_solo: bool = True,
) -> list[Hallazgo]:
    """Un hallazgo por campo vacio, mas `precio` si no hay oferta con precio."""
    salida: list[Hallazgo] = []
    for p in productos:
        if activos_solo and not _activo(p):
            continue
        pid = p.get("id", "")
        for campo in (*CAMPOS_OBLIGATORIOS, *CAMPOS_RECOMENDADOS):
            if _vacio(p.get(campo)):
                salida.append(Hallazgo(pid, campo, "vacio"))
        if pid not in precios_por_producto:
            salida.append(Hallazgo(pid, "precio", "sin_oferta"))
    return salida


def resumir(hallazgos: list[Hallazgo]) -> dict[str, int]:
    return dict(Counter(h.campo for h in hallazgos))


def _leer(datos: Path, nombre: str) -> list[dict[str, str]]:
    with (datos / f"{nombre}.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def productos_con_precio(datos: Path) -> set[str]:
    """Ids de producto con al menos una oferta con precio > 0."""
    oferta_a_producto = {o["id"]: o["producto_canonico_id"] for o in _leer(datos, "ofertas_tienda")}
    con_precio: set[str] = set()
    for pr in _leer(datos, "precios_oferta"):
        try:
            valor = int(float(pr.get("valor_centavos") or 0))
        except ValueError:
            continue
        if valor > 0 and pr["oferta_id"] in oferta_a_producto:
            con_precio.add(oferta_a_producto[pr["oferta_id"]])
    return con_precio


def _informe(resumen: dict[str, int], hallazgos: list[Hallazgo], total: int) -> str:
    afectados = len({h.producto_id for h in hallazgos})
    lineas = [
        "# Auditoria de campos del catalogo",
        "",
        f"Productos auditados (activos): {total}. Con algun hallazgo: {afectados}.",
        "",
        "| Campo | Productos con hueco |",
        "|---|---|",
    ]
    for campo in (*CAMPOS_OBLIGATORIOS, "precio", *CAMPOS_RECOMENDADOS):
        lineas.append(f"| {campo} | {resumen.get(campo, 0)} |")
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datos", type=Path, default=DATOS, help="directorio con los CSV")
    ap.add_argument("--informe", type=Path, default=INFORME)
    ap.add_argument("--estricto", action="store_true", help="devuelve 1 si falta un campo obligatorio o el precio")
    args = ap.parse_args(argv)

    productos = _leer(args.datos, "productos_canonicos")
    hallazgos = auditar(productos, productos_con_precio(args.datos))
    resumen = resumir(hallazgos)
    total = sum(1 for p in productos if _activo(p))

    for campo, n in sorted(resumen.items()):
        print(f"{campo}: {n}")
    if not resumen:
        print("Sin hallazgos.")
    args.informe.parent.mkdir(parents=True, exist_ok=True)
    args.informe.write_text(_informe(resumen, hallazgos, total), encoding="utf-8")
    recomendados = set(CAMPOS_RECOMENDADOS)
    graves = [h for h in hallazgos if h.campo not in recomendados]
    for campo in sorted(set(resumen) & recomendados):
        print(f"ADVERTENCIA: {resumen[campo]} productos sin {campo} (recomendado)")
    return 1 if (args.estricto and graves) else 0


if __name__ == "__main__":
    raise SystemExit(main())
