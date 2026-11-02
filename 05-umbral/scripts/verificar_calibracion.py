"""Recalcula desde los datos crudos las cifras de calibracion de tau/delta.

Fuente: `gold_standard_final.csv` de `Tukit-Col/tukit-mvp-pipeline`
(calibration/, 2.710 pares item-candidato, 542 items anotados a mano) y
`verificador_seleccion_resultados.csv` (salidas guardadas del verificador LLM).
Todo se recalcula sin red ni base de datos; lo que necesita Postgres (similitud
pg_trgm de la hipotesis H1) no se recalcula aqui.

    python verificar_calibracion.py   -> ../resultados/verificacion_calibracion.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold

AQUI = Path(__file__).resolve().parent
DATOS = AQUI.parent / "datos"
SALIDA = AQUI.parent / "resultados" / "verificacion_calibracion.json"


def ece(y, p, n_bins=10):
    """Mismo ECE que calibrar_score.py: bins equiespaciados entre min(p) y max(p)."""
    bordes = np.linspace(p.min(), p.max(), n_bins + 1)
    total = 0.0
    for i in range(n_bins):
        lo, hi = bordes[i], bordes[i + 1]
        m = (p >= lo) & (p <= hi if i == n_bins - 1 else p < hi)
        if m.sum():
            total += (m.sum() / len(p)) * abs(p[m].mean() - y[m].mean())
    return float(total)


def isotonica_oof(x, y, grupos):
    p = np.zeros_like(x, dtype=float)
    for tr, te in GroupKFold(n_splits=5).split(x, y, groups=grupos):
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(x[tr], y[tr])
        p[te] = iso.predict(x[te])
    final = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(x, y)
    return p, final


def main() -> int:
    df = pd.read_csv(DATOS / "gold_standard_final.csv")
    out: dict = {}

    # --- 1. el conjunto de datos
    items = df.groupby("item_id")
    con_match = items["es_correcto"].max()
    out["dataset"] = {
        "pares": int(len(df)),
        "items": int(df["item_id"].nunique()),
        "positivos": int(df["es_correcto"].sum()),
        "negativos": int((df["es_correcto"] == 0).sum()),
        "pct_positivos": round(100 * df["es_correcto"].mean(), 2),
        "pct_negativos": round(100 * (df["es_correcto"] == 0).mean(), 2),
        "items_con_al_menos_un_correcto": int(con_match.sum()),
        "items_sin_correcto_en_top5": int((con_match == 0).sum()),
        "pct_items_sin_correcto": round(100 * (con_match == 0).mean(), 2),
        "skus_correctos_por_item_etiquetado": round(
            float(items["es_correcto"].sum()[con_match == 1].mean()), 3
        ),
        "rango_rerank": [float(df["rerank_score"].min()), float(df["rerank_score"].max())],
        "items_top1_distinto_rrf_vs_rerank": int(
            sum(
                g.loc[g["rank_rrf"] == 1, "sku"].iloc[0] != g.loc[g["rank_rerank"] == 1, "sku"].iloc[0]
                for _, g in items
            )
        ),
    }

    # --- 2. poder discriminativo por senal (pares) y Precision@1 (394 items con match)
    df["max_vec_lex"] = df[["vec_score", "lex_score"]].max(axis=1)
    y = df["es_correcto"].to_numpy()
    senales = {}
    etiquetados = df[df["item_id"].isin(con_match[con_match == 1].index)]
    for s in ["rrf_score", "lex_score", "vec_score", "max_vec_lex", "rerank_score"]:
        x = df[s].to_numpy(dtype=float)
        top = etiquetados.sort_values(s, ascending=False, kind="stable").groupby("item_id").head(1)
        senales[s] = {
            "roc_auc": round(float(roc_auc_score(y, x)), 4),
            "pr_auc": round(float(average_precision_score(y, x)), 4),
            "precision_at_1_por_valor": round(100 * float(top["es_correcto"].mean()), 2),
        }
    # Precision@1 segun el orden con que el sistema entrega los candidatos.
    for col in ["rank_rrf", "rank_rerank"]:
        top = etiquetados[etiquetados[col] == 1]
        senales[f"orden_{col}"] = {"precision_at_1": round(100 * float(top["es_correcto"].mean()), 2)}
    # El documento divide por los 394 items con sin_match=0 (2 de ellos no tienen ningun SKU correcto).
    sin_flag = df[df["item_id"].isin(df.groupby("item_id")["sin_match"].max().pipe(lambda s: s[s == 0]).index)]
    for s in ["rrf_score", "max_vec_lex", "rerank_score"]:
        top = sin_flag.sort_values(s, ascending=False, kind="stable").groupby("item_id").head(1)
        senales[s]["precision_at_1_sobre_394"] = round(100 * float(top["es_correcto"].mean()), 2)
    out["senales"] = senales

    # --- 3. percentiles de rerank_score por clase y umbrales optimos
    pct = {}
    for nombre, m in [("correctos", df["es_correcto"] == 1), ("incorrectos", df["es_correcto"] == 0)]:
        v = df.loc[m, "rerank_score"].to_numpy()
        pct[nombre] = {f"p{q}": round(float(np.percentile(v, q)), 3) for q in (10, 25, 50, 75, 90)}
        pct[nombre]["n"] = int(m.sum())
    out["percentiles_rerank"] = pct
    x = df["rerank_score"].to_numpy(dtype=float)
    fpr, tpr, thr = roc_curve(y, x)
    j = int(np.argmax(tpr - fpr))
    cortes = np.unique(x)
    f1s = []
    for t in cortes:
        pred = x >= t
        tp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        fn = int((~pred & (y == 1)).sum())
        f1s.append(2 * tp / max(1, 2 * tp + fp + fn))
    k = int(np.argmax(f1s))
    out["umbrales_rerank"] = {
        "youden_tau": round(float(thr[j]), 4),
        "youden_J": round(float(tpr[j] - fpr[j]), 4),
        "f1_max_tau": round(float(cortes[k]), 4),
        "f1_max": round(float(f1s[k]), 4),
    }

    # --- 4. items en el orden de produccion (rerank) y barrido de delta (394 con match)
    ordenados = [g.sort_values("rank_rerank").to_dict("records") for _, g in items]
    barrido = []
    gaps, ok1 = [], []
    for c in ordenados:
        if c[0]["sin_match"]:
            continue
        gaps.append(c[0]["rerank_score"] - (c[1]["rerank_score"] if len(c) > 1 else 0.0))
        ok1.append(int(c[0]["es_correcto"]))
    gaps, ok1 = np.array(gaps), np.array(ok1)
    for d in (0.0, 0.005, 0.01, 0.02, 0.05):
        m = gaps >= d if d > 0 else gaps > 0
        barrido.append(
            {
                "delta": d,
                "cobertura_pct": round(100 * float(m.mean()), 2),
                "precision_top1_pct": round(100 * float(ok1[m].mean()), 2) if m.any() else None,
                "cobertura_pct_con_mayor_o_igual": round(100 * float((gaps >= d).mean()), 2),
                "precision_con_mayor_o_igual": round(100 * float(ok1[gaps >= d].mean()), 2),
            }
        )
    out["delta_barrido_394"] = barrido
    out["gap_como_senal_roc_auc_394"] = round(float(roc_auc_score(ok1, gaps)), 4)
    out["gap_medio_top1_correcto"] = round(float(gaps[ok1 == 1].mean()), 4)
    out["gap_medio_top1_incorrecto"] = round(float(gaps[ok1 == 0].mean()), 4)

    # El barrido publicado se reproduce exacto con el orden del RRF (el del pool
    # de calibracion), no con el orden del reranker que usa produccion.
    gaps_rrf, ok_rrf = [], []
    for _, g in items:
        c = g.sort_values("rank_rrf").to_dict("records")
        if c[0]["sin_match"]:
            continue
        gaps_rrf.append(c[0]["rerank_score"] - c[1]["rerank_score"])
        ok_rrf.append(int(c[0]["es_correcto"]))
    gaps_rrf, ok_rrf = np.array(gaps_rrf), np.array(ok_rrf)
    out["delta_barrido_394_orden_rrf"] = [
        {
            "delta": d,
            "cobertura_pct": round(100 * float((gaps_rrf >= d).mean()), 2),
            "precision_top1_pct": round(100 * float(ok_rrf[gaps_rrf >= d].mean()), 2),
        }
        for d in (0.0, 0.005, 0.01, 0.02, 0.05)
    ]
    out["gap_como_senal_roc_auc_394_orden_rrf"] = round(float(roc_auc_score(ok_rrf, gaps_rrf)), 4)
    out["gap_medio_orden_rrf"] = {
        "top1_correcto": round(float(gaps_rrf[ok_rrf == 1].mean()), 4),
        "top1_incorrecto": round(float(gaps_rrf[ok_rrf == 0].mean()), 4),
    }

    # --- 5. calibracion isotonica (out-of-fold, GroupKFold 5 por item)
    calib = {}
    top1 = df[df["rank_rerank"] == 1]
    for nombre, sub in [("top1", top1), ("todos", df)]:
        xs = sub["rerank_score"].to_numpy(dtype=float)
        ys = sub["es_correcto"].to_numpy(dtype=int)
        p, final = isotonica_oof(xs, ys, sub["item_id"].to_numpy())
        calib[nombre] = {
            "n": int(len(sub)),
            "tasa_base_pct": round(100 * ys.mean(), 2),
            "brier_crudo": round(float(brier_score_loss(ys, xs)), 4),
            "brier_calibrado": round(float(brier_score_loss(ys, p)), 4),
            "ece_crudo": round(ece(ys, xs), 4),
            "ece_calibrado": round(ece(ys, p), 4),
        }
        if nombre == "top1":
            iso_top1 = final
    out["calibracion"] = calib
    x1 = top1["rerank_score"].to_numpy(dtype=float)
    y1 = top1["es_correcto"].to_numpy(dtype=int)
    out["prob_calibrada_en_0_58"] = round(float(iso_top1.predict([0.58])[0]), 4)
    tabla_tau = []
    rejilla = np.unique(x1)
    for conf in (0.75, 0.80, 0.85):
        ok = [t for t in rejilla if iso_top1.predict([t])[0] >= conf]
        t = float(min(ok)) if ok else None
        sel = x1 >= t if t is not None else np.zeros_like(x1, dtype=bool)
        tabla_tau.append(
            {
                "confianza": conf,
                "score_crudo_equivalente": round(t, 4) if t is not None else None,
                "items_auto": int(sel.sum()),
                "pct_items": round(100 * sel.mean(), 2),
                "precision_pct": round(100 * float(y1[sel].mean()), 2) if sel.any() else None,
            }
        )
    out["tau_como_confianza"] = tabla_tau
    sel = x1 >= 0.58
    out["precision_conjunto_tau_0_58"] = {"items": int(sel.sum()), "precision_pct": round(100 * float(y1[sel].mean()), 2)}

    # --- 6. simulacion end-to-end (542 items): configuraciones sin base de datos
    sim = []
    for etiqueta, tau, delta in [
        ("tau=0.58 + delta=0.05 (gap vs rank-2)", 0.58, 0.05),
        ("solo tau=0.58", 0.58, None),
        ("solo tau=0.630", 0.630, None),
        ("solo tau=0.716", 0.716, None),
    ]:
        auto = correctos = ambiguo = 0
        for c in ordenados:
            if c[0]["rerank_score"] < tau:
                continue
            if delta is not None:
                top2 = c[1]["rerank_score"] if len(c) > 1 else float("-inf")
                if c[0]["rerank_score"] - top2 < delta:
                    ambiguo += 1
                    continue
            auto += 1
            correctos += int(c[0]["es_correcto"])
        n = len(ordenados)
        sim.append(
            {
                "configuracion": etiqueta,
                "cobertura_pct": round(100 * auto / n, 2),
                "precision_pct": round(100 * correctos / auto, 2) if auto else None,
                "escalados_pct": round(100 * ambiguo / n, 2),
                "auto": auto,
                "correctos": correctos,
            }
        )
    out["simulacion_542"] = sim
    a = s_sin = s_con = 0
    for c in ordenados:
        if c[0]["rerank_score"] < 0.630:
            continue
        if c[0]["es_correcto"]:
            a += 1
        elif c[0]["sin_match"]:
            s_sin += 1
        else:
            s_con += 1
    out["descomposicion_error_tau_0_630"] = {"aciertos": a, "errores_sin_match": s_sin, "errores_con_match": s_con}

    # --- 7. verificador LLM de seleccion (salidas guardadas)
    v = pd.read_csv(DATOS / "verificador_seleccion_resultados.csv")
    # Un lote fallido deja letra_elegida="ERROR" (14 filas); raw_error solo guarda 10 de ellos.
    validos = v[v["letra_elegida"].astype(str).str.upper() != "ERROR"]
    con = validos[validos["hay_correcto_en_pool"].astype(str) == "True"]
    sin = validos[validos["hay_correcto_en_pool"].astype(str) != "True"]
    ninguno_con = con["letra_elegida"].astype(str).str.upper().isin(["NINGUNO", "N", "NONE", "NAN", ""]) | con[
        "sku_elegido"
    ].isna()
    acierto_con = (~ninguno_con) & (con["es_correcto_elegido"].astype(str) == "True")
    elige_mal_con = (~ninguno_con) & (con["es_correcto_elegido"].astype(str) != "True")
    ninguno_sin = sin["letra_elegida"].astype(str).str.upper().isin(["NINGUNO", "N", "NONE", "NAN", ""]) | sin[
        "sku_elegido"
    ].isna()
    total = len(v)
    resueltos = int(acierto_con.sum() + elige_mal_con.sum() + (~ninguno_sin).sum())
    out["verificador_seleccion"] = {
        "filas": int(total),
        "validos": int(len(validos)),
        "fallos_llamada": int(total - len(validos)),
        "con_correcto_en_pool": int(len(con)),
        "acierto": int(acierto_con.sum()),
        "elige_mal": int(elige_mal_con.sum()),
        "ninguno_de_mas": int(ninguno_con.sum()),
        "sin_correcto_en_pool": int(len(sin)),
        "ninguno_bien": int(ninguno_sin.sum()),
        "fuerza_eleccion": int((~ninguno_sin).sum()),
        "precision_sobre_validos_resueltos_pct": round(
            100 * float(acierto_con.sum()) / max(1, resueltos), 2
        ),
        "cobertura_sobre_validos_pct": round(100 * resueltos / max(1, len(validos)), 2),
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
