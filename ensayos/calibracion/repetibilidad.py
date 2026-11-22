"""Repetibilidad de la lectura: la misma lista, leida N veces, ¿da lo mismo?"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "servicios" / "inteligencia"))
ARCHIVO = RAIZ.parent / "_archivo/2026-11-05/borradores_arquitectura/Arquitectura/UTILES_COLEGIO_GRADO"
ORO = RAIZ / "datos/listas/oe1/Corpus_ItemLista.csv"
SALIDA = RAIZ / "ensayos/calibracion/salidas/repetibilidad.json"

DOCUMENTOS = [
    ("CACS_SEPTIMO", "2.13", "Septimo"),
    ("CACS_TERCERO", "2.13", "Tercero"),
    ("CACS_JARDIN", "2.13", "Jardin"),
    ("MODELIA_SEXTO", "2.9", "Sexto"),
    ("BAHIASOLANO_DECIMO", "2.11", "Decimo"),
    ("BAHIASOLANO_QUINTO", "2.11", "Quinto"),
]
TOPE_LLAMADAS_POR_DOC_CORRIDA = 30


def norma(texto: str) -> frozenset[str]:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return frozenset(w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 1)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def f1_contra(items: list[str], oro: list[str], umbral: float = 0.5) -> dict:
    a = [norma(x) for x in items]
    g = [norma(x) for x in oro]
    pares = sorted(
        ((jaccard(x, y), i, j) for i, x in enumerate(a) for j, y in enumerate(g)), reverse=True
    )
    ua, ug, tp = set(), set(), 0
    for s, i, j in pares:
        if s < umbral:
            break
        if i in ua or j in ug:
            continue
        ua.add(i), ug.add(j)
        tp += 1
    p = tp / len(a) if a else 0.0
    r = tp / len(g) if g else 0.0
    return {"tp": tp, "leidos": len(a), "oro": len(g), "f1": 2 * p * r / (p + r) if p + r else 0.0}


def clave_item(i: dict) -> tuple:
    return (" ".join(sorted(norma(i["descripcion"]))), i["cantidad"])


def diferencias(base: list[dict], otra: list[dict]) -> dict:
    cb = Counter(clave_item(i) for i in base)
    co = Counter(clave_item(i) for i in otra)
    solo_base = cb - co
    solo_otra = co - cb
    desc_b = Counter(k[0] for k in solo_base.elements())
    desc_o = Counter(k[0] for k in solo_otra.elements())
    cambian = sum((desc_b & desc_o).values())
    desaparecen = sum(desc_b.values()) - cambian
    aparecen = sum(desc_o.values()) - cambian
    return {
        "aparecen": aparecen,
        "desaparecen": desaparecen,
        "cambian_cantidad": cambian,
        "renglones_distintos": aparecen + desaparecen + cambian,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridas", type=int, default=5)
    n = ap.parse_args().corridas

    import os

    if not os.environ.get("GEMINI_API_KEY", "").strip():
        SALIDA.write_text(
            json.dumps({"ejecutado": False, "motivo": "No habia GEMINI_API_KEY en el entorno."}, indent=2)
        )
        print("Sin GEMINI_API_KEY: no se midio nada.")
        return 0

    from tukit_inteligencia import gemini
    from tukit_inteligencia.gemini import pedir_pagina
    from tukit_inteligencia.paginas import renderizar
    from tukit_inteligencia.percepcion import percibir

    contador = {"http": 0}
    real = urllib.request.urlopen

    def contando(*a, **k):
        contador["http"] += 1
        return real(*a, **k)

    gemini.urllib.request.urlopen = contando  # type: ignore[assignment]

    import csv

    with ORO.open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    resultado = {
        "ejecutado": True,
        "modelo": gemini.modelo(),
        "temperatura": 0,
        "ppp": 150,
        "corridas_por_documento": n,
        "documentos": [],
    }
    for nombre, cod, grado in DOCUMENTOS:
        pdf = ARCHIVO / f"{nombre}.pdf"
        contenido = pdf.read_bytes()
        oro = [r["texto_original"] for r in filas if r["colegio_id"] == cod and r["grado"] == grado]
        paginas = len(renderizar(contenido))
        corridas = []
        for k in range(n):
            antes = contador["http"]
            t0 = time.time()
            r = percibir(contenido, renderizar=renderizar, leer=pedir_pagina)
            llamadas = contador["http"] - antes
            assert llamadas <= TOPE_LLAMADAS_POR_DOC_CORRIDA
            items = [{"descripcion": i.descripcion, "cantidad": i.cantidad} for i in r.items]
            corridas.append(
                {
                    "aceptada": r.aceptada,
                    "error": r.error,
                    "grados": list(r.grados),
                    "items": items,
                    "llamadas": llamadas,
                    "segundos": round(time.time() - t0, 1),
                }
            )
            print(nombre, k + 1, r.aceptada, len(items), flush=True)
        ok = [c for c in corridas if c["aceptada"]]
        huellas = [json.dumps({"g": c["grados"], "i": c["items"]}, sort_keys=True, ensure_ascii=False) for c in ok]
        mas_comun = Counter(huellas).most_common(1)[0][1] if huellas else 0
        f1s = [f1_contra([i["descripcion"] for i in c["items"]], oro)["f1"] for c in ok] if oro else []
        dif = [diferencias(ok[0]["items"], c["items"]) for c in ok[1:]]
        conj = [set(clave_item(i) for i in c["items"]) for c in ok]
        inestables = len(set.union(*conj) - set.intersection(*conj)) if conj else 0
        resultado["documentos"].append(
            {
                "documento": nombre,
                "paginas": paginas,
                "referencia": "oro Corpus_ItemLista" if oro else "primera corrida",
                "items_oro": len(oro),
                "corridas_ok": len(ok),
                "items_por_corrida": [len(c["items"]) for c in ok],
                "corridas_identicas_pct": round(100 * mas_comun / len(ok), 1) if ok else None,
                "pares_identicos_con_la_primera": sum(1 for h in huellas[1:] if h == huellas[0]),
                "renglones_distintos_vs_primera": [d["renglones_distintos"] for d in dif],
                "detalle_vs_primera": dif,
                "renglones_inestables_union_menos_interseccion": inestables,
                "f1_por_corrida": [round(x, 4) for x in f1s],
                "f1_media": round(statistics.mean(f1s), 4) if f1s else None,
                "f1_rango": round(max(f1s) - min(f1s), 4) if f1s else None,
                "f1_desv": round(statistics.pstdev(f1s), 4) if f1s else None,
                "llamadas_http": sum(c["llamadas"] for c in corridas),
                "corridas": corridas,
            }
        )
        SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    resultado["llamadas_http_total"] = contador["http"]
    docs = [d for d in resultado["documentos"] if d["corridas_ok"]]
    if docs:
        tot = sum(d["corridas_ok"] for d in docs)
        resultado["resumen"] = {
            "documentos_con_las_5_identicas": sum(1 for d in docs if d["corridas_identicas_pct"] == 100.0),
            "documentos": len(docs),
            "corridas_identicas_pct_promedio": round(statistics.mean(d["corridas_identicas_pct"] for d in docs), 1),
            "renglones_inestables_total": sum(d["renglones_inestables_union_menos_interseccion"] for d in docs),
            "f1_rango_max": max(d["f1_rango"] for d in docs if d["f1_rango"] is not None),
        }
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    print("llamadas HTTP:", contador["http"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
