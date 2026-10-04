"""Cordura, segunda ronda: ¿hay alguna forma de preguntarle a Laya que si entienda precio y nivel?

Variantes:
  v1  opciones con todo el detalle (la de la primera ronda)
  v2  candidatos como JSON en el estado; opciones cortas ("opcion A")
  v3  noul por candidato ("¿es este el mas barato?") con todos en el estado; gana la mayor prob.
  v4  precio en palabras relativas (mas barato / intermedio / mas caro). OJO: esta variante le da
      la comparacion ya hecha; mide si Laya sabe usarla, no si sabe comparar.
"""

import json
import random
import sys
import time

import laya

from cordura import NIVELES, caso, criterios, verdad

random.seed(11)


def prob_si(r, qid):
    """`noul` ya es la probabilidad de 'si' (p. ej. 0.28 con confidence 0.72 = 'no')."""
    return float(r["answers"][qid]["noul"])


def palabra_precio(c, cands):
    orden = sorted(cands, key=lambda x: x["precio_cop"])
    if c is orden[0]:
        return "el mas barato de todos"
    if c is orden[-1]:
        return "el mas caro de todos"
    return "precio intermedio"


INSTR = {
    "barato": "¿Cual opcion tiene el precio mas bajo?",
    "premium": "¿Cual opcion es de la marca de mejor nivel (premium mejor que confiable, confiable mejor que economico)? Si hay empate, la mas barata.",
    "personaje": "¿Cual opcion trae el personaje {p}? Si hay varias, la mas barata.",
}
NOUL = {
    "barato": "¿El producto {id} es el de precio mas bajo de la lista?",
    "premium": "¿El producto {id} es el de marca de mejor nivel (premium > confiable > economico)?",
    "personaje": "¿El producto {id} trae el personaje {p}?",
}


def correr(agente, variante, tarea, base, cands, p):
    if variante == "v1":
        q = {"q": {"type": "choice", "instructions": INSTR[tarea].format(p=p), "criteria": criterios(cands, "es")}}
        return agente.predict(f"Renglon de la lista escolar: {base}", q)["answers"]["q"]["choice"]
    estado = json.dumps({"renglon": base, "candidatos": cands}, ensure_ascii=False)
    if variante == "v2":
        crit = {c["id"]: f"opcion {c['id']}" for c in cands}
        q = {"q": {"type": "choice", "instructions": INSTR[tarea].format(p=p), "criteria": crit}}
        return agente.predict(estado, q)["answers"]["q"]["choice"]
    if variante == "v3":
        qs = {c["id"]: {"type": "noul", "instructions": NOUL[tarea].format(id=c["id"], p=p)} for c in cands}
        r = agente.predict(estado, qs)
        return max(cands, key=lambda c: prob_si(r, c["id"]))["id"]
    if variante == "v4":
        crit = {}
        for c in cands:
            pj = f", personaje {c['personaje']}" if c["personaje"] else ""
            crit[c["id"]] = f"{c['nombre']}, marca de nivel {c['nivel']}, {palabra_precio(c, cands)}{pj}"
        q = {"q": {"type": "choice", "instructions": INSTR[tarea].format(p=p), "criteria": crit}}
        return agente.predict(f"Renglon de la lista escolar: {base}", q)["answers"]["q"]["choice"]
    raise ValueError(variante)


def main():
    modelos = sys.argv[1:] or ["typed-decisions", "multilingual"]
    casos = [caso(random.choice([2, 3, 4, 6])) for _ in range(200)]
    azar = sum(1 / len(c) for _, c in casos) / len(casos)
    resumen = {"azar": round(azar, 3)}
    for nombre in modelos:
        agente = laya.load(nombre)
        r0 = agente.predict("x", {"q": {"type": "noul", "instructions": "¿si?"}})
        print("forma de respuesta noul:", r0["answers"]["q"], flush=True)
        for variante in ["v1", "v2", "v3", "v4"]:
            for tarea in ["barato", "premium", "personaje"]:
                ok = tot = 0
                t0 = time.perf_counter()
                for base, cands in casos:
                    p = next((c["personaje"] for c in cands if c["personaje"]), None)
                    if tarea == "personaje" and not p:
                        continue
                    ok += correr(agente, variante, tarea, base, cands, p) == verdad(tarea, cands, p)
                    tot += 1
                ms = (time.perf_counter() - t0) / tot * 1000
                resumen[f"{nombre}/{variante}/{tarea}"] = {"acc": round(ok / tot, 3), "n": tot, "ms": round(ms, 1)}
                print(nombre, variante, tarea, f"acc={ok/tot:.2f} (azar~{azar:.2f})", f"{ms:.0f}ms", flush=True)
        del agente
    json.dump(resumen, open("cordura_variantes.json", "w"), indent=2)


if __name__ == "__main__":
    main()
