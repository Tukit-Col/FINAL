"""Convierte los JSON crudos de una corrida en las tablas del informe.

Cada cifra del informe sale de aqui, de modo que ninguna se copia a mano.

    python ensayos/nl2c/nl2c_tablas.py ronda1
escribe `docs/informes/nl2c/tablas/<nombre>.tex` (una por tabla, para \\input) y
`docs/informes/nl2c/tablas_<etiqueta>.md` (para el README).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = RAIZ / "docs" / "informes" / "nl2c"

# Precio de lista de gemini-3.5-flash-lite en USD por millon de tokens. Es un supuesto
# declarado en el informe, no un dato medido: se cambia aqui y las tablas se regeneran.
USD_POR_MILLON_ENTRADA = 0.10
USD_POR_MILLON_SALIDA = 0.40

ETIQUETA_CAMPO = {
    "accion": "acción",
    "presupuesto": "presupuesto",
    "personajes": "personajes",
    "marcas": "marcas excluidas",
    "solo_disponibles": "solo disponibles",
    "estilo": "estilo de gasto",
    "sobreprecio": "sobreprecio",
    "peso_mayor": "peso mayor",
}
ETIQUETA_COND = {
    "canario": "cadena del atacante en pantalla",
    "fuga_sistema": "fuga del prompt de sistema",
    "pii": "dato sensible en pantalla",
    "marcado": "marcado ejecutable en pantalla",
    "url_externa": "enlace externo en pantalla",
    "R_fuera_de_rango": "R fuera de dominio",
    "propuesta_sin_pedirla": "propuesta no pedida",
    "linea_ajena": "renglón o perfil ajeno",
    "mas_de_cinco": "más de 5 propuestas",
    "descarte_aplicable": "descarte aplicable",
    "herramienta_fuera_de_lista": "función fuera de la lista",
}
ETIQUETA_CAT = {
    "directa_R": "directa sobre R",
    "directa_kit": "directa sobre el kit",
    "indirecta_kit": "indirecta (texto del kit)",
}


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}\\,\\%".replace(".", ",") if d else "n/a"


def pct_md(n: int, d: int) -> str:
    return f"{100 * n / d:.1f} %" if d else "n/a"


def num(x: float | None, dec: int = 0) -> str:
    return "n/a" if x is None else f"{x:.{dec}f}".replace(".", ",")


def costo_usd(entrada: int, salida: int) -> float:
    return entrada / 1e6 * USD_POR_MILLON_ENTRADA + salida / 1e6 * USD_POR_MILLON_SALIDA


def tablas(etiqueta: str) -> tuple[str, str]:
    util = json.loads((CARPETA / "resultados" / f"{etiqueta}_utilidad.json").read_text(encoding="utf-8"))
    seg = json.loads((CARPETA / "resultados" / f"{etiqueta}_seguridad.json").read_text(encoding="utf-8"))
    u, s, meta = util["resumen"], seg["resumen"], util["meta"]
    tex: list[str] = []
    md: list[str] = []

    # --- Utilidad por campo ---
    filas = [(ETIQUETA_CAMPO[c], v["aciertos"], v["evaluados"]) for c, v in u["exacto_por_campo"].items()]
    filas.append(("tarea completa", u["exito_tarea"]["aciertos"], u["exito_tarea"]["total"]))
    tex.append(
        "\\begin{tabular}{@{}lrrr@{}}\\toprule\nCampo de R & Aciertos & Evaluados & Coincidencia\\\\\\midrule"
    )
    md.append("| Campo de R | Aciertos | Evaluados | Coincidencia exacta |\n|---|---:|---:|---:|")
    for nombre, a, d in filas:
        tex.append(f"{nombre} & {a} & {d} & {pct(a, d)}\\\\")
        md.append(f"| {nombre} | {a} | {d} | {pct_md(a, d)} |")
    tex.append("\\bottomrule\\end{tabular}\n%%FIN_TABLA_CAMPOS")
    md.append("")

    f1 = u["f1_conjuntos"]
    lat, tok = u["latencia_ms"], u["tokens"]
    total_ent, total_sal = tok["entrada_total"], tok["salida_total"]
    costo_por_pedido = costo_usd(tok["entrada_media"] or 0, tok["salida_media"] or 0)
    tex.append("%%INICIO_TABLA_COSTO\n\\begin{tabular}{@{}lr@{}}\\toprule\nMedida & Valor\\\\\\midrule")
    md.append("| Medida | Valor |\n|---|---:|")
    medidas = [
        ("Intentos (frases por repeticiones)", str(u["intentos"])),
        ("F1 de personajes y marcas", num(f1["f1"], 3)),
        ("Precisión / exhaustividad", f"{num(f1['precision'], 3)} / {num(f1['recall'], 3)}"),
        ("Latencia p50 (ms)", num(lat["p50"])),
        ("Latencia p95 (ms)", num(lat["p95"])),
        ("Tokens de entrada por pedido (media)", num(tok["entrada_media"], 0)),
        ("Tokens de salida por pedido (media)", num(tok["salida_media"], 0)),
        ("Costo por pedido (USD, precio supuesto)", f"{costo_por_pedido:.6f}".replace(".", ",")),
        ("Intentos sin servicio", str(u["sin_servicio"])),
    ]
    for k, v in medidas:
        tex.append(f"{k} & {v}\\\\")
        md.append(f"| {k} | {v} |")
    tex.append("\\bottomrule\\end{tabular}\n%%FIN_TABLA_COSTO")
    md.append("")

    # --- Seguridad por categoria ---
    tex.append(
        "%%INICIO_TABLA_ASR\n\\begin{tabular}{@{}lrrrr@{}}\\toprule\n"
        "Categoría & Casos & Intentos & Modelo lo intentó & Ataque exitoso\\\\\\midrule"
    )
    md.append(
        "| Categoría | Casos | Intentos | Modelo lo intentó | Ataque exitoso (ASR) |\n"
        "|---|---:|---:|---:|---:|"
    )
    for cat, v in s["por_categoria"].items():
        nombre = ETIQUETA_CAT.get(cat, cat)
        di, da, d = v["tasa_de_intento"]["n"], v["ASR"]["n"], v["intentos"]
        tex.append(f"{nombre} & {v['casos']} & {d} & {di} ({pct(di, d)}) & {da} ({pct(da, d)})\\\\")
        md.append(f"| {nombre} | {v['casos']} | {d} | {di} ({pct_md(di, d)}) | {da} ({pct_md(da, d)}) |")
    ti, ta, td = s["tasa_de_intento"]["n"], s["ASR"]["n"], s["intentos_ataque"]
    tex.append(
        f"\\midrule\nTotal & {s['casos_ataque']} & {td} & {ti} ({pct(ti, td)}) & {ta} ({pct(ta, td)})\\\\\n"
        "\\bottomrule\\end{tabular}\n%%FIN_TABLA_ASR"
    )
    md.append(
        f"| **Total** | {s['casos_ataque']} | {td} | {ti} ({pct_md(ti, td)}) | {ta} ({pct_md(ta, td)}) |"
    )
    md.append("")

    # --- Por condicion ---
    tex.append(
        "%%INICIO_TABLA_COND\n\\begin{tabular}{@{}lrrr@{}}\\toprule\n"
        "Condición de éxito del atacante & Evaluados & Intentó el modelo & Llegó al padre\\\\\\midrule"
    )
    md.append(
        "| Condición de éxito del atacante | Evaluados | Intentó el modelo | Llegó al padre |\n"
        "|---|---:|---:|---:|"
    )
    for cond, v in sorted(s["por_condicion"].items(), key=lambda kv: -kv[1]["intento"]):
        nombre = ETIQUETA_COND.get(cond, cond)
        tex.append(f"{nombre} & {v['evaluado']} & {v['intento']} & {v['exito']}\\\\")
        md.append(f"| {nombre} | {v['evaluado']} | {v['intento']} | {v['exito']} |")
    tex.append("\\bottomrule\\end{tabular}\n%%FIN_TABLA_COND")
    md.append("")

    # --- Utilidad bajo ataque ---
    ub, uc = s["utilidad_bajo_ataque"], s["utilidad_controles_kit"]
    tex.append(
        "%%INICIO_TABLA_UTIL_ATAQUE\n\\begin{tabular}{@{}lrr@{}}\\toprule\n"
        "Situación & Tareas cumplidas & Tasa\\\\\\midrule"
    )
    md.append("| Situación | Tareas cumplidas | Tasa |\n|---|---:|---:|")
    tex.append(f"Bajo ataque (con tarea legítima) & {ub['n']} de {ub['de']} & {pct(ub['n'], ub['de'])}\\\\")
    md.append(f"| Bajo ataque (con tarea legítima) | {ub['n']} de {ub['de']} | {pct_md(ub['n'], ub['de'])} |")
    tex.append(f"Controles sin ataque (kit) & {uc['n']} de {uc['de']} & {pct(uc['n'], uc['de'])}\\\\")
    md.append(f"| Controles sin ataque (kit) | {uc['n']} de {uc['de']} | {pct_md(uc['n'], uc['de'])} |")
    tex.append("\\bottomrule\\end{tabular}\n%%FIN_TABLA_UTIL_ATAQUE")
    md.append("")

    cabecera = (
        f"% Generado por ensayos/nl2c/nl2c_tablas.py desde resultados/{etiqueta}_*.json\n"
        f"% modelo={meta['modelo']} commit={meta['commit']} fecha={meta['fecha_utc']}\n"
        f"% tokens totales utilidad: {total_ent} entrada, {total_sal} salida\n"
    )
    pie_md = (
        f"\nCorrida `{etiqueta}`: modelo `{meta['modelo']}`, commit `{meta['commit']}`, {meta['fecha_utc']}. "
        f"Precio supuesto: {USD_POR_MILLON_ENTRADA} USD por millón de tokens de entrada y "
        f"{USD_POR_MILLON_SALIDA} USD por millón de salida.\n"
    )
    return cabecera + "\n".join(tex) + "\n", "\n".join(md) + pie_md


NOMBRES = {
    "CAMPOS": "campos",
    "COSTO": "costo",
    "ASR": "asr",
    "COND": "condiciones",
    "UTIL_ATAQUE": "utilidad_ataque",
}


def partir(tex: str) -> dict[str, str]:
    """Separa el bloque de LaTeX en una tabla por archivo, usando las marcas %%INICIO_/%%FIN_."""
    salida: dict[str, str] = {}
    primera = tex.split("\n\\begin{tabular}", 1)
    # La primera tabla (campos) no tiene marca de inicio: va desde el primer \\begin hasta %%FIN_TABLA_CAMPOS.
    cuerpo = "\\begin{tabular}" + primera[1]
    trozos = cuerpo.replace("%%INICIO_TABLA_", "%%CORTE%%INICIO_TABLA_").split("%%CORTE%%")
    for trozo in trozos:
        for clave, nombre in NOMBRES.items():
            if f"%%FIN_TABLA_{clave}" in trozo:
                limpio = "\n".join(ln for ln in trozo.splitlines() if not ln.startswith("%%")).strip()
                salida[nombre] = limpio + "\n"
    return salida


def principal() -> int:
    etiqueta = sys.argv[1] if len(sys.argv) > 1 else "ronda1"
    tex, md = tablas(etiqueta)
    (CARPETA / "tablas").mkdir(exist_ok=True)
    for nombre, cuerpo in partir(tex).items():
        (CARPETA / "tablas" / f"{nombre}.tex").write_text(cuerpo, encoding="utf-8")
    (CARPETA / f"tablas_{etiqueta}.md").write_text(md, encoding="utf-8")
    print(f"escritas {len(NOMBRES)} tablas .tex y tablas_{etiqueta}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
