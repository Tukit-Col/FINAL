"""Medicion del sistema en el colegio nuevo (Agustiniano Norte) sobre la muestra ciega de 200 renglones.
Uso: uv run python ensayos/calibracion/acuerdo_norte.py"""

from __future__ import annotations

import collections
import csv
import json
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import acuerdo as ac  # noqa: E402
import acuerdo_ruta_real as rr  # noqa: E402

CAL = ac.k.SALIDA
M = CAL / "muestra_holdout"
NINGUNO = "NINGUNO"

CONSEJO = {
    "N001": (
        "NINGUNO",
        "El cable UTP es de red y C138 es cable electrico para circuitos; los 5 asesores coinciden.",
    ),
    "N048": (
        "NINGUNO",
        "El porta bateria con broche es un soporte/conector, no la pila (C103) ni un modulo relay (C142); no se inventan codigos (dividido: 2 NINGUNO, 1 C142, 2 C103).",
    ),
    "N072": (
        "NINGUNO",
        "Porta pila con plug DC es un accesorio pasivo; C103 nombra la pila y C142 son modulos relay; consistente con N048.",
    ),
    "N086": (
        "C027",
        "Pintura cubre acuarela y acrilico, que son las dos opciones del renglon, mientras C065 deja fuera la mitad (dividido: un asesor voto C065 por la regla del primero).",
    ),
    "N123": (
        "C032",
        "'hoja examen' es ejemplo literal de C032 y lo que se compra son hojas de examen (dividido: un asesor voto C003 por la forma block).",
    ),
    "N131": (
        "C120",
        "El papel edad media es papel tipo pergamino y C120 incluye 'block papel pergamino', mas especifico que Block (dividido: C120 tres votos, C003 uno, NINGUNO uno).",
    ),
    "N133": (
        "NINGUNO",
        "Mismo articulo que N048 y N072: porta pila con plug es accesorio sin concepto en el catalogo.",
    ),
    "N164": ("C032", "Identico a N123: hojas de examen, ejemplo literal de C032; se mantiene consistencia."),
}
DIVIDIDOS = {i: "consejo dividido" for i in ("N048", "N072", "N086", "N123", "N131", "N133", "N164")}

LECTURA_CAUSAL = {
    "N078": "PDF: '1 block de hojas blancas tamano carta'; la lectura dejo 'hojas blancas' (faltan 'block' y 'tamano carta'). Con el texto leido el oro (C032) tambien es dudoso; con el texto correcto seria un block (C003, lo que el sistema propuso como AMBIGUO).",
    "N058": "PDF: 'acrilicos en frasco plastico (amarillo, azul, rojo, negro, blanco)'; la lectura dejo 'frasco plastico blanco' (el parentesis de colores se fundio en un solo color).",
    "N151": "PDF: encabezado 'Educacion Etica y en Valores Humanos' en su linea y 'Un cuaderno cuadriculado de 50 hojas.' debajo; la lectura pego la materia al renglon (sobran palabras) y el puntaje cayo a 0,11.",
}
LECTURA_SIN_EFECTO = {
    "N016": "agrego 'by' entre titulo y autor (no esta en el PDF); el error es de resolucion (libro con titulo).",
    "N178": "agrego 'by' entre titulo y autor; el error es de resolucion (libro con titulo).",
    "N034": "perdio letras ('ingls-espaol'); el error es de resolucion (C034 y dic-ingles se solapan en la taxonomia).",
    "N111": "perdio letras ('Andrs Felipe Pelez'); el error es de resolucion (libro con titulo).",
    "N118": "perdio la cantidad '2'; el error es de resolucion (resaltador vs marcador).",
}


def g(x: str) -> str:
    return unicodedata.normalize("NFD", x.split("-")[-1]).encode("ascii", "ignore").decode().lower()


