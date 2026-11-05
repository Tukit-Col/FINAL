"""Fase 0 — ¿Normalizar el catálogo mejora el retrieval? Experimento offline.

Antes de construir un módulo de normalización de ingesta (y tocar esquema,
seeds y Stage 2), se mide si normalizar el TEXTO que ven las dos señales del
retrieval cambia algo sobre el gold-standard:

    - el cross-encoder (``rerank_score``), que ve ``nombre | categoria | marca``
      (pipeline/reranker.py:build_document_text) y es la señal que decide τ;
    - el embedding e5 (``vec_score``), que ve ``texto_embedding``
      (db/seed_catalogo.py:texto_embedding).

Problemas medidos en el catálogo que motivan esto (no supuestos):
    - 660 textos de marca que son 605 marcas reales (NORMA/Norma/CUADERNOS
      NORMA...) y pseudo-marcas (GENERICO, Importado, nombre de la tienda).
    - un mismo tipo de producto repartido en hasta 6 categorías.
    - ``texto_embedding`` mete "Precio 49900" y el proveedor en el vector.
    - presentación escrita de 5+ formas (x 12 uds, Paq X 10 Und, por 10...).

Variantes (acumulativas, salvo V3b que es alternativa a V3):
    V0   texto actual — baseline recalculado aquí mismo, no leído del CSV
    V1   marca canónica; pseudo-marcas → sin marca
    V2   V1 + texto_embedding sin precio/proveedor/campos vacíos
    V3   V2 + categoría canónica (concepto → categoría de la taxonomía actual)
    V3b  V2 + concepto fino como categoría ("Bloc", "Cartulina"...)
    V4   V3 + presentación normalizada en el nombre ("x 12 uds" → "12 unidades")

Límite honesto: el pool de 5 candidatos por ítem queda FIJO (lo anotado). Esto
mide si la normalización ordena y puntúa mejor lo que ya se recuperó, no si
trae candidatos nuevos al top-5 (eso requiere BD re-normalizada — Fase 4).

Nada de esto toca Postgres, la ingesta ni el pipeline de producción.

Uso:
    python calibration/medir_normalizacion.py                 # calcula scores (~15 min en CPU) y resume
    python calibration/medir_normalizacion.py --desde-scores  # solo resume desde normalizacion_scores.csv
"""

import argparse
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))

import json  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

from db.seed_catalogo import generar_sku  # noqa: E402
from db.seed_catalogo import texto_embedding as texto_embedding_seed  # noqa: E402
from pipeline.grafo_sustituibilidad import CONCEPTOS, concepto_desde_nombre  # noqa: E402
from pipeline.reranker import build_document_text, get_reranker  # noqa: E402

CSV = BASE / "gold_standard_final.csv"
CATALOGO_SEED = BASE.parent / "db" / "seed" / "catalogo_utiles.json"
CATALOGO_GRANCENTRAL = BASE / "_grancentral_catalogo.json"
SALIDA_SCORES = BASE / "normalizacion_scores.csv"
SALIDA_RESUMEN = BASE / "normalizacion_resumen.csv"

TAU = 0.630
N_BOOTSTRAP = 2000
SEMILLA = 42


# ---------------------------------------------------------------------------
# Normalizaciones candidatas (se mueven a db/normalizacion.py solo si ganan)
# ---------------------------------------------------------------------------

def clave(texto: str | None) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", t)


# No son marcas: describen origen o la tienda, y en el texto del documento
# solo meten ruido que el cross-encoder y e5 tratan como si fuera identidad.
PSEUDO_MARCAS = frozenset({
    "", "nan", "none", "generico", "generica", "importado", "sinmarca",
    "papeleriagrancentralsanvictorino", "papeleriagrancentral",
})

# Casos que la clave alfanumérica sola no une (verificados en el catálogo).
ALIAS_CLAVE = {
    "cuadernosnorma": "norma",
}


def construir_marcas_canonicas() -> dict[str, str]:
    """clave → grafía más frecuente en todo el catálogo (las 3 fuentes)."""
    conteo: dict[str, Counter] = {}
    seed = json.loads(CATALOGO_SEED.read_text(encoding="utf-8"))["productos"]
    marcas = [p.get("marca") for p in seed]
    if CATALOGO_GRANCENTRAL.exists():
        marcas += [x.get("vendor") for x in json.loads(CATALOGO_GRANCENTRAL.read_text(encoding="utf-8"))]
    for m in marcas:
        if not m or not str(m).strip():
            continue
        k = ALIAS_CLAVE.get(clave(m), clave(m))
        conteo.setdefault(k, Counter())[str(m).strip()] += 1
    return {k: c.most_common(1)[0][0] for k, c in conteo.items()}


