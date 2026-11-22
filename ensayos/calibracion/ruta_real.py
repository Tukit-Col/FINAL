"""Mide la muestra ciega (240 renglones) por la RUTA REAL de produccion y el catalogo ACTUAL."""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "ensayos" / "calibracion" / "salidas"
MUESTRA_CIEGA = Path(__file__).resolve().parent / "datos" / "muestra_ciega"
MUESTRA = MUESTRA_CIEGA / "muestra.csv"
for r in ("servicios/catalogo", "servicios/inteligencia", "libs/py/tukit_comun", "ensayos/calibracion"):
    sys.path.insert(0, str(RAIZ / r))

import clasificacion as CL  # noqa: E402
from tukit_catalogo import clasificacion as D  # noqa: E402
from tukit_catalogo import consulta as C  # noqa: E402
from tukit_inteligencia.dominio.pipeline import estado_desde_emparejamiento  # noqa: E402
from tukit_inteligencia.parseo import BUSCA_EN_CATALOGO, parsear_renglon  # noqa: E402

TAU = 0.75
_LIMPIADOR = D._sin_encabezado_de_grupo
_PIDE = C.pide_titulo


async def cargar_indice():
    from sqlalchemy import text
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.connect() as con:
            await con.execute(text("SET TRANSACTION READ ONLY"))
            return await C.cargar_indice(con)
    finally:
        await motor.cerrar()


def vectores(textos):
    z = np.load(CL.DATOS / "vectores_renglones.npz", allow_pickle=False)
    en_cache = dict(zip(z["textos"].tolist(), z["vectores"].astype(np.float64), strict=True))
    faltan = [t for t in textos if t not in en_cache]
    if faltan:
        import os

        if os.environ.get("GEMINI_API_KEY", "").strip():
            from tukit_catalogo.embeddings import embeder_gemini

            for t, v in zip(faltan, embeder_gemini(faltan), strict=True):
                en_cache[t] = np.array(v, dtype=np.float64)
    return [en_cache[t].tolist() if t in en_cache else None for t in textos], len(faltan)


def correr(textos, vecs, conceptos, productos, *, limpiador=True, libros=True):
    D._sin_encabezado_de_grupo = _LIMPIADOR if limpiador else (lambda r, c: r)
    C._sin_encabezado_de_grupo = D._sin_encabezado_de_grupo
    C.pide_titulo = _PIDE if libros else (lambda d: False)
    try:
        return [C.emparejar(t, conceptos, productos, embedding_renglon=v) for t, v in zip(textos, vecs, strict=True)]
    finally:
        D._sin_encabezado_de_grupo = _LIMPIADOR
        C.pide_titulo = _PIDE


def vieja(textos, vecs):
    d = CL.cargar(con_vectores=False)
    d.textos = list(textos)
    d.corr = [CL.corregir(t, CL.lexico_de(d.conceptos)) for t in textos]
    d.vectores = np.array(vecs)
    r = CL.construir_rasgos(d)
    idx, s = CL.puntuar(r, CL.ACTUAL)
    return [(d.codigos[i] if (i >= 0 and sc >= CL.ACTUAL["corte"]) else None, float(sc)) for i, sc in zip(idx, s)]


def main():
    filas = list(csv.DictReader(MUESTRA.open(encoding="utf-8")))
    textos = [f["texto_original"] for f in filas]
    conceptos, productos = asyncio.run(cargar_indice())
    vecs, nuevos = vectores(textos)
    sin_vec = sum(v is None for v in vecs)
    real = correr(textos, vecs, conceptos, productos)
    sin_enc = correr(textos, vecs, conceptos, productos, limpiador=False)
    sin_lib = correr(textos, vecs, conceptos, productos, libros=False)
    sin_ambos = correr(textos, vecs, conceptos, productos, limpiador=False, libros=False)
    ant = vieja(textos, vecs)
    por_codigo = {c["codigo"]: c for c in conceptos}

    def aceptado(e):
        return estado_desde_emparejamiento(e.a_dict(), TAU) == "RESUELTO_AUTO"

    salida, difs = [], []
    for f, t, e, e1, e2, e3, (cv, pv) in zip(filas, textos, real, sin_enc, sin_lib, sin_ambos, ant, strict=True):
        dem = parsear_renglon(t)
        busca = dem.tipo_item in BUSCA_EN_CATALOGO
        estado = estado_desde_emparejamiento(e.a_dict(), TAU)
        concepto = e.concepto_codigo or "NINGUNO"
        titulo = e.concepto_codigo and C.pide_titulo(por_codigo[e.concepto_codigo].get("discriminantes") or ())
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
        if not busca:
            rama += "+no_busca_catalogo(tipo=%s)" % dem.tipo_item
        salida.append(
            {
                "id": f["id"],
                "concepto": concepto,
                "puntaje": f"{e.parecido:.4f}",
                "estado": estado,
                "aceptado": "si" if estado == "RESUELTO_AUTO" else "no",
                "rama": rama,
            }
        )
        ac_v = cv is not None and pv >= TAU
        if (e.concepto_codigo != cv) or (aceptado(e) != ac_v):
            same = lambda x: x.concepto_codigo == cv and aceptado(x) == ac_v  # noqa: E731
            if same(e1) and not same(e2):
                causa = "encabezado"
            elif same(e2) and not same(e1):
                causa = "libros"
            elif same(e3):
                causa = "ambos(encabezado+libros)"
            elif e.concepto_codigo != cv:
                causa = "otro_concepto_distinto(catalogo actual/centroides)"
            elif e.estado == "abstencion":
                causa = "atributos(abstencion)"
            elif e.estado == "hueco_catalogo":
                causa = "sin_producto_en_catalogo_actual"
            else:
                causa = "otro_puntaje(centroides vivos)"
            difs.append((f["id"], t, cv, round(pv, 3), e.concepto_codigo, round(e.parecido, 3), estado, causa))
    with (SALIDA / "ruta_real_muestra.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(salida[0]))
        w.writeheader()
        w.writerows(salida)
    from collections import Counter

    print("n", len(salida), "sin_vector", sin_vec, "vectores_nuevos_gemini", nuevos)
    print("estados", dict(Counter(s["estado"] for s in salida)))
    print("aceptados", sum(s["aceptado"] == "si" for s in salida))
    print("ramas", dict(Counter(s["rama"].split("+")[0] for s in salida)))
    print("concepto distinto", sum(1 for t_, e, (cv, _) in zip(textos, real, ant) if e.concepto_codigo != cv),
          "| puntaje distinto >0.001", sum(1 for e, (cv, pv) in zip(real, ant) if abs(e.parecido - pv) > 1e-3 and e.concepto_codigo == cv))
    print("diferencias", len(difs), dict(Counter(d[-1] for d in difs)))
    for d in difs:
        print(" | ".join(map(str, d)))


if __name__ == "__main__":
    main()
