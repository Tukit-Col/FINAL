"""Exporta de la base local (SOLO SELECT) los renglones de las versiones vigentes y revisadas.

Salidas en ensayos/calibracion/datos/:
  renglones_etiquetados.csv  colegio, grado, anio, orden, texto_original, concepto_codigo (etiqueta)
  catalogo_conceptos.json    conceptos activos con sinonimos (y cuales fueron aprendidos de una correccion)
  centroides.npz             centro normalizado de los embeddings de producto de cada concepto

No lleva datos de personas: son listas de utiles y el catalogo. Los nombres de colegio son
instituciones. Uso: uv run python ensayos/calibracion/exportar_etiquetas.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
from pathlib import Path

import numpy as np

DATOS = Path(__file__).resolve().parent / "datos"
ENTORNO = {**os.environ, "PGGSSENCMODE": "disable", "PGPASSWORD": "tukit"}


def consulta(base: str, sql: str) -> list[list[str]]:
    assert sql.lstrip().lower().startswith("select"), "solo lectura"
    r = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-U", "tukit", "-d", base, "-c", f"copy ({sql}) to stdout with csv"],
        capture_output=True, text=True, env=ENTORNO, timeout=120, check=True,
    )
    return list(csv.reader(io.StringIO(r.stdout)))


def main() -> int:
    DATOS.mkdir(exist_ok=True)
    colegios = {i: nombre for i, nombre in consulta("tukit_identidad", "select id, nombre from colegio")}
    filas = consulta(
        "tukit_catalogo",
        "select l.colegio_id, l.grado, l.anio_lectivo, i.orden, i.texto_original, c.codigo "
        "from item_lista_oficial i join version_lista_oficial v on v.id=i.version_id "
        "join lista_oficial l on l.id=v.lista_id left join concepto c on c.id=i.concepto_id "
        "where v.vigente and v.revisada_en is not null order by l.colegio_id, l.grado, i.orden",
    )
    with (DATOS / "renglones_etiquetados.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["colegio", "grado", "anio", "orden", "texto_original", "concepto_codigo"])
        for cid, grado, anio, orden, texto, codigo in filas:
            w.writerow([colegios.get(cid, cid), grado, anio, orden, texto, codigo])

    conceptos = consulta(
        "tukit_catalogo",
        "select id, codigo, nombre_canonico, array_to_json(sinonimos), tipo_item, "
        "array_to_json(atributos_discriminantes) from concepto where activo",
    )
    aprendidos = consulta(
        "tukit_catalogo", "select aprendido->>'concepto', aprendido->>'sinonimo' from correccion_lista where aprendido is not null"
    )
    json.dump(
        {
            "conceptos": [
                {"id": a, "codigo": b, "nombre": c, "sinonimos": json.loads(d), "tipo_item": e, "discriminantes": json.loads(g)}
                for a, b, c, d, e, g in conceptos
            ],
            "sinonimos_aprendidos": [{"concepto": a, "sinonimo": b} for a, b in aprendidos],
        },
        (DATOS / "catalogo_conceptos.json").open("w", encoding="utf-8"),
        ensure_ascii=False,
        indent=0,
    )
    prods = consulta(
        "tukit_catalogo",
        "select c.codigo, p.embedding::text from producto_canonico p join concepto c on c.id=p.concepto_id "
        "where p.activo and p.embedding is not null and c.activo",
    )
    por: dict[str, list[np.ndarray]] = {}
    for codigo, v in prods:
        por.setdefault(codigo, []).append(np.array(json.loads(v), dtype=np.float64))
    codigos = sorted(por)
    cent = []
    for c in codigos:
        s = np.sum(por[c], axis=0)
        cent.append(s / np.linalg.norm(s))
    np.savez_compressed(DATOS / "centroides.npz", codigos=np.array(codigos), centroides=np.array(cent, dtype=np.float32))
    print(len(filas), "renglones;", len(conceptos), "conceptos;", len(codigos), "con centroide;", len(aprendidos), "sinonimos aprendidos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