def normalizar_marca(marca: str | None, canonicas: dict[str, str]) -> str | None:
    if marca is None or (isinstance(marca, float) and np.isnan(marca)):
        return None
    k = clave(marca)
    k = ALIAS_CLAVE.get(k, k)
    if k in PSEUDO_MARCAS:
        return None
    return canonicas.get(k, str(marca).strip())


CONCEPTO_A_CATEGORIA = {
    "esfero": "Boligrafos y esferos", "lapiz": "Lapices y portaminas",
    "marcador": "Marcadores", "cuaderno": "Cuadernos",
    "pegamento": "Adhesivos y pegamentos", "cinta": "Adhesivos y pegamentos",
    "sacapuntas": "Sacapuntas", "borrador": "Borradores",
    "cartuchera": "Cartucheras y estuches", "mochila": "Maleteria", "lonchera": "Maleteria",
    "corrector": "Correctores", "tijera": "Tijeras", "resaltador": "Resaltadores",
    "regla": "Geometria", "escuadra": "Geometria", "compas": "Geometria", "transportador": "Geometria",
    "carpeta": "Archivo y organizacion", "perforadora": "Archivo y organizacion",
    "grapadora": "Archivo y organizacion", "rotulo": "Archivo y organizacion",
    "vinilo": "Pinturas", "acuarela": "Pinturas", "oleo": "Pinturas", "tempera": "Pinturas", "pincel": "Pinturas",
    "cartulina": "Papel y cartulina", "papel": "Papel y cartulina", "bloc": "Papel y cartulina",
    "colores": "Colores",
    "algodon": "Manualidades", "lentejuela": "Manualidades", "escarcha": "Manualidades", "punzon": "Manualidades",
}
_faltantes = set(CONCEPTOS) - set(CONCEPTO_A_CATEGORIA)
assert not _faltantes, f"Conceptos sin categoría asignada: {_faltantes}"


def categoria_canonica(nombre: str, categoria_fuente: str | None) -> str | None:
    concepto = concepto_desde_nombre(nombre)
    return CONCEPTO_A_CATEGORIA[concepto] if concepto else categoria_fuente


def concepto_fino(nombre: str, categoria_fuente: str | None) -> str | None:
    concepto = concepto_desde_nombre(nombre)
    return concepto.capitalize() if concepto else categoria_fuente


# "x 12 unidades", "x 12 uds", "Paq X 10 Und", "por 10 unidades".
# No toca dimensiones ("70X100": dígito pegado antes de la x) ni cantidades con
# otra unidad ("x 35 hojas", "x 12 colores"). Un "x 100" suelto tampoco: en
# "Cuaderno 1/8 x 100" son hojas, no unidades — sin palabra de unidad ni
# "paquete" delante, la presentación es ambigua y se deja como está.
_PRESENTACION = re.compile(
    r"(?<![\w/])(?P<paq>paq(?:uete)?\.?\s*)?(?:x|por)\s*(?P<n>\d+)"
    r"(?P<unidad>\s*(?:unidades|unidad|unds|und|uds|ud|un)\b\.?)?"
    r"(?!\d)(?!\s*(?:hojas|ml|gr|g|cm|mm|colores|cc|oz|kg|m|mts|metros|pliegos)\b)",
    re.IGNORECASE,
)


def _reemplazo_presentacion(m: re.Match) -> str:
    if not (m.group("paq") or m.group("unidad")):
        return m.group(0)
    return f"{m.group('n')} unidades"


def normalizar_presentacion(nombre: str) -> str:
    return re.sub(r"\s{2,}", " ", _PRESENTACION.sub(_reemplazo_presentacion, nombre)).strip()


def texto_embedding_limpio(nombre: str, marca: str | None, categoria: str | None) -> str:
    return ". ".join(p for p in (nombre, marca, categoria) if p) + "."


# ---------------------------------------------------------------------------
# Construcción de variantes
# ---------------------------------------------------------------------------

