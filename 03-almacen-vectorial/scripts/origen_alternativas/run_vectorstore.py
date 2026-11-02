"""Corre el benchmark de vector store y guarda resultados en resultados/."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.vectorstore import ejecutar

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
RESULTADOS.mkdir(exist_ok=True)


def main():
    res = ejecutar(n=10_000, d=1024, n_queries=100, k=10)
    with open(RESULTADOS / "vectorstore.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
