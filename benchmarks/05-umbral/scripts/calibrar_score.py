"""Paso 1 — Calibra el score del cross-encoder a probabilidad de acierto.

El ``rerank_score`` de BAAI/bge-reranker-v2-m3 es un score de *ranking* pasado
por sigmoid, no una probabilidad calibrada: se entrena con pérdidas que solo
exigen ordenar (lo correcto por encima de lo incorrecto), sin obligar a que el
valor absoluto corresponda a una frecuencia real de acierto. La evidencia en
estos datos es que todo el universo —aciertos y errores— se apiña entre 0.50 y
0.73, en vez de repartirse por [0,1].

Este script ajusta una regresión isotónica que mapea ``rerank_score`` →
probabilidad empírica de acierto, usando las 2.710 etiquetas del gold-standard.

Dos decisiones metodológicas:

1. **Validación cruzada agrupada por ítem** (``GroupKFold``, 5 folds). Los 5
   candidatos de un mismo ítem no son observaciones independientes (compiten
   entre sí por la misma consulta); si cayeran en folds distintos, el modelo
   vería parte del ítem en entrenamiento y el resto en validación, inflando la
   calidad aparente de la calibración. Agrupar por ``item_id`` evita esa fuga.
2. Las métricas (Brier, ECE) se reportan sobre las predicciones
   *out-of-fold* —nunca sobre los mismos puntos con que se ajustó—, porque
   evaluar una calibración contra sí misma la hace parecer perfecta por
   construcción.

El modelo final que se reporta como tabla de conversión sí se ajusta sobre el
100% de los datos (es el que se desplegaría); las métricas honestas vienen de
la validación cruzada.

Uso:
    python calibration/calibrar_score.py
"""

import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import GroupKFold

BASE = Path(__file__).resolve().parent
CSV = BASE / "gold_standard_final.csv"
FIG_DIR = Path(r"C:\Users\gabri\Documents\Tesis\POC-Tesis\documento_maestro\figuras")
SALIDA_TABLA = BASE / "tabla_calibracion.csv"

N_BINS = 10