def construir_documentos(pares: pd.DataFrame, catalogo: dict[str, dict], canonicas: dict[str, str]) -> dict[str, pd.DataFrame]:
    """Por variante: DataFrame (sku → doc_rerank, doc_embedding)."""
    skus = pares.drop_duplicates("sku")[["sku", "nombre_producto", "marca", "categoria", "precio"]]
    variantes: dict[str, list[dict]] = {v: [] for v in ["V0", "V1", "V2", "V3", "V3b", "V4"]}

    for r in skus.itertuples(index=False):
        fuente = catalogo.get(r.sku) or {
            "nombre": r.nombre_producto, "marca": None if pd.isna(r.marca) else r.marca,
            "categoria": r.categoria, "precio": float(r.precio), "proveedor": r.sku.split("-")[0],
        }
        nombre, marca, cat = fuente["nombre"], fuente.get("marca"), fuente.get("categoria")
        marca_c = normalizar_marca(marca, canonicas)
        cat_c = categoria_canonica(nombre, cat)
        cat_f = concepto_fino(nombre, cat)
        nombre_p = normalizar_presentacion(nombre)

        variantes["V0"].append({"sku": r.sku, "doc_rerank": build_document_text(nombre, cat, marca),
                                "doc_emb": texto_embedding_seed(fuente)})
        variantes["V1"].append({"sku": r.sku, "doc_rerank": build_document_text(nombre, cat, marca_c),
                                "doc_emb": texto_embedding_seed({**fuente, "marca": marca_c})})
        variantes["V2"].append({"sku": r.sku, "doc_rerank": build_document_text(nombre, cat, marca_c),
                                "doc_emb": texto_embedding_limpio(nombre, marca_c, cat)})
        variantes["V3"].append({"sku": r.sku, "doc_rerank": build_document_text(nombre, cat_c, marca_c),
                                "doc_emb": texto_embedding_limpio(nombre, marca_c, cat_c)})
        variantes["V3b"].append({"sku": r.sku, "doc_rerank": build_document_text(nombre, cat_f, marca_c),
                                 "doc_emb": texto_embedding_limpio(nombre, marca_c, cat_f)})
        variantes["V4"].append({"sku": r.sku, "doc_rerank": build_document_text(nombre_p, cat_c, marca_c),
                                "doc_emb": texto_embedding_limpio(nombre_p, marca_c, cat_c)})

    return {v: pd.DataFrame(filas) for v, filas in variantes.items()}


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def metricas_top1(df: pd.DataFrame, col: str) -> dict:
    top1 = df.loc[df.groupby("item_id")[col].idxmax()]
    cubiertos = top1[top1[col] >= TAU]
    return {
        "acc1": top1.es_correcto.mean(),
        "cobertura_tau": len(cubiertos) / len(top1),
        "precision_tau": cubiertos.es_correcto.mean() if len(cubiertos) else float("nan"),
    }


