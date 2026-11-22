"""Vectoriza los textos unicos de holdout_norte.csv que faltan en cache y resuelve de nuevo (v2)."""

from __future__ import annotations

import asyncio
import csv
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ruta_real as RR  # noqa: E402
from tukit_catalogo import embeddings as EM  # noqa: E402
from tukit_inteligencia.dominio.pipeline import estado_desde_emparejamiento  # noqa: E402

TOPE = 16
ENTRADA = RR.SALIDA / "holdout_norte.csv"
SALIDA = RR.SALIDA / "holdout_norte_v2.csv"
NPZ_NUEVO = RR.CL.DATOS / "vectores_holdout.npz"
NPZ_VIEJO = RR.CL.DATOS / "vectores_renglones.npz"
llamadas = {"n": 0}
_real = urllib.request.urlopen


def _contando(*a, **k):
    if llamadas["n"] >= TOPE:
        raise RuntimeError("tope de llamadas alcanzado")
    llamadas["n"] += 1
    return _real(*a, **k)


def cargar(ruta):
    if not ruta.exists():
        return {}
    z = np.load(ruta, allow_pickle=False)
    return dict(zip(z["textos"].tolist(), z["vectores"].astype(np.float64), strict=True))


def main():
    filas = list(csv.DictReader(ENTRADA.open(encoding="utf-8")))
    textos = [f["texto"] for f in filas]
    cache = {**cargar(NPZ_VIEJO), **cargar(NPZ_NUEVO)}
    faltan = list(dict.fromkeys(t for t in textos if t not in cache))
    por_col = {
        c: len({f["texto"] for f in filas if f["colegio"] == c} - set(cache))
        for c in {f["colegio"] for f in filas}
    }
    print("faltan", len(faltan), por_col)
    if faltan:
        urllib.request.urlopen = _contando  # type: ignore[assignment]
        EM.urllib.request.urlopen = _contando
        nuevos = {}
        for i in range(0, len(faltan), 100):
            lote = faltan[i : i + 100]
            for t, v in zip(lote, EM.embeder_gemini(lote), strict=True):
                nuevos[t] = np.array(v, dtype=np.float32)
            np.savez(NPZ_NUEVO, textos=np.array(list(nuevos)), vectores=np.stack(list(nuevos.values())))
        cache.update({t: v.astype(np.float64) for t, v in nuevos.items()})
    print("LLAMADAS", llamadas["n"])

    vecs = [cache[t].tolist() if t in cache else None for t in textos]
    conceptos, productos = asyncio.run(RR.cargar_indice())
    real = RR.correr(textos, vecs, conceptos, productos)
    sin_enc = RR.correr(textos, vecs, conceptos, productos, limpiador=False)
    por_codigo = {c["codigo"]: c for c in conceptos}
    out = []
    for f, e, e1, v in zip(filas, real, sin_enc, vecs, strict=True):
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
        out.append(
            {
                "colegio": f["colegio"],
                "grado": f["grado"],
                "id": f["id"],
                "texto": f["texto"],
                "concepto": e.concepto_codigo or "NINGUNO",
                "puntaje": f"{e.parecido:.4f}",
                "estado": estado,
                "aceptado": "si" if estado == "RESUELTO_AUTO" else "no",
                "rama": rama + ("" if v is not None else "+sin_vector"),
                "comparable": "si" if v is not None else "no",
            }
        )
    with SALIDA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for col in sorted({f["colegio"] for f in filas}):
        idx = [i for i, f in enumerate(filas) if f["colegio"] == col]
        n = len(idx)
        est = Counter(out[i]["estado"] for i in idx)
        acept = est["RESUELTO_AUTO"]
        cambia_e = sum(out[i]["estado"] != filas[i]["estado"] for i in idx)
        cambia_c = sum(out[i]["concepto"] != filas[i]["concepto"] for i in idx)
        cambia_ec = sum(
            out[i]["estado"] != filas[i]["estado"] or out[i]["concepto"] != filas[i]["concepto"] for i in idx
        )
        sv = sum(out[i]["comparable"] == "no" for i in idx)
        sv0 = sum("sin_vector" in filas[i]["rama"] for i in idx)
        print(
            col,
            n,
            dict(est),
            "aceptada %.3f revision %.3f" % (acept / n, (n - acept) / n),
            "sin_vector v1/v2",
            sv0,
            sv,
            "cambian estado",
            cambia_e,
            "concepto",
            cambia_c,
            "alguno",
            cambia_ec,
        )


if __name__ == "__main__":
    main()
