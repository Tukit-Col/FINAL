"""Corre el benchmark de embeddings y guarda resultados en resultados/."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.data import generar_catalogo, generar_consultas
from benchmarks.embeddings import (
    MODELOS,
    evaluar_baseline_ngram,
    evaluar_modelo_fastembed,
    _normalizar,
)

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
RESULTADOS.mkdir(exist_ok=True)


def main():
    productos = generar_catalogo(semilla=7)
    consultas = generar_consultas(productos, semilla=7)
    nombres = [p["nombre"] for p in productos]
    ids = [p["id"] for p in productos]
    relevantes = [c["id_producto"] for c in consultas]
    textos = [c["consulta"] for c in consultas]
    print(f"catálogo: {len(productos)} productos, {len(consultas)} consultas")

    filas = []
    for m in MODELOS:
        try:
            r = evaluar_modelo_fastembed(m["id"], nombres, textos, ids, relevantes)
            r.update({"modelo": m["nombre"], "tipo": m["tipo"]})
            filas.append(r)
            print("ok:", m["nombre"], r)
        except Exception as exc:  # noqa: BLE001
            print("ERROR", m["nombre"], exc)

    r = evaluar_baseline_ngram(nombres, textos, ids, relevantes)
    r.update({"modelo": "ngram-3-5 (pg_trgm approx)", "tipo": "léxico"})
    filas.append(r)
    print("ok: ngram baseline", r)

    with open(RESULTADOS / "embeddings.json", "w", encoding="utf-8") as fh:
        json.dump(filas, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