def error_calibracion_esperado(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS) -> float:
    """ECE: |confianza predicha − frecuencia observada| promediado, ponderado por bin."""
    bordes = np.linspace(p.min(), p.max(), n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bordes[i], bordes[i + 1]
        m = (p >= lo) & (p <= hi if i == n_bins - 1 else p < hi)
        if m.sum() == 0:
            continue
        ece += (m.sum() / len(p)) * abs(p[m].mean() - y[m].mean())
    return ece


def curva_confiabilidad(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS):
    """Devuelve (confianza media por bin, frecuencia observada por bin, n por bin)."""
    bordes = np.linspace(p.min(), p.max(), n_bins + 1)
    xs, ys, ns = [], [], []
    for i in range(n_bins):
        lo, hi = bordes[i], bordes[i + 1]
        m = (p >= lo) & (p <= hi if i == n_bins - 1 else p < hi)
        if m.sum() < 5:  # bins con muy pocos puntos no dicen nada
            continue
        xs.append(p[m].mean())
        ys.append(y[m].mean())
        ns.append(int(m.sum()))
    return np.array(xs), np.array(ys), ns


def calibrar(x: np.ndarray, y: np.ndarray, grupos: np.ndarray, etiqueta: str):
    """Ajusta isotónica out-of-fold (agrupada) y devuelve (p_oof, modelo_final, métricas)."""
    n_splits = min(5, len(np.unique(grupos)))
    p_oof = np.zeros_like(x, dtype=float)
    gkf = GroupKFold(n_splits=n_splits)
    for tr, te in gkf.split(x, y, groups=grupos):
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(x[tr], y[tr])
        p_oof[te] = iso.predict(x[te])

    iso_final = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso_final.fit(x, y)

    metricas = {
        "brier_crudo": brier_score_loss(y, x),
        "brier_cal": brier_score_loss(y, p_oof),
        "ece_crudo": error_calibracion_esperado(y, x),
        "ece_cal": error_calibracion_esperado(y, p_oof),
    }
    print(f"\n=== Calibración — {etiqueta} (out-of-fold, {n_splits} folds por ítem) ===")
    print(f"  n={len(y)}, tasa base de acierto = {y.mean():.1%}")
    print(f"  Brier  crudo={metricas['brier_crudo']:.4f}  calibrado={metricas['brier_cal']:.4f}")
    print(f"  ECE    crudo={metricas['ece_crudo']:.4f}  calibrado={metricas['ece_cal']:.4f}")
    return p_oof, iso_final, metricas


def main() -> None:
    df = pd.read_csv(CSV)
    df = df[df["rerank_score"].notna()].copy()

    x = df["rerank_score"].to_numpy(dtype=float)
    y = df["es_correcto"].to_numpy(dtype=int)
    grupos = df["item_id"].to_numpy()

    print(f"Dataset: {len(df)} pares, {y.sum()} positivos ({y.mean():.1%}), "
          f"{df['item_id'].nunique()} ítems")
    print(f"Rango del score crudo: [{x.min():.3f}, {x.max():.3f}]  "
          f"(un score calibrado debería usar buena parte de [0,1])")

    # ------------------------------------------------------------------
    # El decisor real de Stage 3 pregunta "¿es correcto el TOP-1?", no
    # "¿es correcto este candidato cualquiera?". La tasa base de las dos
    # preguntas es distinta (47% sobre todos los candidatos vs. la del
    # top-1), así que una calibración ajustada sobre los 2.710 pares
    # subestima sistemáticamente la probabilidad del top-1. Se reportan
    # ambas, y la decisión de τ se toma con la del top-1.
    # ------------------------------------------------------------------
    df_top1 = df[df["rank_rerank"] == 1].copy()
    x1 = df_top1["rerank_score"].to_numpy(dtype=float)
    y1 = df_top1["es_correcto"].to_numpy(dtype=int)
    g1 = df_top1["item_id"].to_numpy()
    print(f"\nSubconjunto top-1 (el que realmente decide τ): {len(df_top1)} ítems, "
          f"tasa base de acierto = {y1.mean():.1%}")

    _, iso_top1, _ = calibrar(x1, y1, g1, "solo TOP-1 (decisor real de τ)")

    # --- Calibración sobre todos los candidatos (referencia) ---
    p_oof, iso_final, met = calibrar(x, y, grupos, "TODOS los candidatos (referencia)")
    ece_crudo, ece_cal = met["ece_crudo"], met["ece_cal"]

    print("\n=== Tabla de conversión (todos los candidatos): score → P(correcto) ===")
    scores_ref = [0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.73]
    filas_tabla = []
    for s in scores_ref:
        p = float(iso_final.predict([s])[0])
        n_ge = int((x >= s).sum())
        print(f"  score {s:.2f}  →  P(correcto) = {p:6.1%}   "
              f"(candidatos con score ≥ {s:.2f}: {n_ge})")
        filas_tabla.append({"score_crudo": s, "prob_calibrada": round(p, 4), "n_candidatos_ge": n_ge})
    pd.DataFrame(filas_tabla).to_csv(SALIDA_TABLA, index=False)

    # --- τ reexpresado sobre el decisor real (top-1) ---
    print("\n=== τ reexpresado como decisión explícita de confianza (sobre TOP-1) ===")
    rejilla = np.linspace(x1.min(), x1.max(), 2000)
    probs = iso_top1.predict(rejilla)
    for objetivo in [0.75, 0.80, 0.85, 0.90, 0.95]:
        idx = np.where(probs >= objetivo)[0]
        if len(idx) == 0:
            print(f"  P ≥ {objetivo:.0%}  →  inalcanzable "
                  f"(prob. máxima del modelo: {probs.max():.1%})")
            continue
        s_min = rejilla[idx[0]]
        n_cubiertos = int((x1 >= s_min).sum())
        precision_real = y1[x1 >= s_min].mean() if n_cubiertos else float("nan")
        print(f"  P ≥ {objetivo:.0%}  →  score ≥ {s_min:.3f}   "
              f"(auto-resolvería {n_cubiertos}/{len(x1)} ítems = {n_cubiertos/len(x1):.1%}, "
              f"precisión real de ese conjunto: {precision_real:.1%})")

    p_tau_58 = float(iso_top1.predict([0.58])[0])
    n58 = int((x1 >= 0.58).sum())
    prec58 = y1[x1 >= 0.58].mean()
    print(f"\n  τ vigente = 0.58:")
    print(f"    P(top-1 correcto | score ≈ 0.58) = {p_tau_58:.1%}  ← el ítem marginal")
    print(f"    precisión del conjunto completo con score ≥ 0.58 = {prec58:.1%} "
          f"({n58}/{len(x1)} ítems)")

    # --- Diagrama de confiabilidad ---
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))

    for ax, (p_plot, titulo, ece_v) in zip(
        axes,
        [(x, "Score crudo del cross-encoder", ece_crudo),
         (p_oof, "Score calibrado (isotónica, out-of-fold)", ece_cal)],
    ):
        xs, ys, ns = curva_confiabilidad(y, p_plot)
        ax.plot([0, 1], [0, 1], "--", color="gray", linewidth=1, label="Calibración perfecta")
        ax.plot(xs, ys, "o-", color="#1f77b4", linewidth=2, markersize=6, label="Observado")
        ax.set_xlabel("Probabilidad predicha")
        ax.set_ylabel("Frecuencia observada de acierto")
        ax.set_title(f"{titulo}\nECE = {ece_v:.3f}", fontsize=10)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="upper left")

    fig.tight_layout()
    destino = FIG_DIR / "diagrama_confiabilidad.png"
    fig.savefig(destino, dpi=160)
    print(f"\nFigura guardada: {destino}")
    print(f"Tabla guardada:  {SALIDA_TABLA}")


if __name__ == "__main__":
    main()
