"""Recalcula la tabla de percepcion (5 enfoques x 10 documentos del CGS-10).

Lee las predicciones guardadas (`datos/resultados_benchmark_10.json.gz`, el
`corpus/resultados_benchmark_10.json` de Tukit-Poc-Tesis) y las puntua con la
misma funcion `calcular_prf1` de `06_comparar_enfoques.py` (emparejamiento
exacto normalizado y, si no, difuso con SequenceMatcher >= 0,75).

Diferencia con el script original: la latencia "p50" se reporta como mediana
estadistica (promedio de los dos centrales con 10 documentos). El original
tomaba `sorted(x)[len(x)//2]`, el sexto de diez, que no es la mediana.

    python verificar_percepcion.py  -> ../resultados/verificacion_percepcion.json
"""

from __future__ import annotations

import gzip
import importlib
import json
import statistics as st
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
comp = importlib.import_module("06_comparar_enfoques")

# Vision y Gemini leen como maximo 5 paginas por documento (pdf_a_imagenes_base64);
# las paginas por documento salen de los inventarios de Tukit-Poc-Tesis.
PRECIO_VISION_POR_PAGINA = 1.5 / 1000  # USD, DOCUMENT_TEXT_DETECTION, primeras 1.000 unidades/mes gratis aparte


def main() -> int:
    with gzip.open(AQUI.parent / "datos" / "resultados_benchmark_10.json.gz", "rt", encoding="utf-8") as f:
        datos = json.load(f)
    paginas = json.loads((AQUI.parent / "datos" / "paginas_por_documento.json").read_text(encoding="utf-8"))
    salida = {}
    for nombre, filas in datos.items():
        m = comp.evaluar_enfoque(filas)
        lat = [r["latencia_s"] for r in filas]
        orden = sorted(lat)
        salida[nombre] = {
            "documentos": m["documentos"],
            "micro": m["micro"],
            "macro": m["macro"],
            "tp": m["tp_total"],
            "fp": m["fp_total"],
            "fn": m["fn_total"],
            "latencia_mediana_s": round(st.median(lat), 2),
            "latencia_media_s": round(st.mean(lat), 2),
            "latencia_p50_publicado_s": round(orden[len(orden) // 2], 2),
            "latencia_min_s": round(min(lat), 2),
            "latencia_max_s": round(max(lat), 2),
            "costo_total_usd": round(sum(r.get("costo_usd", 0) for r in filas), 5),
            "costo_medio_usd": round(st.mean(r.get("costo_usd", 0) for r in filas), 5),
        }
        if nombre == "Google Vision":
            pags = [min(5, paginas.get(r["archivo"], 1) or 1) for r in filas]
            salida[nombre]["paginas_leidas"] = sum(pags)
            salida[nombre]["costo_total_usd_por_pagina"] = round(sum(pags) * PRECIO_VISION_POR_PAGINA, 4)
            salida[nombre]["costo_medio_usd_por_pagina"] = round(st.mean(pags) * PRECIO_VISION_POR_PAGINA, 5)
    # Sesgos del montaje: (1) Vision, Baidu y Gemini leen <= 5 paginas, OCR y
    # Docling el documento entero, y el gold cubre en la practica las primeras
    # paginas, asi que lo que OCR/Docling leen despues de la pagina 5 cuenta como
    # falso positivo; (2) el gold se construyo editando una de las extracciones
    # (test_alternatives_app.py), y el 92,8 % de sus items es texto identico al de
    # Gemini. Se reporta el subconjunto justo (documentos de <= 5 paginas) y la
    # coincidencia literal gold-prediccion por enfoque.
    cortos = {a for a, p in paginas.items() if p is not None and p <= 5}
    subconjunto = {}
    literal = {}
    for nombre, filas in datos.items():
        sub = [r for r in filas if r["archivo"] in cortos]
        m = comp.evaluar_enfoque(sub)
        subconjunto[nombre] = {"documentos": len(sub), "items_gold": sum(len(r["items_gold_data"]) for r in sub), "micro": m["micro"]}
        exactos = total = 0
        for r in filas:
            pred = {comp.normalizar(x.get("descripcion", "")) for x in r["items_pred_data"]}
            gold = [comp.normalizar(x.get("descripcion", "")) for x in r["items_gold_data"]]
            exactos += sum(1 for g in gold if g in pred)
            total += len(gold)
        literal[nombre] = round(exactos / total, 4)
    salida["_subconjunto_documentos_hasta_5_paginas"] = subconjunto
    salida["_fraccion_gold_identica_a_la_prediccion"] = literal
    salida["_items_predichos_por_documento"] = {
        r["archivo"]: {"paginas": paginas.get(r["archivo"]), "gold": len(r["items_gold_data"]),
                       **{n: len(datos[n][i]["items_pred_data"]) for n in datos}}
        for i, r in enumerate(datos["OCR Baseline"])
    }
    destino = AQUI.parent / "resultados" / "verificacion_percepcion.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in salida.items():
        if k.startswith("_"):
            continue
        print(
            f"{k:15s} P={v['micro']['precision']:.3f} R={v['micro']['recall']:.3f} F1={v['micro']['f1']:.3f} "
            f"| macro F1={v['macro']['f1']:.3f} | mediana={v['latencia_mediana_s']} s "
            f"(publicado {v['latencia_p50_publicado_s']}) | costo={v['costo_total_usd']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