def calcular_scores(pares: pd.DataFrame) -> pd.DataFrame:
    t_inicio = time.monotonic()
    seed = json.loads(CATALOGO_SEED.read_text(encoding="utf-8"))["productos"]
    catalogo = {generar_sku(p["proveedor"], p["nombre"]): p for p in seed}
    encontrados = pares.sku.drop_duplicates().isin(catalogo).sum()
    print(f"SKUs del gold-standard encontrados en el feed original: {encontrados}/{pares.sku.nunique()}")

    canonicas = construir_marcas_canonicas()
    documentos = construir_documentos(pares, catalogo, canonicas)

    base = documentos["V0"].set_index("sku")
    for v, d in documentos.items():
        d = d.set_index("sku")
        print(f"  {v}: docs reranker distintos de V0 = {(d.doc_rerank != base.doc_rerank).sum():>4}   "
              f"docs embedding distintos de V0 = {(d.doc_emb != base.doc_emb).sum():>4}")

    consultas = pares.drop_duplicates("item_id")[["item_id", "descripcion"]]

    # --- Reranker (cache por par único consulta/documento) ---
    reranker = get_reranker()
    if reranker is None:
        raise SystemExit("El reranker no cargó; sin él no hay experimento.")
    pares_unicos: set[tuple[str, str]] = set()
    for d in documentos.values():
        m = pares[["descripcion", "sku"]].merge(d, on="sku")
        pares_unicos.update(zip(m.descripcion, m.doc_rerank))
    lista_pares = sorted(pares_unicos)
    print(f"\nReranker: {len(lista_pares)} pares únicos a puntuar ({reranker.device})...", flush=True)
    rerank_cache: dict[tuple[str, str], float] = {}
    lote = 256
    for i in range(0, len(lista_pares), lote):
        trozo = lista_pares[i:i + lote]
        for par, s in zip(trozo, reranker.score(trozo)):
            rerank_cache[par] = s
        print(f"  {min(i + lote, len(lista_pares))}/{len(lista_pares)} "
              f"({time.monotonic() - t_inicio:.0f}s)", flush=True)

    # --- Embeddings e5 (mismo modelo y prefijos que producción) ---
    from pipeline.stage2_busqueda import _get_model

    modelo = _get_model()
    docs_emb = sorted({t for d in documentos.values() for t in d.doc_emb})
    print(f"\ne5: {len(docs_emb)} documentos únicos + {len(consultas)} consultas...", flush=True)
    vec_docs = modelo.encode([f"passage: {t}" for t in docs_emb], batch_size=32,
                             normalize_embeddings=True, show_progress_bar=True)
    emb_doc = dict(zip(docs_emb, vec_docs))
    vec_q = modelo.encode([f"query: {t}" for t in consultas.descripcion], batch_size=32,
                          normalize_embeddings=True, show_progress_bar=True)
    emb_q = dict(zip(consultas.item_id, vec_q))

    filas = []
    for v, d in documentos.items():
        m = pares[["item_id", "descripcion", "sku", "es_correcto", "rerank_score", "vec_score"]].merge(d, on="sku")
        m["rerank"] = [rerank_cache[(q, doc)] for q, doc in zip(m.descripcion, m.doc_rerank)]
        m["vec"] = [float(np.dot(emb_q[i], emb_doc[doc])) for i, doc in zip(m.item_id, m.doc_emb)]
        m["variante"] = v
        filas.append(m)
    scores = pd.concat(filas, ignore_index=True)

    # --- Sanidad: V0 local debe reproducir el gold-standard ---
    # vec_score=0 en el CSV no es un score real: el candidato entró solo por el
    # canal léxico y el SQL de Stage 2 le pone COALESCE(vec_score, 0).
    v0 = scores[scores.variante == "V0"]
    solo_lex = v0.vec_score == 0
    d_rr = (v0.rerank - v0.rerank_score).abs()
    d_vec = (v0.vec - v0.vec_score).abs()[~solo_lex]
    print("\n=== Sanidad: V0 recalculado vs. scores guardados en el gold-standard ===")
    print(f"  rerank: |diff| media = {d_rr.mean():.5f}  máx = {d_rr.max():.4f}  "
          f"pares con |diff|>0.05: {(d_rr > 0.05).sum()}")
    print(f"  vec:    |diff| media = {d_vec.mean():.5f}  máx = {d_vec.max():.4f}  "
          f"(excluye {solo_lex.sum()} pares con vec_score=0 por entrar solo vía léxico)")

    columnas = ["variante", "item_id", "sku", "es_correcto", "rerank", "vec", "doc_rerank", "doc_emb"]
    scores[columnas].to_csv(SALIDA_SCORES, index=False, encoding="utf-8")
    print(f"\nScores calculados en {(time.monotonic() - t_inicio) / 60:.1f} min")
    return scores[columnas]


def _top1(scores: pd.DataFrame, variante: str) -> pd.DataFrame:
    d = scores[scores.variante == variante]
    return d.loc[d.groupby("item_id").rerank.idxmax()].set_index("item_id")[["rerank", "es_correcto"]]


def intervalos_bootstrap(scores: pd.DataFrame, variante: str) -> dict[str, tuple[float, float]]:
    """IC 95% de la diferencia variante − V0, remuestreando ÍTEMS (no pares):
    los 5 candidatos de un ítem compiten entre sí y no son independientes."""
    base, var = _top1(scores, "V0"), _top1(scores, variante)
    items = base.index.to_numpy()
    rng = np.random.default_rng(SEMILLA)

    def puntos(t: pd.DataFrame, idx: np.ndarray) -> tuple[float, float, float]:
        x = t.loc[idx]
        c = x.rerank >= TAU
        return c.mean(), x.es_correcto[c].mean(), x.es_correcto.mean()

    deltas = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.choice(items, len(items), replace=True)
        deltas.append(np.subtract(puntos(var, idx), puntos(base, idx)))
    lo, hi = np.percentile(np.array(deltas), [2.5, 97.5], axis=0)
    return {"cobertura": (lo[0], hi[0]), "precision": (lo[1], hi[1]), "acc1": (lo[2], hi[2])}


