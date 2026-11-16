"""Repetibilidad en el PRODUCTO: la lectura varia, ¿varia el concepto resuelto y el kit?

Reusa las lecturas guardadas en repetibilidad.json (6 listas x 5 corridas; no relee, 0 llamadas de lectura).
Cada renglon pasa por la resolucion real del sistema: `corregir` + `descubrir.clasificar` (con el vector del
renglon, como produccion), corte 0,5 (sin_match) y tau = 0,75 (aceptacion automatica vs revision humana).
Los vectores de textos nuevos se piden al mismo embeder del sistema (`embeder_gemini`) y se cachean.

    uv run python ensayos/calibracion/repetibilidad_producto.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
for r in (RAIZ / "servicios" / "catalogo", RAIZ / "libs" / "py" / "tukit_comun"):
    sys.path.insert(0, str(r))
from tukit_catalogo import descubrir as D  # noqa: E402
from tukit_catalogo.transcripcion import corregir, lexico_de  # noqa: E402

DATOS = Path(__file__).resolve().parent / "datos"
ENTRADA = RAIZ / "docs/informes/calibracion/repetibilidad.json"
SALIDA = RAIZ / "docs/informes/calibracion/repetibilidad_producto.json"
CACHE = DATOS / "vectores_repetibilidad.npz"
TAU, CORTE = 0.75, 0.5


def norma(t: str) -> frozenset[str]:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return frozenset(w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 1)


def jac(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def main() -> int:
    ent = json.loads(ENTRADA.read_text())
    cat = json.loads((DATOS / "catalogo_conceptos.json").read_text())
    z = np.load(DATOS / "centroides.npz", allow_pickle=False)
    cent = dict(zip(z["codigos"].tolist(), z["centroides"].astype(float), strict=True))
    conceptos = []
    for c in cat["conceptos"]:
        conceptos.append({"id": c["id"], "codigo": c["codigo"], "nombre": c["nombre"], "sinonimos": list(c["sinonimos"]),
                          "discriminantes": tuple(c["discriminantes"]), "tipo_item": c["tipo_item"],
                          "embedding": cent[c["codigo"]].tolist() if c["codigo"] in cent else None})
    lex = lexico_de(conceptos)
    nombre = {c["id"]: c["nombre"] for c in conceptos}

    textos = sorted({i["descripcion"] for d in ent["documentos"] for c in d["corridas"] if c["aceptada"] for i in c["items"]})
    vec: dict[str, np.ndarray] = {}
    if CACHE.exists():
        zz = np.load(CACHE, allow_pickle=False)
        vec = dict(zip(zz["textos"].tolist(), zz["vectores"], strict=True))
    faltan = [t for t in textos if t not in vec]
    # vectores ya calculados del corpus etiquetado
    zr = np.load(DATOS / "vectores_renglones.npz", allow_pickle=False)
    previos = dict(zip(zr["textos"].tolist(), zr["vectores"], strict=True))
    for t in list(faltan):
        if t in previos:
            vec[t] = previos[t]
            faltan.remove(t)
    sin_vector = 0
    if faltan:
        if os.environ.get("GEMINI_API_KEY", "").strip():
            from tukit_catalogo.embeddings import embeder_gemini

            nuevos = np.array(embeder_gemini(faltan), dtype=np.float32)
            for t, v in zip(faltan, nuevos, strict=True):
                vec[t] = v
            np.savez_compressed(CACHE, textos=np.array(list(vec)), vectores=np.array(list(vec.values())))
        else:
            sin_vector = len(faltan)

    memo = {}

    def resolver(t: str):
        if t not in memo:
            v = vec[t].astype(float).tolist() if t in vec else None
            cid, _, s = D.clasificar(corregir(t, lex), conceptos, embedding_renglon=v)
            if cid is None or s < CORTE:
                memo[t] = (None, round(s, 4), "sin_match")
            else:
                memo[t] = (cid, round(s, 4), "auto" if s >= TAU else "revision")
        return memo[t]

    docs = []
    for d in ent["documentos"]:
        corr = [c for c in d["corridas"] if c["aceptada"]]
        n = len(corr)
        # agrupar renglones entre corridas: ancla = primera corrida; el resto se empareja voraz por Jaccard >= 0.5
        grupos = []  # cada grupo: {run: (desc, cant)}
        ya = []
        for k, c in enumerate(corr):
            its = [(i["descripcion"], i["cantidad"], norma(i["descripcion"])) for i in c["items"]]
            usados = set()
            pares = sorted(((jac(its[a][2], grupos[g]["n"]), a, g) for a in range(len(its)) for g in range(len(grupos))), reverse=True)
            gu = set()
            for s, a, g in pares:
                if s < 0.5:
                    break
                if a in usados or g in gu or k in grupos[g]["r"]:
                    continue
                usados.add(a), gu.add(g)
                grupos[g]["r"][k] = (its[a][0], its[a][1])
            for a, it in enumerate(its):
                if a not in usados:
                    grupos.append({"n": it[2], "r": {k: (it[0], it[1])}})
        estables = absorbidos = auto_cambia = 0
        solo_ausencia = concepto_distinto = 0
        presentes_todas = concepto_igual_todas = cantidad_cambia = 0
        detalle_cambios = []
        for g in grupos:
            res = {k: resolver(x[0]) for k, x in g["r"].items()}
            resultados = {(r[0], r[2]) for r in res.values()}
            todas = len(g["r"]) == n
            if todas:
                presentes_todas += 1
                if len({r[0] for r in res.values()}) == 1:
                    concepto_igual_todas += 1
                if len({x[1] for x in g["r"].values()}) > 1:
                    cantidad_cambia += 1
            if todas and len(resultados) == 1:
                estables += 1
                continue
            # inestable: ausente en alguna corrida o resultado distinto
            if len(resultados) == 1:
                solo_ausencia += 1
            else:
                concepto_distinto += 1
            hay_auto = any(r[2] == "auto" for r in res.values())
            if hay_auto:
                auto_cambia += 1
            else:
                absorbidos += 1
            if len(detalle_cambios) < 12:
                detalle_cambios.append({"ejemplo": next(iter(g["r"].values()))[0], "corridas_presente": len(g["r"]),
                                        "resultados": sorted({(nombre.get(r[0], "sin concepto"), r[2]) for r in res.values()})})
        total = len(grupos)
        # conjunto de conceptos que entran solos (auto) por corrida
        conj = []
        for c in corr:
            s = set()
            rev = set()
            for i in c["items"]:
                cid, sc, est = resolver(i["descripcion"])
                if est == "auto":
                    s.add(cid)
                elif cid is not None:
                    rev.add(cid)
            conj.append((s, rev))
        auto = [a for a, _ in conj]
        union = set.union(*auto)
        inter = set.intersection(*auto)
        variables = union - inter
        en_revision_alguna = {c for c in variables if any(c in r for _, r in conj)}
        vs_primera = [{"aparecen": len(a - auto[0]), "desaparecen": len(auto[0] - a)} for a in auto[1:]]
        pares_j = [len(auto[i] & auto[j]) / len(auto[i] | auto[j]) for i in range(n) for j in range(i + 1, n)]
        # estados de renglon por corrida
        est_run = []
        for c in corr:
            cnt = {"auto": 0, "revision": 0, "sin_match": 0}
            for i in c["items"]:
                cnt[resolver(i["descripcion"])[2]] += 1
            est_run.append(cnt)
        docs.append({
            "documento": d["documento"], "corridas": n,
            "renglones_agrupados_entre_corridas": total,
            "a_renglones_presentes_en_las_5": presentes_todas,
            "a_pct_renglones_estables_(presente_en_las_5_y_mismo_resultado)": round(100 * estables / total, 1),
            "a_pct_mismo_concepto_entre_los_presentes_en_las_5": round(100 * concepto_igual_todas / presentes_todas, 1) if presentes_todas else None,
            "a_renglones_presentes_en_las_5_con_cantidad_distinta": cantidad_cambia,
            "b_conceptos_auto_por_corrida": [len(a) for a in auto],
            "b_conceptos_union": len(union), "b_conceptos_en_las_5": len(inter),
            "b_conceptos_que_aparecen_o_desaparecen": len(variables),
            "b_vs_primera_corrida": vs_primera,
            "b_jaccard_conjunto_entre_corridas_media": round(float(np.mean(pares_j)), 4),
            "b_jaccard_conjunto_entre_corridas_min": round(float(min(pares_j)), 4),
            "b_conceptos_variables": sorted(nombre[c] for c in variables),
            "b_de_ellos_que_aparecen_en_revision_en_alguna_corrida": len(en_revision_alguna),
            "c_renglones_inestables": total - estables,
            "c_inestables_solo_por_ausencia_en_alguna_corrida": solo_ausencia,
            "c_inestables_con_resultado_distinto_(concepto_o_estado)": concepto_distinto,
            "c_absorbidos_por_guardrail_(nunca_>=tau)": absorbidos,
            "c_con_alguna_aceptacion_automatica": auto_cambia,
            "estados_por_corrida": est_run,
            "ejemplos_inestables": detalle_cambios,
        })
    T = lambda k: sum(x[k] for x in docs)  # noqa: E731
    resumen = {
        "tau": TAU, "corte_sin_match": CORTE, "lecturas_nuevas": 0, "textos_unicos_resueltos": len(memo),
        "textos_sin_vector_(coseno=0)": sin_vector,
        "renglones_agrupados": T("renglones_agrupados_entre_corridas"),
        "renglones_inestables": T("c_renglones_inestables"),
        "absorbidos_por_guardrail": T("c_absorbidos_por_guardrail_(nunca_>=tau)"),
        "inestables_solo_por_ausencia": T("c_inestables_solo_por_ausencia_en_alguna_corrida"),
        "inestables_resultado_distinto": T("c_inestables_con_resultado_distinto_(concepto_o_estado)"),
        "con_aceptacion_automatica": T("c_con_alguna_aceptacion_automatica"),
        "conceptos_que_aparecen_o_desaparecen": T("b_conceptos_que_aparecen_o_desaparecen"),
        "conceptos_union": T("b_conceptos_union"),
    }
    # (d) ruta rapida: lista oficial con version vigente revisada (consulta de solo lectura a la base de desarrollo)
    import subprocess

    try:
        q = ("select count(*), count(*) filter (where v.vigente and v.revisada_en is not null) "
             "from lista_oficial l join version_lista_oficial v on v.lista_id=l.id and v.vigente")
        o = subprocess.run(["psql", "tukit_catalogo", "-At", "-F", ",", "-c", q], capture_output=True, text=True, timeout=20).stdout.strip().split(",")
        ruta = {"listas_oficiales": int(o[0]), "con_version_vigente_revisada": int(o[1]),
                "memoria_dice": "76 grados de 7 colegios, cada lista aprobada por una persona",
                "nota": "La base de desarrollo no reproduce el 76: hay mas listas y mas revisadas. Cuadrar la cifra antes de citarla."}
    except Exception as e:  # noqa: BLE001
        ruta = {"error": str(e)}
    resumen["d_ruta_rapida"] = ruta
    SALIDA.write_text(json.dumps({"resumen": resumen, "documentos": docs}, ensure_ascii=False, indent=1))
    print(json.dumps(resumen, indent=1))
    for x in docs:
        print(x["documento"], x["renglones_agrupados_entre_corridas"], x["a_pct_renglones_estables_(presente_en_las_5_y_mismo_resultado)"],
              x["a_pct_mismo_concepto_entre_los_presentes_en_las_5"], "union", x["b_conceptos_union"], "var", x["b_conceptos_que_aparecen_o_desaparecen"],
              "revis", x["b_de_ellos_que_aparecen_en_revision_en_alguna_corrida"], "J", x["b_jaccard_conjunto_entre_corridas_media"],
              "inest", x["c_renglones_inestables"], "abs", x["c_absorbidos_por_guardrail_(nunca_>=tau)"], "auto", x["c_con_alguna_aceptacion_automatica"],
              "ausencia", x["c_inestables_solo_por_ausencia_en_alguna_corrida"], "distinto", x["c_inestables_con_resultado_distinto_(concepto_o_estado)"], "cant", x["a_renglones_presentes_en_las_5_con_cantidad_distinta"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
