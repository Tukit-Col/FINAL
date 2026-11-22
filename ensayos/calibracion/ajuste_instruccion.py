"""Ajuste iterativo de la instruccion de lectura con ejemplos en el contexto."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ajuste_nucleo as nu  # noqa: E402

for ruta in (nu.RAIZ / "servicios" / "inteligencia", nu.RAIZ / "libs" / "py" / "tukit_comun"):
    sys.path.insert(0, str(ruta))
from tukit_inteligencia import gemini  # noqa: E402  (solo lectura: la instruccion de produccion)

RESULTADOS = nu.CACHE / "resultados"

ENTRENAMIENTO = (
    "COLEGIO AGUSTINIANO CIUDAD SALITRE",
    "COLEGIO MADRE MATILDE",
    "JARDIN INFANTIL OSITO DE MIEL",
)
EVALUACION = (
    "GIMNASIO NUEVO MODELIA",
    "COLEGIO PARROQUIAL SAN PEDRO CLAVER",
    "UNIDAD EDUCATIVA PRADOS DE ALAMEDA",
    "UNIDAD EDUCATIVA BAHIA SOLANO",
)

V0 = gemini._PROMPT

EJEMPLOS_V1: list[tuple[str, str]] = [
    (
        "· Diccionario Escolar pequeño. Cualquier editorial.\n"
        "@LIBRO RAYITAS C / EDITORIAL MUNDO DE NIÑOS.\n"
        "AGENDA ESCOLAR (la entrega el colegio)",
        '[{"descripcion": "Diccionario Escolar pequeño. Cualquier editorial.", "cantidad": 1},\n'
        ' {"descripcion": "LIBRO RAYITAS C / EDITORIAL MUNDO DE NIÑOS", "cantidad": 1},\n'
        ' {"descripcion": "Agenda escolar (la entrega el colegio)", "cantidad": 1}]',
    ),
    (
        "● 1 Kit de aseo personal: Pañitos húmedos, 1 caja de pañuelos faciales.",
        '[{"descripcion": "Kit de aseo personal", "cantidad": 1},\n'
        ' {"descripcion": "Kit de aseo personal: Pañitos húmedos", "cantidad": 1},\n'
        ' {"descripcion": "Kit de aseo personal: 1 caja de pañuelos faciales", "cantidad": 1}]',
    ),
    (
        "1 regla 30 cm compás, transportador,\nTodo debidamente marcado.",
        '[{"descripcion": "regla 30 cm", "cantidad": 1},\n'
        ' {"descripcion": "compás", "cantidad": 1},\n'
        ' {"descripcion": "transportador", "cantidad": 1}]',
    ),
    (
        "3 pintura académica con olor de 120g, amarillo, azul y rojo.",
        '[{"descripcion": "pintura académica con olor de 120g, amarillo", "cantidad": 1},\n'
        ' {"descripcion": "pintura académica con olor de 120g, azul", "cantidad": 1},\n'
        ' {"descripcion": "pintura académica con olor de 120g, rojo", "cantidad": 1}]',
    ),
]
EJEMPLOS_V2: list[tuple[str, str]] = [
    EJEMPLOS_V1[0],
    EJEMPLOS_V1[2],
    (
        "ARTES\nBata para artes con mangas.\nTodo debidamente marcado.\n"
        "Cartuchera con: esferos, lápices, borrador.\nLink de pago: https://pagoslearning.com/\n"
        "UNIFORMES\nUniforme de diario: blusa blanca, jardinera, medias y zapatos negros de cuero.",
        '[{"descripcion": "Bata para artes con mangas", "cantidad": 1},\n'
        ' {"descripcion": "Cartuchera", "cantidad": 1},\n'
        ' {"descripcion": "esferos", "cantidad": 1},\n'
        ' {"descripcion": "lápices", "cantidad": 1},\n'
        ' {"descripcion": "borrador", "cantidad": 1},\n'
        ' {"descripcion": "Uniforme de diario", "cantidad": 1}]\n'
        '(Sin "ARTES:" ni "Cartuchera con:" delante de cada item; la nota, el enlace y las prendas '
        "del uniforme no son items.)",
    ),
]
REGLAS_V2 = ""


def _con_ejemplos(base: str, ejemplos: list[tuple[str, str]], reglas: str = "") -> str:
    if not ejemplos and not reglas:
        return base
    partes = [base]
    if reglas:
        partes.append(reglas.strip())
    if ejemplos:
        partes.append(
            "Ejemplos (fragmento de una pagina -> los items que esperamos). Son solo guias de "
            "formato: no los copies si no estan escritos en la pagina."
        )
        for i, (entrada, salida) in enumerate(ejemplos, 1):
            partes.append(f"Ejemplo {i}. Pagina:\n{entrada.strip()}\nItems:\n{salida.strip()}")
    return "\n\n".join(partes)


def instrucciones() -> dict[str, tuple[str, int]]:
    return {
        "v0": (V0, 0),
        "v1": (_con_ejemplos(V0, EJEMPLOS_V1), len(EJEMPLOS_V1)),
        "v2": (_con_ejemplos(V0, EJEMPLOS_V2, REGLAS_V2), len(EJEMPLOS_V2)),
    }


def conjunto(nombre: str) -> list[dict]:
    listas = sorted(nu.cargar_listas().values(), key=lambda d: (d["colegio"], d["grado"]))
    if nombre == "entrenamiento":
        return [d for d in listas if d["colegio"] in ENTRENAMIENTO]
    if nombre == "evaluacion":
        return [d for d in listas if d["colegio"] in EVALUACION]
    return listas


def _paginas(pdf: Path) -> int:
    import pypdfium2 as pdfium

    return len(pdfium.PdfDocument(pdf.read_bytes()))


def _leer_lista(d: dict, version: str, texto: str, max_paginas: int | None = None) -> dict:
    r = nu.leer_documento(d["pdf"], version, texto, max_paginas)
    m = nu.calcular_prf1(r["items"], d["gold"])
    e = nu.tipos_de_error(r["items"], d["gold"], m)
    return {
        "id": d["id"],
        "colegio": d["colegio"],
        "grado": d["grado"],
        "paginas": r["paginas"],
        "tp": m["tp"],
        "fp": m["fp"],
        "fn": m["fn"],
        "precision": m["precision"],
        "recall": m["recall"],
        "f1": m["f1"],
        "n_pred": len(r["items"]),
        "n_gold": len(d["gold"]),
        "errores": e["cuenta"],
        "ejemplos": e["ejemplos"],
        "usd_nuevo": r["usd_nuevo"],
        "llamadas_nuevas": r["llamadas_nuevas"],
    }


def ronda(version: str, nombre: str, maximo: int | None) -> None:
    texto, k = instrucciones()[version]
    listas = conjunto(nombre)[: maximo or None]
    antes = nu.gasto_total()
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda d: _leer_lista(d, version, texto), listas))
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    previo = RESULTADOS / f"{version}.json"
    guardado = json.loads(previo.read_text()) if previo.exists() else {}
    guardado.update({r["id"]: r for r in res})
    previo.write_text(json.dumps(guardado, ensure_ascii=False))
    for parte in ("entrenamiento", "evaluacion"):
        ids = {d["id"] for d in conjunto(parte)}
        sel = [r for r in res if r["id"] in ids]
        if sel:
            a = nu.agregar(sel)
            print(
                f"{version} {parte}: listas={a['listas']} P={a['P']:.4f} R={a['R']:.4f} "
                f"F1micro={a['F1_micro']:.4f} F1macro={a['F1_macro']:.4f}"
            )
    print(f"gasto de esta corrida {nu.gasto_total() - antes:.4f} USD; acumulado {nu.gasto_total():.4f} USD")


def errores(version: str, por_tipo: int) -> None:
    datos = json.loads((RESULTADOS / f"{version}.json").read_text())
    ids = {d["id"] for d in conjunto("entrenamiento")}
    tot: dict[str, int] = {}
    ej: dict[str, list] = {}
    for r in datos.values():
        if r["id"] not in ids:
            continue
        for t, c in r["errores"].items():
            tot[t] = tot.get(t, 0) + c
            for x in r["ejemplos"][t]:
                ej.setdefault(t, []).append((r["colegio"][:12], r["grado"], x))
    print("conteo entrenamiento:", tot)
    for t, xs in ej.items():
        print(f"== {t} ({len(xs)})")
        for x in xs[:por_tipo]:
            print("  ", json.dumps(x, ensure_ascii=False)[:260])


def estimar(version: str) -> None:
    texto, _ = instrucciones()[version]
    pags = sum(_paginas(d["pdf"]) for d in conjunto("todos"))
    t_in = 1300 + len(texto) / 3.5
    usd = pags * (t_in * nu.USD_IN + 900 * nu.USD_OUT) / 1e6
    print(
        f"{version}: {pags} paginas, ~{t_in:.0f} tokens de entrada/pagina, estimado {usd:.3f} USD "
        f"para las 80 listas; gasto acumulado {nu.gasto_total():.4f} USD (tope {nu.TOPE_USD:.2f})"
    )


def _cgs() -> list[dict]:
    rev = "de2c887"
    g = json.loads(
        gzip.decompress(
            subprocess.run(
                ["git", "-C", str(nu.RAIZ), "show", f"{rev}:01-percepcion/datos/gold_standard_anon.json.gz"],
                capture_output=True,
                check=True,
            ).stdout
        )
    )["documentos"]
    archivos = {unicodedata.normalize("NFC", p.name): p for p in nu.CGS_DIR.glob("*.pdf")}
    out = []
    for d in g:
        p = archivos.get(unicodedata.normalize("NFC", d["archivo"]))
        if p:
            out.append(
                {
                    "id": d["id"],
                    "archivo": d["archivo"],
                    "pdf": p,
                    "gold": [
                        {"descripcion": i["descripcion"], "cantidad": i.get("cantidad")} for i in d["items"]
                    ],
                }
            )
    return out


def _cgs_referencia(ids: set[str]) -> dict:
    rev = "de2c887"
    r = json.loads(
        gzip.decompress(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(nu.RAIZ),
                    "show",
                    f"{rev}:01-percepcion/datos/resultados_benchmark_10.json.gz",
                ],
                capture_output=True,
                check=True,
            ).stdout
        )
    )["Gemini (LMM)"]
    archivo_a_id = {d["archivo"]: d["id"] for d in _cgs()}
    todos = [nu.calcular_prf1(x["items_pred_data"], x["items_gold_data"]) for x in r]
    sub = [
        nu.calcular_prf1(x["items_pred_data"], x["items_gold_data"])
        for x in r
        if archivo_a_id.get(x["archivo"]) in ids
    ]
    return {"cgs10_completo": nu.agregar(todos), "mismos_docs": nu.agregar(sub)}


def cgs(version: str) -> None:
    texto, _ = instrucciones()[version]
    docs = _cgs()
    antes = nu.gasto_total()
    res = []
    for d in docs:
        r = nu.leer_documento(d["pdf"], f"cgs-{version}", texto, max_paginas=5)
        m = nu.calcular_prf1(r["items"], d["gold"])
        res.append(
            {
                "id": d["id"],
                "archivo": d["archivo"],
                "tp": m["tp"],
                "fp": m["fp"],
                "fn": m["fn"],
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
            }
        )
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / f"cgs_{version}.json").write_text(json.dumps(res, ensure_ascii=False))
    a = nu.agregar(res)
    ref = _cgs_referencia({d["id"] for d in docs})
    print(
        f"CGS ({len(docs)} de 10 docs) {version}: P={a['P']:.4f} R={a['R']:.4f} F1micro={a['F1_micro']:.4f} "
        f"F1macro={a['F1_macro']:.4f}"
    )
    print(
        f"referencia benchmark mismos docs: F1micro={ref['mismos_docs']['F1_micro']:.4f} "
        f"F1macro={ref['mismos_docs']['F1_macro']:.4f}; CGS-10 completo {ref['cgs10_completo']['F1_micro']:.4f}"
    )
    print(f"gasto {nu.gasto_total() - antes:.4f} USD; acumulado {nu.gasto_total():.4f}")


def _delta_pareado(a: list[dict], b: list[dict], reps: int = 2000) -> dict:
    import random

    rnd = random.Random(11)
    d0 = nu.agregar(b)["F1_micro"] - nu.agregar(a)["F1_micro"]
    vals = []
    for _ in range(reps):
        idx = [rnd.randrange(len(a)) for _ in a]
        vals.append(nu.agregar([b[i] for i in idx])["F1_micro"] - nu.agregar([a[i] for i in idx])["F1_micro"])
    vals.sort()
    return {
        "delta_f1_micro": round(d0, 4),
        "ic95": [round(vals[int(0.025 * reps)], 4), round(vals[int(0.975 * reps) - 1], 4)],
    }


def informe(elegida: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ins = instrucciones()
    ent, eva = conjunto("entrenamiento"), conjunto("evaluacion")
    ids_eva = {d["id"] for d in eva}
    ids_ent = {d["id"] for d in ent}
    gasto = [json.loads(x) for x in nu.LIBRO_GASTO.read_text().splitlines() if x.strip()]
    filas, detalle = [], {}
    hoy = dt.date.today().isoformat()
    for v in ("v0", "v1", "v2"):
        f = RESULTADOS / f"{v}.json"
        if not f.exists():
            continue
        datos = json.loads(f.read_text())
        sel = [r for r in datos.values() if r["id"] in ids_eva]
        sel_ent = [r for r in datos.values() if r["id"] in ids_ent]
        a, ci = nu.agregar(sel), nu.bootstrap(sel)
        a_ent = nu.agregar(sel_ent) if sel_ent else None
        usd = sum(g["usd"] for g in gasto if g["version"] == v)
        filas.append(
            {
                "fecha": hoy,
                "version_instruccion": v,
                "n": len(ent),
                "j": len(sel),
                "k": ins[v][1],
                "P": round(a["P"], 4),
                "R": round(a["R"], 4),
                "F1_micro": round(a["F1_micro"], 4),
                "F1_macro": round(a["F1_macro"], 4),
                "costo_usd": round(usd, 4),
            }
        )
        errs: dict[str, dict] = {"entrenamiento": {}, "evaluacion": {}}
        for nombre, conj in (("entrenamiento", sel_ent), ("evaluacion", sel)):
            for r in conj:
                for t, c in r["errores"].items():
                    errs[nombre][t] = errs[nombre].get(t, 0) + c
        base = json.loads((RESULTADOS / "v0.json").read_text())
        dif = _delta_pareado([base[r["id"]] for r in sel], sel) if v != "v0" else None
        detalle[v] = {
            "delta_vs_v0_evaluacion": dif,
            "evaluacion": {
                **{k: round(x, 4) if isinstance(x, float) else x for k, x in a.items()},
                "ic95_bootstrap_por_lista": {k: [round(y, 4) for y in z] for k, z in ci.items()},
            },
            "entrenamiento": {k: round(x, 4) if isinstance(x, float) else x for k, x in a_ent.items()}
            if a_ent
            else None,
            "tipos_de_error": errs,
            "k": ins[v][1],
            "instruccion": ins[v][0],
            "costo_usd": round(usd, 4),
        }
    with (nu.SALIDA / "gemini_rondas.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    cgs_res = {}
    for v in ("v0", "v1", "v2"):
        f = RESULTADOS / f"cgs_{v}.json"
        if f.exists():
            rr = json.loads(f.read_text())
            cgs_res[v] = {
                "documentos": [r["id"] for r in rr],
                **{k: round(x, 4) if isinstance(x, float) else x for k, x in nu.agregar(rr).items()},
            }
    ids_cgs = set(next(iter(cgs_res.values()))["documentos"]) if cgs_res else set()
    ref = _cgs_referencia(ids_cgs) if cgs_res else None
    out = {
        "fecha": hoy,
        "modelo": nu.MODELO,
        "temperatura": 0,
        "render_dpi": 150,
        "commit": subprocess.run(
            ["git", "-C", str(nu.RAIZ), "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "metrica": "06_comparar_enfoques.calcular_prf1 (de2c887): texto normalizado igual o SequenceMatcher >= 0,75",
        "gold": (
            "renglones de la version vigente y revisada de cada lista (item_lista_oficial). Es la salida del "
            "sistema revisada por una persona: circular en parte. Solo el Agustiniano Ciudad Salitre tiene "
            "renglones editados (versiones 5 y 6); en los otros seis colegios el gold coincide con la lectura "
            "de produccion del 13-nov salvo la cantidad."
        ),
        "x_listas": len(ent) + len(eva),
        "n_entrenamiento": len(ent),
        "j_evaluacion": len(eva),
        "colegios_entrenamiento": list(ENTRENAMIENTO),
        "colegios_evaluacion": list(EVALUACION),
        "listas_entrenamiento": [f"{d['colegio']} | {d['grado']} | {d['id']}" for d in ent],
        "listas_evaluacion": [f"{d['colegio']} | {d['grado']} | {d['id']}" for d in eva],
        "rondas": detalle,
        "version_elegida": elegida,
        "cgs10": {
            "nota": "solo comparacion, nunca ajuste; 6 de los 10 PDF siguen disponibles; 5 primeras paginas "
            "como el benchmark",
            "corridas": cgs_res,
            "referencia_benchmark_mismos_docs": ref["mismos_docs"] if ref else None,
            "referencia_cgs10_completo": ref["cgs10_completo"] if ref else None,
        },
        "umbral": None,
        "umbral_nota": "No hay un umbral de F1 de lectura fijado antes de medir en ningun commit; la figura no lo dibuja.",
        "gasto": {
            "total_usd": round(sum(g["usd"] for g in gasto), 4),
            "llamadas": len(gasto),
            "precio_supuesto_usd_por_millon": {"entrada": nu.USD_IN, "salida": nu.USD_OUT},
            "tokens_entrada": sum(int((g["uso"] or {}).get("promptTokenCount") or 0) for g in gasto),
            "tokens_salida": sum(int((g["uso"] or {}).get("candidatesTokenCount") or 0) for g in gasto),
        },
    }
    (nu.SALIDA / "gemini_rondas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "axes.grid": True,
            "grid.color": "#E3E3E3",
            "axes.axisbelow": True,
        }
    )
    metricas = [("F1_micro", "F1 micro"), ("F1_macro", "F1 macro"), ("P", "Precisión"), ("R", "Sensibilidad")]
    versiones = [f["version_instruccion"] for f in filas]
    color = {v: ("#D55E00" if v == elegida else ("#8C8C8C" if v == "v0" else "#0072B2")) for v in versiones}
    fig, ax = plt.subplots(figsize=(6.3, 3.2))
    ancho = 0.8 / len(versiones)
    for i, v in enumerate(versiones):
        d = detalle[v]["evaluacion"]
        for jx, (m, _) in enumerate(metricas):
            x = jx + (i - (len(versiones) - 1) / 2) * ancho
            lo, hi = (
                d["ic95_bootstrap_por_lista"].get(m, [d[m], d[m]])
                if m in ("F1_micro", "F1_macro", "P", "R")
                else (d[m], d[m])
            )
            ax.bar(x, d[m], ancho * 0.92, color=color[v], label=v if jx == 0 else None)
            ax.errorbar(x, d[m], yerr=[[d[m] - lo], [hi - d[m]]], color="#333333", lw=0.8, capsize=2)
    ax.set_xticks(range(len(metricas)), [b for _, b in metricas])
    lo_all = min(
        min(detalle[v]["evaluacion"]["ic95_bootstrap_por_lista"][m][0] for m, _ in metricas)
        for v in versiones
    )
    ax.set_ylim(max(0, lo_all - 0.03), 1.0)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.2f}".replace(".", ",")))
    etiquetas = {"v0": "v0 (instrucción de producción, k=0)"}
    for v in versiones[1:]:
        etiquetas[v] = f"{v} (k={detalle[v]['k']}){' elegida' if v == elegida else ''}"
    h, lab = ax.get_legend_handles_labels()
    ax.legend(
        h,
        [etiquetas[x] for x in lab],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        fontsize=7.5,
        frameon=False,
    )
    ax.set_ylabel(f"evaluación, j={len(eva)} listas")
    ax.set_title(
        "Lectura de listas por ronda de ajuste de la instrucción (IC95 bootstrap por lista)", fontsize=9
    )
    fig.tight_layout()
    fig.savefig(nu.SALIDA / "gemini_rondas.pdf")
    print(json.dumps(filas, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["exportar", "estimar", "ronda", "errores", "cgs", "informe"])
    ap.add_argument("version", nargs="?", default="v0")
    ap.add_argument("--conjunto", default="todos", choices=["todos", "entrenamiento", "evaluacion"])
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--por-tipo", type=int, default=12)
    a = ap.parse_args()
    if a.accion == "exportar":
        nu.exportar()
    elif a.accion == "estimar":
        estimar(a.version)
    elif a.accion == "ronda":
        ronda(a.version, a.conjunto, a.max)
    elif a.accion == "errores":
        errores(a.version, a.por_tipo)
    elif a.accion == "cgs":
        cgs(a.version)
    else:
        informe(a.version)


if __name__ == "__main__":
    main()
