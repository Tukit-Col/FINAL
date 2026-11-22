"""Colegio nuevo (Agustiniano Norte + Tagaste por grado) por la ruta real, sin etiquetas ni escrituras."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ruta_real as RR  # noqa: E402
from tukit_inteligencia import gemini  # noqa: E402
from tukit_inteligencia.dominio.pipeline import estado_desde_emparejamiento  # noqa: E402
from tukit_inteligencia.paginas import renderizar  # noqa: E402
from tukit_inteligencia.percepcion import percibir  # noqa: E402

RAIZ = RR.RAIZ
HOLD = RAIZ / "datos" / "holdout_agustinianos"
SALIDA = RR.SALIDA / "holdout_norte.csv"
CACHE = Path("/tmp/holdout_percepcion.json")
TOPE = 60
ORDEN = [
    "1J-JARDIN",
    "1T-TRANSICION",
    "1-PRIMERO",
    "2-SEGUNDO",
    "3-TERCERO",
    "4-CUARTO",
    "5-QUINTO",
    "6-SEXTO",
    "7-SEPTIMO",
    "8-OCTAVO",
    "9-NOVENO",
    "10-DECIMO",
    "11-ONCE",
]

cont = {
    "http": sum(d["llamadas"] for d in json.loads(Path("/tmp/holdout_percepcion.json").read_text()).values())
    if Path("/tmp/holdout_percepcion.json").exists()
    else 0
}
_real = urllib.request.urlopen


def _contando(*a, **k):
    if cont["http"] >= TOPE:
        raise RuntimeError("tope de llamadas alcanzado")
    cont["http"] += 1
    return _real(*a, **k)


urllib.request.urlopen = _contando  # type: ignore[assignment]


def leer_todo():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    fuentes = [("Agustiniano Norte", HOLD / "norte" / f"{g}.pdf", g) for g in ORDEN] + [
        ("Agustiniano Tagaste", HOLD / "tagaste_por_grado" / f"{g}.pdf", g) for g in ORDEN
    ]
    for colegio, pdf, g in fuentes:
        k = f"{colegio}|{g}"
        if k in cache:
            continue
        antes, t0 = cont["http"], time.time()
        r = percibir(pdf.read_bytes(), renderizar=renderizar, leer=gemini.pedir_pagina)
        cache[k] = {
            "colegio": colegio,
            "grado": g,
            "aceptada": r.aceptada,
            "error": r.error,
            "grados": list(r.grados),
            "paginas": r.paginas,
            "items": [i.descripcion for i in r.items],
            "llamadas": cont["http"] - antes,
            "segundos": round(time.time() - t0, 1),
        }
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        print(k, r.aceptada, r.error, len(r.items), cache[k]["llamadas"], cache[k]["segundos"], flush=True)
    return cache


def main():
    cache = leer_todo()
    docs = [v for v in cache.values()]
    ok = [d for d in docs if d["aceptada"]]
    textos = [t for d in ok for t in d["items"]]
    conceptos, productos = asyncio.run(RR.cargar_indice())
    antes = cont["http"]
    t0 = time.time()
    import os

    tn = [t for d in ok if d["colegio"].endswith("Norte") for t in d["items"]]
    tt = [t for d in ok if not d["colegio"].endswith("Norte") for t in d["items"]]
    clave = os.environ.pop("GEMINI_API_KEY")
    vn, nuevos = RR.vectores(tn)
    vt, _ = RR.vectores(tt)
    os.environ["GEMINI_API_KEY"] = clave
    print("Norte sin vector:", sum(v is None for v in vn), "de", len(vn))
    vecs = vn + vt
    print("Tagaste sin vector:", sum(v is None for v in vt), "de", len(vt))
    t_vec = time.time() - t0
    t0 = time.time()
    real = RR.correr(textos, vecs, conceptos, productos)
    sin_enc = RR.correr(textos, vecs, conceptos, productos, limpiador=False)
    t_res = time.time() - t0
    por_codigo = {c["codigo"]: c for c in conceptos}
    filas, i = [], 0
    for d in ok:
        for t in d["items"]:
            e, e1 = real[i], sin_enc[i]
            estado = estado_desde_emparejamiento(e.a_dict(), RR.TAU)
            titulo = e.concepto_codigo and RR.C.pide_titulo(
                por_codigo[e.concepto_codigo].get("discriminantes") or ()
            )
            if e.estado == "sin_match":
                rama = "sin_match"
            elif e1.concepto_codigo != e.concepto_codigo or abs(e1.parecido - e.parecido) > 1e-9:
                rama = "encabezado_limpiado"
            elif titulo:
                rama = "libro_con_titulo"
            elif e.estado == "abstencion":
                rama = "lexica_abstencion_atributos"
            else:
                rama = "lexica"
            filas.append(
                {
                    "colegio": d["colegio"],
                    "grado": d["grado"],
                    "id": f"H{i + 1:04d}",
                    "texto": t,
                    "concepto": e.concepto_codigo or "NINGUNO",
                    "puntaje": f"{e.parecido:.4f}",
                    "estado": estado,
                    "aceptado": "si" if estado == "RESUELTO_AUTO" else "no",
                    "rama": rama + ("" if vecs[i] is not None else "+sin_vector"),
                }
            )
            i += 1
    with SALIDA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(
        "LLAMADAS_TOTAL", cont["http"], "vectores_nuevos", nuevos, "llamadas_vectores", cont["http"] - antes
    )
    print("segundos vectores %.1f resolucion %.1f" % (t_vec, t_res))
    print("rechazados", [(d["colegio"], d["grado"], d["error"]) for d in docs if not d["aceptada"]])
    for col in ("Agustiniano Norte", "Agustiniano Tagaste"):
        fs = [f for f in filas if f["colegio"] == col]
        if not fs:
            continue
        print(
            "==",
            col,
            len(fs),
            "estados",
            dict(Counter(f["estado"] for f in fs)),
            "aceptado",
            sum(f["aceptado"] == "si" for f in fs),
            "ramas",
            dict(Counter(f["rama"] for f in fs)),
        )
        pg = Counter(f["grado"] for f in fs)
        print("por grado", dict(pg))
        for g in ORDEN:
            sub = [f for f in fs if f["grado"] == g]
            if sub:
                print(" ", g, len(sub), dict(Counter(f["estado"] for f in sub)))
    print("tiempos lectura", {f"{d['colegio'][-6:]}|{d['grado']}": d["segundos"] for d in docs})
    print("grados leidos", {f"{d['colegio'][-6:]}|{d['grado']}": d["grados"] for d in docs})


if __name__ == "__main__":
    main()