def veredicto(ic_cobertura: tuple[float, float], ic_precision: tuple[float, float]) -> str:
    """Regla de δ/grafo ("se descarta si pierde en ambos ejes") sobre intervalos
    de confianza, no sobre diferencias puntuales: con 542 ítems, un solo ítem
    que cambia mueve la cobertura 0.18 pp."""
    gana_cob, gana_prec = ic_cobertura[0] > 0, ic_precision[0] > 0
    pierde_cob, pierde_prec = ic_cobertura[1] < 0, ic_precision[1] < 0
    if pierde_cob and pierde_prec:
        return "RECHAZA (pierde en ambos ejes)"
    if (gana_cob or gana_prec) and not (pierde_cob or pierde_prec):
        return "CANDIDATA (gana en un eje sin perder en el otro)"
    if pierde_cob or pierde_prec:
        return "NO MEJORA (pierde en un eje, no gana en ninguno)"
    return "NEUTRA (dentro del ruido)"


def resumir(scores: pd.DataFrame) -> None:
    v0 = scores[scores.variante == "V0"]
    top1_base = _top1(scores, "V0")
    resumen = []
    for v, m in scores.groupby("variante", sort=False):
        y = m.es_correcto.to_numpy()
        ahora = _top1(scores, v).es_correcto.reindex(top1_base.index)
        antes = top1_base.es_correcto
        fila = {
            "variante": v,
            "rerank_roc_auc": roc_auc_score(y, m.rerank), "rerank_pr_auc": average_precision_score(y, m.rerank),
            "vec_roc_auc": roc_auc_score(y, m.vec), "vec_pr_auc": average_precision_score(y, m.vec),
            **metricas_top1(m, "rerank"),
            "vec_acc1": metricas_top1(m, "vec")["acc1"],
            "top1_corregidos": int(((antes == 0) & (ahora == 1)).sum()),
            "top1_rotos": int(((antes == 1) & (ahora == 0)).sum()),
        }
        if v != "V0":
            for metrica, (lo, hi) in intervalos_bootstrap(scores, v).items():
                fila[f"ic95_{metrica}_lo"], fila[f"ic95_{metrica}_hi"] = lo, hi
            fila["veredicto"] = veredicto((fila["ic95_cobertura_lo"], fila["ic95_cobertura_hi"]),
                                          (fila["ic95_precision_lo"], fila["ic95_precision_hi"]))
        resumen.append(fila)
    res = pd.DataFrame(resumen)
    res.to_csv(SALIDA_RESUMEN, index=False, encoding="utf-8")

    print(f"\n=== Resultados ({len(v0)} pares, {v0.item_id.nunique()} ítems, pool fijo de 5, τ={TAU}) ===\n")
    print(f"{'var':<5}{'rrk AUC':>9}{'rrk PR':>8}{'vec AUC':>9}{'vec PR':>8}{'acc@1':>8}"
          f"{'cob@τ':>8}{'prec@τ':>8}{'vec@1':>8}{'+corr':>7}{'-rotos':>7}")
    for r in res.itertuples():
        print(f"{r.variante:<5}{r.rerank_roc_auc:>9.3f}{r.rerank_pr_auc:>8.3f}{r.vec_roc_auc:>9.3f}"
              f"{r.vec_pr_auc:>8.3f}{r.acc1:>8.1%}{r.cobertura_tau:>8.1%}{r.precision_tau:>8.1%}"
              f"{r.vec_acc1:>8.1%}{r.top1_corregidos:>7}{r.top1_rotos:>7}")

    print(f"\n=== Compuerta (IC 95%, bootstrap pareado por ítem, {N_BOOTSTRAP} réplicas) ===")
    for r in res.iloc[1:].itertuples():
        print(f"  {r.variante:<4} Δcob@τ [{r.ic95_cobertura_lo:+.1%}, {r.ic95_cobertura_hi:+.1%}]  "
              f"Δprec@τ [{r.ic95_precision_lo:+.1%}, {r.ic95_precision_hi:+.1%}]  "
              f"Δacc@1 [{r.ic95_acc1_lo:+.1%}, {r.ic95_acc1_hi:+.1%}]  → {r.veredicto}")

    print(f"\nScores por par: {SALIDA_SCORES}\nResumen: {SALIDA_RESUMEN}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde-scores", action="store_true",
                    help=f"No recalcula modelos: resume desde {SALIDA_SCORES.name} de una corrida previa")
    args = ap.parse_args()

    if args.desde_scores:
        scores = pd.read_csv(SALIDA_SCORES)
    else:
        pares = pd.read_csv(CSV)
        print(f"Gold-standard: {len(pares)} pares, {pares.item_id.nunique()} ítems, {pares.sku.nunique()} SKUs")
        scores = calcular_scores(pares)
    resumir(scores)


if __name__ == "__main__":
    main()
