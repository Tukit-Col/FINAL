"""Nucleo del barrido: la clasificacion de `descubrir.clasificar` con constantes parametrizables.

La funcion real (`tukit_catalogo.descubrir.clasificar`) tiene las constantes cableadas y recorre
todos los candidatos de todos los conceptos en Python puro. Para barrer miles de combinaciones
se separa en dos pasos que, juntos, dan EXACTAMENTE lo mismo:

  1. Rasgos (no dependen de las constantes): para cada renglon y cada candidato (nombre o
     sinonimo de un concepto) se calcula con las funciones reales del modulo si el candidato
     acierta la cabeza, si la nombra, su parecido (Jaccard) y, por concepto, el coseno contra
     el centro de sus productos (`promedio` de producto_canonico.embedding).
  2. Puntaje (depende de las constantes): la misma formula de `clasificar`, vectorizada, y el
     mismo desempate (primer maximo estricto, en el orden del catalogo).

`validar` compara este camino con `clasificar` y `emparejar` reales sobre todos los renglones.
No se modifica ningun archivo del sistema: se importa tal cual.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
DATOS = Path(__file__).resolve().parent / "datos"
MUESTRA_CIEGA = DATOS / "muestra_ciega"
SALIDA = RAIZ / "ensayos" / "calibracion" / "salidas"
for ruta in (str(RAIZ / "servicios" / "catalogo"), str(RAIZ / "libs" / "py" / "tukit_comun")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from tukit_catalogo import clasificacion as D  # noqa: E402
from tukit_catalogo.routers.admin import sinonimo_de_renglon  # noqa: E402
from tukit_catalogo.transcripcion import corregir, lexico_de  # noqa: E402

# Valores de produccion hoy (descubrir.py y UMBRAL de emparejar/consulta, TAU de inteligencia).
ACTUAL = {
    "piso": 0.6,  # piso si la frase empieza por la cabeza
    "w_jac": 0.4,  # peso del Jaccard
    "w_cos": D._APORTE_COSENO,  # 0.15
    "res_cos": getattr(D, "_RESCATE_COSENO", 1.01),  # 1.01 = sin rescate (el clasificador de produccion ya no lo trae)
    "res_piso": getattr(D, "_PISO_RESCATE", 0.55),
    "corte": 0.5,  # `parecido < 0.5` -> sin_match
    "tau": 0.75,
}
PENDIENTE_RESCATE = 0.4  # fija en la formula del rescate (no es una de las 7 constantes)
CLAVES_PUNTAJE = ("piso", "w_jac", "w_cos", "res_cos", "res_piso")


@dataclass
class Datos:
    filas: list[dict]  # colegio, grado, texto, etiqueta (codigo o None), lista, u (indice de texto unico)
    textos: list[str]  # textos unicos (crudos)
    conceptos: list[dict]  # catalogo en el orden de la base
    codigos: list[str]
    vectores: np.ndarray | None  # (U, 1024) o None
    cent: np.ndarray | None  # (C, 1024), fila de ceros si el concepto no tiene centroide
    tiene_cent: np.ndarray  # (C,) bool
    corr: list[str] = field(default_factory=list)  # texto corregido por unico


def cargar_filas() -> list[dict]:
    filas = []
    for x in csv.DictReader((DATOS / "renglones_etiquetados.csv").open(encoding="utf-8")):
        filas.append(
            {
                "colegio": x["colegio"],
                "grado": x["grado"],
                "texto": x["texto_original"],
                "etiqueta": x["concepto_codigo"] or None,
                "lista": f'{x["colegio"]}|{x["grado"]}',
            }
        )
    return filas


def vectorizar(textos: list[str]) -> np.ndarray | None:
    """Vectores de Gemini (el mismo embeder del sistema) de los renglones CRUDOS, con cache en disco."""
    ruta = DATOS / "vectores_renglones.npz"
    if ruta.exists():
        z = np.load(ruta, allow_pickle=False)
        if list(z["textos"]) == textos:
            return z["vectores"].astype(np.float64)
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        return None
    from tukit_catalogo.embeddings import embeder_gemini

    v = np.array(embeder_gemini(textos), dtype=np.float32)
    np.savez_compressed(ruta, textos=np.array(textos), vectores=v)
    return v.astype(np.float64)


def cargar(con_vectores: bool = True) -> Datos:
    filas = cargar_filas()
    cat = json.load((DATOS / "catalogo_conceptos.json").open(encoding="utf-8"))
    conceptos = [
        {
            "id": c["id"],
            "codigo": c["codigo"],
            "nombre": c["nombre"],
            "sinonimos": list(c["sinonimos"]),
            "discriminantes": tuple(c["discriminantes"]),
            "tipo_item": c["tipo_item"],
        }
        for c in cat["conceptos"]
    ]
    textos = sorted({f["texto"] for f in filas})
    ind = {t: i for i, t in enumerate(textos)}
    for f in filas:
        f["u"] = ind[f["texto"]]
    z = np.load(DATOS / "centroides.npz", allow_pickle=False)
    por = dict(zip(z["codigos"].tolist(), z["centroides"].astype(np.float64), strict=True))
    dim = len(next(iter(por.values())))
    cent = np.array([por.get(c["codigo"], np.zeros(dim)) for c in conceptos])
    tiene = np.array([c["codigo"] in por for c in conceptos])
    lex = lexico_de(conceptos)
    d = Datos(
        filas=filas,
        textos=textos,
        conceptos=conceptos,
        codigos=[c["codigo"] for c in conceptos],
        vectores=vectorizar(textos) if con_vectores else None,
        cent=cent,
        tiene_cent=tiene,
    )
    d.corr = [corregir(t, lex) for t in textos]
    return d


# ---------------------------------------------------------------------------
# Rasgos
# ---------------------------------------------------------------------------


@dataclass
class Rasgos:
    jac: np.ndarray  # (U, K)
    caso: np.ndarray  # (U, K) int8: 1 cabeza, 2 nombra la cabeza, 0 ninguna
    cos: np.ndarray  # (U, K) coseno del concepto de la columna (recortado en 0)
    col_concepto: np.ndarray  # (K,) indice del concepto
    col_texto: list[str]
    col_tipo: list[str]  # nombre | base | pool
    orden: np.ndarray  # (K,) posicion para el desempate: (concepto, insercion)


def construir_rasgos(d: Datos, pool: list[tuple[int, str]] | None = None) -> Rasgos:
    """Rasgos de cada renglon contra cada candidato del catalogo y del `pool` de sinonimos por aprender."""
    cols: list[tuple[int, str, str]] = []
    vistos: set[tuple[int, str]] = set()
    for i, c in enumerate(d.conceptos):
        cols.append((i, c["nombre"], "nombre"))
        vistos.add((i, c["nombre"]))
        for s in c["sinonimos"]:
            cols.append((i, s, "base"))
            vistos.add((i, s))
    for i, s in pool or []:
        if (i, s) not in vistos:
            cols.append((i, s, "pool"))
            vistos.add((i, s))
    K, U = len(cols), len(d.textos)
    prep = []
    for t in d.corr:
        r = D.RANGO_DUREZA.sub(" serie durezas ", D._plano(t))
        r = D.PAR_DE_ESCUADRAS.sub(" escuadras juego ", r)
        prep.append((r, D._significativas(r), D.cabeza(r)))
    cand = []
    for _, texto, _ in cols:
        pal = D._plano(texto).split()
        cand.append((pal, D._significativas(texto)))
    jac = np.zeros((U, K))
    caso = np.zeros((U, K), dtype=np.int8)
    memo: dict[tuple[str, str], bool] = {}

    def misma(a: str, b: str) -> bool:
        k = (a, b)
        if k not in memo:
            memo[k] = D._misma_cosa(a, b)
        return memo[k]

    for u, (_, pu, nuc) in enumerate(prep):
        for k, (pal, pk) in enumerate(cand):
            if pu and pk:
                jac[u, k] = len(pu & pk) / len(pu | pk)
            if nuc:
                if pal and misma(nuc, pal[0]):
                    caso[u, k] = 1
                elif any(misma(nuc, w) for w in pal):
                    caso[u, k] = 2
    if d.vectores is not None:
        cosc = np.maximum(0.0, d.vectores @ d.cent.T)  # vectores unitarios
        cosc[:, ~d.tiene_cent] = 0.0
    else:
        cosc = np.zeros((U, len(d.conceptos)))
    col_c = np.array([c for c, _, _ in cols])
    orden = np.lexsort((np.arange(K), col_c))  # por concepto, luego insercion
    r = Rasgos(jac, caso, cosc[:, col_c], col_c, [t for _, t, _ in cols], [k for _, _, k in cols], np.argsort(orden))
    # reordenar columnas para que el argmax respete (concepto, insercion)
    p = orden
    return Rasgos(r.jac[:, p], r.caso[:, p], r.cos[:, p], r.col_concepto[p], [r.col_texto[i] for i in p], [r.col_tipo[i] for i in p], np.arange(K))


# ---------------------------------------------------------------------------
# Puntaje (la formula de `clasificar`)
# ---------------------------------------------------------------------------


def puntuar(r: Rasgos, cfg: dict, activas: np.ndarray | None = None, filas: np.ndarray | None = None):
    """(concepto_idx, puntaje) por renglon unico; concepto_idx = -1 si ningun candidato puntua > 0."""
    sl = slice(None) if filas is None else filas
    jac, caso, cos = r.jac[sl], r.caso[sl], r.cos[sl]
    cc = r.col_concepto
    if activas is not None:
        jac, caso, cos, cc = jac[:, activas], caso[:, activas], cos[:, activas], cc[activas]
    w = cfg["w_cos"]
    res = cfg["res_cos"]
    p = np.where(
        caso == 1,
        np.minimum(1.0, cfg["piso"] + cfg["w_jac"] * jac + w * cos),
        np.where(
            caso == 2,
            np.minimum(1.0, jac + w * cos),
            np.where(cos >= res, cfg["res_piso"] + (PENDIENTE_RESCATE * (cos - res) / (1.0 - res)), 0.0),
        ),
    )
    j = p.argmax(1)
    s = p[np.arange(p.shape[0]), j]
    idx = np.where(s > 0.0, cc[j], -1)
    return idx, np.where(s > 0.0, s, 0.0)


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------


def metricas(pred: np.ndarray, s: np.ndarray, y: np.ndarray, corte: float, tau: float) -> dict:
    """pred/y: indice de concepto (-1 = ninguno). Correcto: coincide (sin_match == sin etiqueta tambien)."""
    pred_c = np.where(s >= corte, pred, -1)
    ok = pred_c == y
    acepta = (s >= tau) & (pred_c >= 0)
    ok_acepta = acepta & ok
    n = len(y)
    na = int(acepta.sum())
    return {
        "n": n,
        "exactitud": float(ok.mean()) if n else None,
        "aceptada": na / n if n else None,
        "precision_aceptada": float(ok_acepta.sum() / na) if na else None,
        "auto_correcta": float(ok_acepta.sum() / n) if n else None,
        "revision_humana": 1 - na / n if n else None,
    }


def etiquetas(d: Datos) -> np.ndarray:
    ind = {c: i for i, c in enumerate(d.codigos)}
    return np.array([ind[f["etiqueta"]] if f["etiqueta"] else -1 for f in d.filas])


def validar(d: Datos, r: Rasgos, muestra_emparejar: int = 400) -> dict:
    """Con las constantes actuales, el camino vectorizado = `clasificar` y `emparejar` reales."""
    from tukit_catalogo.consulta import emparejar

    concs = []
    for i, c in enumerate(d.conceptos):
        e = dict(c)
        e["embedding"] = d.cent[i].tolist() if d.tiene_cent[i] and d.vectores is not None else None
        concs.append(e)
    pos = {c["id"]: i for i, c in enumerate(d.conceptos)}
    idx, s = puntuar(r, ACTUAL)
    dif = 0
    dif_s = 0.0
    for u, t in enumerate(d.corr):
        v = d.vectores[u].tolist() if d.vectores is not None else None
        cid, _, sc = D.clasificar(t, concs, embedding_renglon=v)
        real = pos[cid] if cid is not None else -1
        if real != int(idx[u]):
            dif += 1
        dif_s = max(dif_s, abs(sc - float(s[u])))
    # emparejar real (corrige + clasifica + corte 0.5) sobre una muestra con orden fijo
    rng = np.random.default_rng(0)
    n_emp = min(muestra_emparejar, len(d.textos))
    dif_emp = 0
    for u in rng.choice(len(d.textos), n_emp, replace=False):
        v = d.vectores[u].tolist() if d.vectores is not None else None
        e = emparejar(d.textos[u], concs, [], embedding_renglon=v)
        mio = d.codigos[int(idx[u])] if (idx[u] >= 0 and s[u] >= ACTUAL["corte"]) else None
        if e.concepto_codigo != mio:
            dif_emp += 1
    return {
        "textos_unicos": len(d.textos),
        "difieren_de_clasificar": dif,
        "max_dif_puntaje": dif_s,
        "emparejar_muestra": n_emp,
        "difieren_de_emparejar": dif_emp,
    }
