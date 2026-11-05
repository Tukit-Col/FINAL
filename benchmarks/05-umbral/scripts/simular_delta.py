"""Paso 3 — Re-simula la clasificación de Stage 3 bajo distintas definiciones
de δ y mide cobertura vs. precisión sobre el gold-standard completo.

Configuraciones comparadas:

    A. Vigente          τ + δ por gap contra el rank-2 (lo que corre hoy)
    B. Solo τ           sin δ: si el top-1 supera τ, se auto-resuelve
    C. τ + familias H1  δ redefinido: ¿hay más de una familia de producto por
                        encima de τ? (equivalencia por nombre sin marca)
    D. τ + familias H2  igual, pero con equivalencia condicionada a la consulta

Métricas (sobre los 542 ítems, no solo los 394 con match — auto-resolver un
ítem que no tenía match en catálogo es un error y debe contarse como tal):

    cobertura  % de ítems que el sistema resuelve solo (RESUELTO_AUTO)
    precisión  de esos, % en que el producto elegido era realmente correcto
    escalados  % que van a un humano (AMBIGUO)
    descartados % clasificados SIN_MATCH

Uso:
    python calibration/simular_delta.py
"""

import sys
import unicodedata
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE.parent))

from medir_equivalencia import (  # noqa: E402
    UMBRAL_SIMILARITY,
    equivalentes_por_consulta,
    equivalentes_por_grafo,
    normalizar,
    similitudes_en_lote,
    tokens_consulta,
)

# Política ganadora medida en medir_equivalencia.py (menos falsos
# equivalentes: 14.8% sin restringir, vs. 22.5% de "defer").
POLITICA_H3 = "block"

CSV = BASE / "gold_standard_final.csv"


