"""Analiza resultados/agentes.json y resume los modos de fallo de cada
enfoque (ítems faltantes, ítems extra, cantidad mal, id sin match, y
aciertos por restricción). Alimenta la sección "agentes" del reporte."""
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.data import generar_catalogo
from benchmarks.nl2c_data import generar_casos

RAIZ = Path(__file__).resolve().parents[1]
RUTA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "resultados" / "agentes_lexico.json"


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _resumir(items_gt, items_pred):
    gt_set = {it["id"] for it in items_gt}
    pred_set = {it["id"] for it in items_pred}
    gt_q = {it["id"]: it["cantidad"] for it in items_gt}
    pred_q = {it["id"]: it["cantidad"] for it in items_pred}
    return {
        "faltantes": sorted(gt_set - pred_set),
        "extra": sorted(pred_set - gt_set),
        "cantidad_mal": sorted(
            pid for pid in gt_set & pred_set if gt_q[pid] != pred_q.get(pid)
        ),
        "sin_match": sorted(
            it["id"] for it in items_pred if it.get("id") is None
        ),
    }


def main():
    with open(RUTA, encoding="utf-8") as fh:
        datos = json.load(fh)
    filas = datos["filas"]
    # Ground truth regenerado (determinista: semilla 7/11), unido por n.
    casos_gt = {i: c for i, c in enumerate(generar_casos(generar_catalogo(semilla=7), semilla=11), 1)}
    for metodo in ("actual", "agente"):
        if not any(metodo in f for f in filas):
            continue
        conteos = {"faltantes": [], "extra": [], "cantidad_mal": [], "sin_match": []}
        rest_ok = {"exclusion_marcas": 0, "precio_max": 0, "categoria": 0}
        rest_total = {"exclusion_marcas": 0, "precio_max": 0, "categoria": 0}
        casos_con_error = []
        for f in filas:
            if metodo not in f:
                continue
            d = f[metodo]
            gt = casos_gt[f["n"]]
            fallos = _resumir(gt["items"], d["items_pred"])
            for k in ("faltantes", "extra", "cantidad_mal", "sin_match"):
                conteos[k].extend(fallos[k])
            for k in rest_total:
                if k in gt["restricciones"]:
                    rest_total[k] += 1
                    vp = d["restricciones"].get(k)
                    if k == "exclusion_marcas":
                        ok = vp is not None and set(_norm(v) for v in vp) & set(_norm(v) for v in gt["restricciones"][k])
                    elif k == "categoria":
                        ok = vp is not None and _norm(vp) == _norm(gt["restricciones"][k])
                    else:
                        ok = vp == gt["restricciones"][k]
                    if ok:
                        rest_ok[k] += 1
            if any(fallos.values()):
                casos_con_error.append(f["n"])
        print(f"\n=== {metodo.upper()} ({len([f for f in filas if metodo in f])} casos) ===")
        for k, v in conteos.items():
            print(f"  {k}: {len(v)}")
        print("  restricciones aciertos:", {k: f"{rest_ok[k]}/{rest_total[k]}" for k in rest_total})
        print("  casos con >=1 fallo:", casos_con_error)


if __name__ == "__main__":
    main()
