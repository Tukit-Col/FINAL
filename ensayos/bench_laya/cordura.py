"""Prueba de cordura: ¿Laya entiende 'el mas barato' / 'la mejor marca' / 'el personaje'?"""

import json
import random
import sys
import time
from pathlib import Path

import laya

random.seed(7)
NIVELES = ["economico", "confiable", "premium"]
PERSONAJES = [None, None, "bluey", "spiderman", "frozen"]
PRODUCTOS = [
    "Cuaderno cuadriculado 100 hojas",
    "Lapiz negro HB",
    "Colores x24",
    "Pegante en barra",
    "Tijeras punta roma",
]


def caso(n: int):
    base = random.choice(PRODUCTOS)
    marcas = random.sample(["Norma", "Scribe", "Faber", "Pelikan", "Kores", "Prismacolor", "Bic"], n)
    cands = []
    for i in range(n):
        cands.append(
            {
                "id": "ABCDEFGHIJ"[i],
                "nombre": f"{base} {marcas[i]}",
                "nivel": random.choice(NIVELES),
                "precio_cop": random.randrange(1500, 30000, 100),
                "personaje": random.choice(PERSONAJES),
            }
        )
    return base, cands


def criterios(cands, idioma):
    out = {}
    for c in cands:
        if idioma == "es":
            p = f", personaje {c['personaje']}" if c["personaje"] else ""
            out[c["id"]] = f"{c['nombre']}, marca de nivel {c['nivel']}, ${c['precio_cop']:,} pesos{p}"
        else:
            p = f", character {c['personaje']}" if c["personaje"] else ""
            out[c["id"]] = f"{c['nombre']}, {c['nivel']} brand tier, {c['precio_cop']} COP{p}"
    return out


PREGUNTAS = {
    "es": {
        "barato": "¿Cual opcion tiene el precio mas bajo?",
        "premium": (
            "¿Cual opcion es de la marca de mejor nivel (premium mejor que confiable, "
            "confiable mejor que economico)? Si hay empate, la mas barata."
        ),
        "personaje": "¿Cual opcion trae el personaje {p}? Si hay varias, la mas barata.",
    },
    "en": {
        "barato": "Which option has the lowest price?",
        "premium": (
            "Which option has the best brand tier (premium > confiable > economico)? On ties, the cheapest."
        ),
        "personaje": "Which option has the character {p}? If several, the cheapest.",
    },
}


def verdad(tarea, cands, p=None):
    if tarea == "barato":
        return min(cands, key=lambda c: c["precio_cop"])["id"]
    if tarea == "premium":
        m = max(NIVELES.index(c["nivel"]) for c in cands)
        return min((c for c in cands if NIVELES.index(c["nivel"]) == m), key=lambda c: c["precio_cop"])["id"]
    con = [c for c in cands if c["personaje"] == p]
    return min(con, key=lambda c: c["precio_cop"])["id"] if con else None


def main():
    modelos = sys.argv[1:] or ["multilingual", "typed-decisions", "english"]
    casos = []
    for _ in range(60):
        n = random.choice([2, 3, 4, 6])
        casos.append(caso(n))
    resumen = {}
    for nombre in modelos:
        agente = laya.load(nombre)
        for idioma in ["es", "en"]:
            for tarea in ["barato", "premium", "personaje"]:
                ok = tot = 0
                t0 = time.perf_counter()
                for base, cands in casos:
                    p = next((c["personaje"] for c in cands if c["personaje"]), None)
                    if tarea == "personaje" and not p:
                        continue
                    v = verdad(tarea, cands, p)
                    q = {
                        "q": {
                            "type": "choice",
                            "instructions": PREGUNTAS[idioma][tarea].format(p=p),
                            "criteria": criterios(cands, idioma),
                        }
                    }
                    estado = (
                        f"Renglon de la lista escolar: {base}"
                        if idioma == "es"
                        else f"School list line: {base}"
                    )
                    r = (
                        agente.predict(estado, q)
                        if hasattr(agente, "predict")
                        else agente.system_one(estado, q)
                    )
                    eleg = r["answers"]["q"]["choice"]
                    ok += eleg == v
                    tot += 1
                ms = (time.perf_counter() - t0) / max(tot, 1) * 1000
                azar = sum(1 / len(c) for _, c in casos) / len(casos)
                resumen[f"{nombre}/{idioma}/{tarea}"] = {
                    "aciertos": ok,
                    "total": tot,
                    "acc": round(ok / tot, 3),
                    "ms": round(ms, 1),
                }
                print(
                    nombre,
                    idioma,
                    tarea,
                    f"{ok}/{tot}",
                    f"acc={ok / tot:.2f}",
                    f"azar~{azar:.2f}",
                    f"{ms:.0f}ms",
                    flush=True,
                )
        del agente
    salida = Path(__file__).resolve().parents[2] / "ensayos" / "bench_laya" / "salidas" / "cordura.json"
    salida.write_text(json.dumps(resumen, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