def familias(candidatos: list[dict], modo: str, sim_lookup: dict) -> int:
    """Cuenta familias de producto entre los candidatos (componentes conexas
    de la relación de equivalencia)."""
    n = len(candidatos)
    padre = list(range(n))

    def find(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            padre[ri] = rj

    toks = tokens_consulta(candidatos[0]["descripcion"]) if modo in ("h2", "h3") else None
    for i in range(n):
        for j in range(i + 1, n):
            a, b = candidatos[i], candidatos[j]
            if modo == "h1":
                eq = sim_lookup.get((a["sku"], b["sku"]), 0.0) >= UMBRAL_SIMILARITY
            elif modo == "h3":
                eq = equivalentes_por_grafo(
                    a["nombre_producto"], b["nombre_producto"],
                    a["nombre_norm"], b["nombre_norm"], toks, POLITICA_H3,
                )
            else:
                eq = equivalentes_por_consulta(a["nombre_norm"], b["nombre_norm"], toks)
            if eq:
                union(i, j)
    return len({find(i) for i in range(n)})


def clasificar(cands_sobre_tau: list[dict], todos: list[dict], config: str,
               delta: float, sim_lookup: dict) -> str:
    if not cands_sobre_tau:
        return "SIN_MATCH"
    if config == "A":
        top1 = todos[0]["rerank_score"]
        top2 = todos[1]["rerank_score"] if len(todos) > 1 else float("-inf")
        return "AMBIGUO" if (top1 - top2) < delta else "RESUELTO_AUTO"
    if config == "B":
        return "RESUELTO_AUTO"
    modo = {"C": "h1", "D": "h2", "E": "h3"}[config]
    return "RESUELTO_AUTO" if familias(cands_sobre_tau, modo, sim_lookup) == 1 else "AMBIGUO"


def main() -> None:
    df = pd.read_csv(CSV)
    df["marca"] = df["marca"].fillna("")
    df["nombre_norm"] = [normalizar(n, m) for n, m in zip(df["nombre_producto"], df["marca"])]

    # Pre-calcula todas las similitudes H1 de una vez (una sola ida a Postgres).
    import os

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(BASE.parent / ".env")
    pares_sku, pares_txt = [], []
    for _, g in df.groupby("item_id"):
        filas = g.to_dict("records")
        for i in range(len(filas)):
            for j in range(i + 1, len(filas)):
                pares_sku.append((filas[i]["sku"], filas[j]["sku"]))
                pares_txt.append((filas[i]["nombre_norm"], filas[j]["nombre_norm"]))
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        sims = similitudes_en_lote(conn, pares_txt)
    finally:
        conn.close()
    sim_lookup = {}
    for (a, b), s in zip(pares_sku, sims):
        sim_lookup[(a, b)] = s
        sim_lookup[(b, a)] = s

    items = [g.sort_values("rank_rerank").to_dict("records") for _, g in df.groupby("item_id")]
    print(f"Simulando sobre {len(items)} ítems "
          f"({sum(1 for it in items if it[0]['sin_match'] == 0)} con match real)\n")

    configs = [
        ("A", 0.58, 0.05, "Vigente: τ=0.58 + δ=0.05 (gap vs rank-2)"),
        ("B", 0.58, 0.00, "Solo τ=0.58, sin δ"),
        ("B", 0.630, 0.00, "Solo τ=0.630  (P≥75% calibrada)"),
        ("B", 0.716, 0.00, "Solo τ=0.716  (P≥85% calibrada)"),
        ("C", 0.58, 0.00, "τ=0.58 + familias H1 (nombre sin marca)"),
        ("C", 0.630, 0.00, "τ=0.630 + familias H1"),
        ("D", 0.58, 0.00, "τ=0.58 + familias H2 (condicionada a consulta)"),
        ("D", 0.630, 0.00, "τ=0.630 + familias H2"),
        ("E", 0.58, 0.00, "τ=0.58 + familias H3 (H2 + grafo de sustituibilidad)"),
        ("E", 0.630, 0.00, "τ=0.630 + familias H3"),
    ]

    print(f"  {'configuración':<48} | {'cobertura':>9} | {'precisión':>9} | "
          f"{'escala':>7} | {'descarta':>8}")
    print("  " + "-" * 92)
    for config, tau, delta, etiqueta in configs:
        auto = correctos = ambiguo = sinmatch = 0
        for cands in items:
            sobre_tau = [c for c in cands if c["rerank_score"] >= tau]
            estado = clasificar(sobre_tau, cands, config, delta, sim_lookup)
            if estado == "RESUELTO_AUTO":
                auto += 1
                correctos += int(cands[0]["es_correcto"])
            elif estado == "AMBIGUO":
                ambiguo += 1
            else:
                sinmatch += 1
        n = len(items)
        prec = f"{correctos/auto:.1%}" if auto else "n/a"
        print(f"  {etiqueta:<48} | {auto/n:>8.1%} | {prec:>9} | "
              f"{ambiguo/n:>6.1%} | {sinmatch/n:>7.1%}")

    print("\n  cobertura = ítems resueltos sin humano | precisión = de esos, cuántos acertaron")
    print("  (sobre los 542 ítems: auto-resolver uno sin match en catálogo cuenta como error)")

    # ------------------------------------------------------------------
    # ¿De dónde viene el error que queda? Si la mayoría son ítems que NO
    # tenían match en el catálogo, ningún mecanismo de ambigüedad puede
    # arreglarlo: no hay un segundo candidato con el cual contrastar, el
    # problema es de cobertura de catálogo, no de desambiguación.
    # ------------------------------------------------------------------
    print("\n=== Descomposición del error en la mejor configuración (solo τ=0.630) ===")
    err_sin_match = err_con_match = aciertos = 0
    for cands in items:
        sobre_tau = [c for c in cands if c["rerank_score"] >= 0.630]
        if not sobre_tau:
            continue
        if cands[0]["es_correcto"]:
            aciertos += 1
        elif cands[0]["sin_match"]:
            err_sin_match += 1
        else:
            err_con_match += 1
    total_auto = aciertos + err_sin_match + err_con_match
    print(f"  auto-resueltos: {total_auto}")
    print(f"    ✔ aciertos:                              {aciertos:>3} ({aciertos/total_auto:.1%})")
    print(f"    ✘ ítem SIN match en catálogo:            {err_sin_match:>3} "
          f"({err_sin_match/total_auto:.1%})  → hueco de catálogo, δ no puede ayudar")
    print(f"    ✘ ítem CON match pero top-1 equivocado:  {err_con_match:>3} "
          f"({err_con_match/total_auto:.1%})  → único error que un δ podría atrapar")


if __name__ == "__main__":
    main()