def unir(filas, ruta):
    idx = {}
    for r in csv.DictReader(ruta.open(encoding="utf-8-sig")):
        idx.setdefault((g(r["grado"]), r["texto"]), []).append(r)
    inc = [k for k, v in idx.items() if len({(x["concepto"], x["aceptado"]) for x in v}) > 1]
    out, sin = {}, []
    for f in filas:
        v = idx.get((g(f["grado"]), f["texto_original"]))
        if v:
            out[f["id"]] = v[0]
        else:
            sin.append(f["id"])
    return out, sin, inc


def tipo(i, oro, sis, acep):
    if sis == oro:
        return None
    if oro == "C134":
        return (
            "libro con titulo no reconocido (oro C134, sistema NINGUNO)"
            if sis == NINGUNO
            else "libro con titulo: otro concepto"
        )
    if oro == NINGUNO:
        return (
            "oro NINGUNO, sistema acepta un concepto"
            if acep
            else "oro NINGUNO, sistema propone concepto sin aceptar"
        )
    if sis == NINGUNO:
        return "concepto existe en oro, sistema NINGUNO (SIN_MATCH)"
    return "concepto equivocado ACEPTADO" if acep else "concepto equivocado, no aceptado (HUECO/AMBIGUO)"


def main() -> int:
    filas = list(csv.DictReader((M / "muestra.csv").open(encoding="utf-8-sig")))
    ids = [f["id"] for f in filas]
    fm = {f["id"]: f for f in filas}
    A, B = ac.leer(M / "anotador_A_llm.csv"), ac.leer(M / "anotador_B_llm.csv")
    desac = [i for i in ids if A[i] != B[i]]
    assert sorted(desac) == sorted(CONSEJO), (desac, sorted(CONSEJO))
    with (M / "adjudicacion_llm.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "texto_original", "concepto_A", "concepto_B", "adjudicado"])
        for i in desac:
            w.writerow([i, fm[i]["texto_original"], A[i], B[i], CONSEJO[i][0]])
    oro = {i: (A[i] if A[i] == B[i] else CONSEJO[i][0]) for i in ids}
    TAX = {x["codigo"].strip() for x in csv.DictReader((M / "conceptos.csv").open(encoding="utf-8-sig"))}
    S, sin_union, inc = unir(filas, CAL / "holdout_norte_v2.csv")
    S0, sin0, _ = unir(filas, CAL / "holdout_norte.csv")
    if sin_union:
        print("RENGLONES SIN UNIR:", sin_union)
    n = len(ids)
    ok_ids = [i for i in ids if i in S]
    assert len(ok_ids) == n
    rng = np.random.default_rng(ac.SEMILLA)
    a, b = [A[i] for i in ids], [B[i] for i in ids]
    og = [oro[i] for i in ids]
    grado = np.array([fm[i]["grado"] for i in ids])
    kap = lambda x, y: lambda ix: ac.kappa([x[i] for i in ix], [y[i] for i in ix])  # noqa: E731
    acu = np.array([x == y for x, y in zip(a, b, strict=True)])
    res = {
        "aviso_honestidad": "Los tres jueces son LLM (dos anotadores ciegos A y B y un consejo LLM como tercer juez en 8 desacuerdos); el oro NO es humano. Agustiniano Norte es 'otro colegio' pero de la misma congregacion que el colegio piloto (formato de lista y vocabulario parecidos): es generalizacion a un colegio nuevo, no a una congregacion nueva.",
        "n": n,
        "union": {
            "renglones_sin_unir": sin_union,
            "claves_texto_duplicadas_con_resultado_distinto": len(inc),
            "criterio": "colegio Norte, grado y texto leido; en duplicados identicos se usa el primero (todos con igual resultado)",
        },
        "acuerdo_A_B": {
            "porcentaje": float(acu.mean()),
            "desacuerdos": int((~acu).sum()),
            "kappa_cohen": ac.kappa(a, b),
            "kappa_ic95": ac.ic(kap(a, b), n, rng),
            "kappa_ic95_por_grado": ac.ic(kap(a, b), n, rng, grado),
        },
        "oro": {
            "por_acuerdo": int(acu.sum()),
            "por_consejo": len(desac),
            "consejo_dividido": DIVIDIDOS,
            "etiquetas_fuera_de_taxonomia": sorted({v for v in og if v != NINGUNO and v not in TAX}),
        },
    }

    def evalua(SS):
        sis = {i: ac.norm(SS[i]["concepto"]) for i in ids}
        ok = np.array([sis[i] == oro[i] for i in ids])
        acepta = np.array([SS[i]["aceptado"].strip().lower() == "si" for i in ids])
        return sis, ok, acepta

    sis, ok, acepta = evalua(S)
    sis0, ok0, acepta0 = evalua(S0)

    def bloque(ok_, ac_, mask=None):
        m = np.ones(n, bool) if mask is None else mask
        return rr.bloque(ok_[m], ac_[m], None, grado[m], rng)

    res["sistema_v2_vectores"] = {"tau": 0.75, "global": bloque(ok, acepta)}
    res["sistema_v2_vectores"]["solo_renglones_con_acuerdo_A_B"] = bloque(ok, acepta, acu)
    libro = np.array([oro[i] == "C134" for i in ids])
    res["por_tipo"] = {
        "libros_con_titulo_oro_C134": bloque(ok, acepta, libro),
        "resto": bloque(ok, acepta, ~libro),
    }
    res["por_grado_n"] = {gr: int((grado == gr).sum()) for gr in sorted(set(grado))}
    res["sin_vectores_holdout_norte_csv"] = {
        "global": bloque(ok0, acepta0),
        "libros": bloque(ok0, acepta0, libro),
        "resto": bloque(ok0, acepta0, ~libro),
    }
    prev = json.loads((CAL / "acuerdo_ruta_real.json").read_text(encoding="utf-8"))["sistema_ruta_real"][
        "global"
    ]
    gl = res["sistema_v2_vectores"]["global"]
    res["comparacion"] = {
        "siete_colegios_ruta_real_n240": {
            k: prev[k]["valor"] for k in ("exactitud", "precision_aceptada", "aceptada")
        },
        "norte_con_vectores": {k: gl[k]["valor"] for k in ("exactitud", "precision_aceptada", "aceptada")},
        "norte_sin_vectores": {
            k: res["sin_vectores_holdout_norte_csv"]["global"][k]["valor"]
            for k in ("exactitud", "precision_aceptada", "aceptada")
        },
        "nota": "oro LLM en los tres casos; muestras distintas (n 240 vs 200); no se afirma diferencia significativa si los IC se solapan",
    }
    cambio = [i for i in ids if sis[i] != sis0[i] or acepta[ids.index(i)] != acepta0[ids.index(i)]]
    res["comparacion"]["renglones_que_cambian_con_vectores"] = len(cambio)

    errores = []
    for k_, i in enumerate(ids):
        if ok[k_]:
            continue
        t = tipo(i, oro[i], sis[i], acepta[k_])
        if i in LECTURA_CAUSAL:
            origen, nota = "lectura", LECTURA_CAUSAL[i]
        else:
            origen, nota = "resolucion", LECTURA_SIN_EFECTO.get(i, "")
        razones = []
        if i in DIVIDIDOS:
            razones.append("oro del consejo dividido")
        if A[i] != B[i] and sis[i] in (A[i], B[i]):
            razones.append("el sistema coincide con un anotador")
        if oro[i] != NINGUNO and oro[i] not in TAX:
            razones.append(f"oro fuera de taxonomia ({oro[i]})")
        if {oro[i], sis[i]} == {"C034", "dic-ingles"}:
            razones.append(
                "conceptos solapados en la taxonomia (C034 / dic-ingles); los dos anotadores dudaron"
            )
        if origen == "lectura":
            razones.append("el oro se dio sobre el texto mal leido")
        errores.append(
            {
                "id": i,
                "grado": fm[i]["grado"],
                "texto": fm[i]["texto_original"],
                "oro": oro[i],
                "sistema": sis[i],
                "estado": S[i]["estado"],
                "puntaje": float(S[i]["puntaje"]),
                "aceptado": bool(acepta[k_]),
                "origen": origen,
                "tipo": t,
                "nota_lectura": nota,
                "criterio_discutible": bool(razones),
                "razon_discutible": "; ".join(razones),
            }
        )
    res["errores_total"] = len(errores)
    res["errores_por_origen"] = collections.Counter(e["origen"] for e in errores)
    res["errores_por_tipo"] = []
    por = collections.defaultdict(list)
    for e in errores:
        por[e["tipo"]].append(e)
    for t, l in sorted(por.items(), key=lambda kv: -len(kv[1])):
        res["errores_por_tipo"].append(
            {
                "tipo": t,
                "n": len(l),
                "aceptados": sum(e["aceptado"] for e in l),
                "discutibles": sum(e["criterio_discutible"] for e in l),
                "ejemplos": [{k: e[k] for k in ("id", "texto", "oro", "sistema", "estado")} for e in l[:3]],
            }
        )
    ae = [e for e in errores if e["aceptado"]]
    res["aceptados_erroneos"] = {
        "n": len(ae),
        "discutibles": sum(e["criterio_discutible"] for e in ae),
        "detalle": ae,
    }
    res["errores_discutibles_total"] = sum(e["criterio_discutible"] for e in errores)
    res["lectura"] = {
        "con_efecto_en_el_error": LECTURA_CAUSAL,
        "sin_efecto": LECTURA_SIN_EFECTO,
        "revision": "Los 200 textos se cotejaron con el vocabulario del PDF (pdftotext) y los 52 errores uno a uno; solo la presencia de palabras ajenas o letras perdidas se detecta de forma automatica, asi que los errores de lectura en renglones acertados (palabras que faltan) no estan contados: la tasa de lectura es una cota inferior.",
        "defectos_automaticos_en_la_muestra": [
            "N016",
            "N034",
            "N040(apostrofo)",
            "N111",
            "N178",
            "N180(apostrofo)",
        ],
    }
    quita = np.array([i not in LECTURA_CAUSAL for i in ids])
    res["sensibilidad_sin_errores_de_lectura_causales"] = bloque(ok, acepta, quita)
    disc = {e["id"] for e in errores if e["criterio_discutible"]}
    res["sensibilidad_sin_errores_discutibles"] = {
        "nota": "excluye los renglones con error y criterio discutible (cota optimista)",
        **bloque(ok, acepta, np.array([i not in disc for i in ids])),
    }
    (CAL / "acuerdo_norte.json").write_text(
        json.dumps(
            res, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else dict(o)
        ),
        encoding="utf-8",
    )
    f = lambda d: {
        k: (None if d[k]["valor"] is None else round(d[k]["valor"], 3))
        for k in ("exactitud", "precision_aceptada", "aceptada")
    }  # noqa: E731
    print(
        json.dumps(
            {
                "kappa_AB": res["acuerdo_A_B"],
                "oro_extra": res["oro"]["etiquetas_fuera_de_taxonomia"],
                "global": gl,
                "libros": f(res["por_tipo"]["libros_con_titulo_oro_C134"]),
                "n_libros": int(libro.sum()),
                "resto": f(res["por_tipo"]["resto"]),
                "sin_vect": f(res["sin_vectores_holdout_norte_csv"]["global"]),
                "cambian": len(cambio),
                "origen": res["errores_por_origen"],
                "tipos": [
                    (t["tipo"], t["n"], t["aceptados"], t["discutibles"]) for t in res["errores_por_tipo"]
                ],
                "acep_err": {k: v for k, v in res["aceptados_erroneos"].items() if k != "detalle"},
                "disc": res["errores_discutibles_total"],
                "sens_lect": f(res["sensibilidad_sin_errores_de_lectura_causales"]),
                "sens_disc": f(res["sensibilidad_sin_errores_discutibles"]),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
