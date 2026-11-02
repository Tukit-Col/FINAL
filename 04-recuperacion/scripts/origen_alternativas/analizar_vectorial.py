"""Analiza resultados/vectorial_*.json y resume los modos de fallo del
enfoque solo-vectorial vs el enfoque actual (reglas), a nivel de ítem.

Uso: py -3.12 scripts/analizar_vectorial.py [vectorial_umbral_0_3.json]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.data import generar_catalogo
from benchmarks.nl2c_data import generar_casos

RAIZ = Path(__file__).resolve().parents[1]
RUTA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "resultados" / "vectorial_umbral_0_3.json"

CASOS_GT = {i: c for i, c in enumerate(generar_casos(generar_catalogo(semilla=7), semilla=11), 1)}


def _resumir(items_gt, items_pred):
    """Fallos a nivel de ítem, idéntico a analizar_agentes._resumir:
    faltantes (gt no recuperado), extra (recupera ítem que no es gt),
    cantidad_mal (mismo id pero cantidad distinta), sin_match (id None)."""
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

    for metodo in ("actual", "vectorial_e5"):
        print(f"\n========== {metodo.upper()} ==========")
        conteos = {"faltantes": [], "extra": [], "cantidad_mal": [], "sin_match": []}
        gt_nombre = {p["id"]: p["nombre"] for p in _catalogo_nombres()}
        for f in filas:
            d = f[metodo]
            gt = CASOS_GT[f["n"]]
            fallos = _resumir(gt["items"], d["items_pred"])
            # Los descartes por score<umbral quedan en `detalle` con id None y
            # NO en items_pred; se cuentan como sin_match aparte.
            for det in d["detalle"]:
                if det["id"] is None:
                    fallos["sin_match"].append((f["n"], det["descripcion"], round(det["score"], 3)))
            for k in ("faltantes", "extra", "cantidad_mal", "sin_match"):
                conteos[k].extend(fallos[k])

        faltantes = conteos["faltantes"]
        print(f"Faltantes (gt no recuperado): {len(faltantes)}")
        for n in faltantes[:15]:
            print(f"  caso {n:>2}: {gt_nombre.get(n, n)}")
        sin_match = conteos["sin_match"]
        print(f"Sin match (score<umbral): {len(sin_match)}")
        for x in sin_match[:15]:
            print(f"  caso {x[0]:>2}: '{x[1]}' score={x[2]}")
        extra = conteos["extra"]
        print(f"Extra (recupera ítem que no es gt): {len(extra)}")
        for n in extra[:15]:
            print(f"  caso {n:>2}: {gt_nombre.get(n, n)}")
        cantidad_mal = conteos["cantidad_mal"]
        print(f"Cantidad mal: {len(cantidad_mal)}")
        for n in cantidad_mal[:10]:
            print(f"  caso {n:>2}: {gt_nombre.get(n, n)}")

    print("\nDetalle de los peores casos (prosa) donde vectorial_e5 difiere:")
    for f in filas:
        if f["tipo"] != "prosa":
            continue
        a, v = f["actual"]["f1"], f["vectorial_e5"]["f1"]
        if v < a:
            print(f"\n  caso {f['n']}: actual={a} vectorial={v}")
            print(f"  texto: {f['texto']}")
            gt = CASOS_GT[f["n"]]
            nombre_por_id = {p["id"]: p["nombre"] for p in _catalogo_nombres()}
            for det in f["vectorial_e5"]["detalle"]:
                print(f"    chunk '{det['descripcion']}' -> {det['nombre']} (score {det['score']})")


def _catalogo_nombres():
    return generar_catalogo(semilla=7)


if __name__ == "__main__":
    main()
