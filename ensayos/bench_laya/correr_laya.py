"""El retador: Laya armando los mismos kits, en cuatro modalidades.

Corre en `.venv-laya` (torch + laya), sin importar nada del proyecto: lee
`instancias.json` y `escenarios.json` y escribe `laya_<modalidad>.json` con una
asignacion `{orden: sku}` por (instancia, escenario). La evaluacion la hace
`evaluar.py` con las funciones de produccion, igual que para el NSGA-II.

Modalidades:
  A  linea aislada: una pregunta por linea, viendo solo ese renglon.
  B  lista completa: el estado es la lista entera (con presupuesto si lo hay) y
     se pregunta por cada linea; varias preguntas por pasada.
  C  secuencial: decide en orden y cada pregunta ve el presupuesto restante y lo
     minimo que cuestan las lineas que faltan.
  D  juez de kits: se arman 5 kits completos con reglas simples (sin NSGA-II) y
     Laya elige uno.

El formato de las preguntas (opciones descritas en espanol, checkpoint
`typed-decisions`) se eligio con la prueba de cordura sobre casos sinteticos,
no mirando estas instancias.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

CARPETA = Path(__file__).resolve().parent
NIVELES = ("economico", "confiable", "premium")
INFORMATIVOS = {"licencia_digital", "no_comprar", "diferido", "uniforme"}
SURTIBLES = {"mercado_abierto", "libro_libre"}
LETRAS = "ABCDEFGHIJ"
PREGUNTAS_POR_PASADA = 8
TOKENS_POR_PASADA = 8000

# Laya, ante una falta de memoria en GPU, reintenta la llamada en CPU; con estados
# de miles de tokens eso tarda minutos por llamada y colgo una corrida dos horas.
# Se vuelve error para manejarlo aqui (tandas de una pregunta).
warnings.filterwarnings("error", message="Warning: GPU memory exceeded")


# ------------------------------------------------------- utilidades de dominio
# Copias minimas de la aritmetica del optimizador (este entorno no tiene pymoo).


def rango(c: dict) -> int:
    return NIVELES.index(c["nivel"]) if c["nivel"] in NIVELES else len(NIVELES)


def unidades(r: dict, c: dict) -> int:
    if r["cantidad"] <= 0:
        return 0
    return math.ceil(r["cantidad"] / max(1, int(c.get("unidades_por_empaque") or 1)))


def costo(r: dict, c: dict) -> int:
    return (c["precio_cop"] or 0) * unidades(r, c)


def admisibles(r: dict) -> list[dict]:
    return [c for c in r["candidatos"] if c["cumple"]] or list(r["candidatos"])


def decidibles(inst: dict) -> list[dict]:
    return [
        r
        for r in inst["renglones"]
        if not (r["tipo_item"] in INFORMATIVOS or r["modo_adquisicion"] not in SURTIBLES) and admisibles(r)
    ]


def pesos(n: int) -> str:
    return f"${n:,}".replace(",", ".")


def describir(r: dict, c: dict) -> str:
    marca = f", marca {c['marca']}" if c.get("marca") else ""
    pj = f", personaje {c['personaje']}" if c.get("personaje") else ""
    return f"{c['nombre']}{marca}, marca de nivel {c['nivel']}, {pesos(costo(r, c))} por {unidades(r, c)} unidad(es){pj}"


def criterios(r: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Opciones de una linea: {letra: descripcion} y {letra: sku}."""
    adm = admisibles(r)
    return ({LETRAS[i]: describir(r, c) for i, c in enumerate(adm)}, {LETRAS[i]: c["sku"] for i, c in enumerate(adm)})


def instruccion(esc: dict) -> str:
    e = esc["escenario"]
    if e == "ahorrador":
        return "El papa quiere el kit mas barato posible. ¿Cual opcion cuesta menos?"
    if e == "premium":
        return (
            "El papa quiere la mejor calidad de marca. ¿Cual opcion es de la marca de mejor nivel "
            "(premium mejor que confiable, confiable mejor que economico)? Si empatan, la mas barata."
        )
    if e == "fan":
        p = esc["personaje"]
        return f"El papa pidio productos de {p}. ¿Cual opcion trae el personaje {p}? Si ninguna lo trae, la mas barata."
    return (
        f"El papa tiene un presupuesto de {pesos(esc['presupuesto'])} para todo el kit. "
        "Elige la opcion de mejor nivel de marca que no haga pasar el kit del presupuesto."
    )


def renglon_txt(r: dict) -> str:
    return f"Renglon de la lista escolar: {r['texto']} (cantidad pedida {r['cantidad']})"


# ------------------------------------------------------------- modalidades


def _elige(respuesta: dict, qid: str, skus: dict[str, str]) -> tuple[str, float]:
    a = respuesta["answers"][qid]
    letra = a.get("choice")
    conf = float(a.get("answer_confidence", a.get("confidence", 0.0)) or 0.0)
    return skus.get(letra, next(iter(skus.values()))), conf


def modalidad_a(agente, inst, esc):
    asign, confs = {}, []
    for r in decidibles(inst):
        crit, skus = criterios(r)
        if len(crit) == 1:
            asign[str(r["orden"])] = next(iter(skus.values()))
            continue
        resp = agente.predict(renglon_txt(r), {"q": {"type": "choice", "instructions": instruccion(esc), "criteria": crit}})
        asign[str(r["orden"])], c = _elige(resp, "q", skus)
        confs.append(c)
    return asign, confs


def _lista_txt(dec: list[dict], esc: dict) -> str:
    partes = []
    if esc["escenario"] == "presupuesto":
        partes.append(f"Presupuesto total del kit: {pesos(esc['presupuesto'])}.")
    if esc["escenario"] == "fan":
        partes.append(f"Personaje pedido: {esc['personaje']}.")
    partes.append("Lista escolar con las opciones de cada renglon:")
    for r in dec:
        crit, _ = criterios(r)
        ops = " | ".join(f"{k}) {v}" for k, v in crit.items())
        partes.append(f"L{r['orden']}: {r['texto']} x{r['cantidad']} -> {ops}")
    return "\n".join(partes)


def modalidad_b(agente, inst, esc):
    dec = decidibles(inst)
    estado = _lista_txt(dec, esc)
    asign, confs = {}, []
    pendientes = []
    for r in dec:
        crit, skus = criterios(r)
        if len(crit) == 1:
            asign[str(r["orden"])] = next(iter(skus.values()))
        else:
            pendientes.append((r, crit, skus))
    # Laya repite el estado por cada pregunta de la pasada: con listas de miles de
    # tokens, 8 preguntas por pasada no caben en 6 GB. La tanda se ajusta al largo.
    tokens = len(agente.tok(estado)["input_ids"])
    por_pasada = max(1, min(PREGUNTAS_POR_PASADA, TOKENS_POR_PASADA // max(1, tokens)))
    for i in range(0, len(pendientes), por_pasada):
        tanda = pendientes[i : i + por_pasada]
        qs = {
            f"L{r['orden']}": {
                "type": "choice",
                "instructions": f"Para el renglon L{r['orden']} ({r['texto']}): {instruccion(esc)}",
                "criteria": crit,
            }
            for r, crit, _ in tanda
        }
        resp = agente.predict(estado, qs, max_len=8192, head_max_len=1024)
        for r, _crit, skus in tanda:
            asign[str(r["orden"])], c = _elige(resp, f"L{r['orden']}", skus)
            confs.append(c)
    return asign, confs


def modalidad_c(agente, inst, esc):
    dec = decidibles(inst)
    tope = esc.get("presupuesto")
    minimos = [min(costo(r, c) for c in admisibles(r)) for r in dec]
    gastado = 0
    asign, confs = {}, []
    for i, r in enumerate(dec):
        crit, skus = criterios(r)
        if len(crit) == 1:
            sku = next(iter(skus.values()))
        else:
            faltan = len(dec) - i - 1
            minimo_resto = sum(minimos[i + 1 :])
            contexto = ""
            if tope is not None:
                contexto = (
                    f"Presupuesto total {pesos(tope)}. Ya se gastaron {pesos(gastado)}, quedan {pesos(tope - gastado)}. "
                    f"Despues de este faltan {faltan} renglones que cuestan como minimo {pesos(minimo_resto)}. "
                )
                instr = (
                    "Elige la opcion de mejor nivel de marca cuyo precio deje dinero suficiente "
                    "para los renglones que faltan."
                )
            else:
                instr = instruccion(esc)
            resp = agente.predict(
                contexto + renglon_txt(r), {"q": {"type": "choice", "instructions": instr, "criteria": crit}}
            )
            sku, c = _elige(resp, "q", skus)
            confs.append(c)
        asign[str(r["orden"])] = sku
        elegido = next(c for c in admisibles(r) if c["sku"] == sku)
        gastado += costo(r, elegido)
    return asign, confs


def kits_por_reglas(dec: list[dict], personaje: str | None) -> list[dict]:
    """5 kits armados con reglas simples, sin NSGA-II.

    Barato por linea; Premium por linea; y tres intermedios que suben de nivel
    las lineas en orden de menor costo extra por nivel ganado (25/50/75 % de las
    subidas posibles). Si hay personaje pedido, el Fan reemplaza al 75 %.
    """
    barato = {str(r["orden"]): min(admisibles(r), key=lambda c: (costo(r, c), -rango(c))) for r in dec}
    premium = {str(r["orden"]): min(admisibles(r), key=lambda c: (-rango(c), costo(r, c))) for r in dec}
    pasos = []
    for r in dec:
        actual = barato[str(r["orden"])]
        for c in sorted(admisibles(r), key=rango):
            if rango(c) > rango(actual):
                pasos.append(((costo(r, c) - costo(r, actual)) / (rango(c) - rango(actual)), str(r["orden"]), c))
                actual = c
    pasos.sort(key=lambda t: t[0])
    kits = [{"nombre": "barato", "elec": barato}]
    for frac in (0.25, 0.5, 0.75):
        elec = dict(barato)
        for _, orden, c in pasos[: int(len(pasos) * frac)]:
            if rango(c) > rango(elec[orden]):
                elec[orden] = c
        kits.append({"nombre": f"intermedio_{int(frac * 100)}", "elec": elec})
    kits.append({"nombre": "premium", "elec": premium})
    if personaje:
        fan = {
            str(r["orden"]): min(
                admisibles(r),
                key=lambda c: (not (c.get("personaje") or "").lower() == personaje.lower(), costo(r, c)),
            )
            for r in dec
        }
        kits[3] = {"nombre": "fan", "elec": fan}
    return kits


def modalidad_d(agente, inst, esc):
    dec = decidibles(inst)
    personaje = esc.get("personaje")
    kits = kits_por_reglas(dec, personaje)
    por_orden = {str(r["orden"]): r for r in dec}
    crit = {}
    for i, k in enumerate(kits):
        total = sum(costo(por_orden[o], c) for o, c in k["elec"].items())
        nivel = sum(rango(c) for c in k["elec"].values()) / max(1, len(k["elec"]))
        txt = f"Kit {i + 1}: total {pesos(total)}, nivel de marca promedio {nivel:.2f} de 2"
        if personaje:
            n = sum(1 for c in k["elec"].values() if (c.get("personaje") or "").lower() == personaje.lower())
            txt += f", {n} productos de {personaje}"
        crit[LETRAS[i]] = txt
    pregunta = {
        "ahorrador": "El papa quiere el kit mas barato. ¿Cual kit cuesta menos?",
        "premium": "El papa quiere la mejor calidad. ¿Cual kit tiene el nivel de marca promedio mas alto?",
        "fan": f"El papa pidio {personaje}. ¿Cual kit trae mas productos de {personaje}?",
        "presupuesto": (
            f"El papa tiene {pesos(esc.get('presupuesto') or 0)} de presupuesto. "
            "¿Cual kit tiene el nivel de marca mas alto sin pasarse del presupuesto?"
        ),
    }[esc["escenario"]]
    resp = agente.predict(
        f"Kits armados para la lista {inst['id']} ({len(dec)} renglones a comprar).",
        {"q": {"type": "choice", "instructions": pregunta, "criteria": crit}},
    )
    a = resp["answers"]["q"]
    i = LETRAS.index(a["choice"]) if a.get("choice") in LETRAS[: len(kits)] else 0
    conf = float(a.get("answer_confidence", a.get("confidence", 0.0)) or 0.0)
    return {o: c["sku"] for o, c in kits[i]["elec"].items()}, [conf]


MODALIDADES = {"A": modalidad_a, "B": modalidad_b, "C": modalidad_c, "D": modalidad_d}


def _recargar(lib, modelo: str):
    import gc

    import torch

    gc.collect()
    torch.cuda.empty_cache()
    agente = lib.load(modelo)
    agente.predict("calentamiento", {"q": {"type": "noul", "instructions": "¿si?"}})
    return agente


def main() -> int:
    import laya

    lib_laya = laya

    ap = argparse.ArgumentParser()
    ap.add_argument("modalidades", nargs="*", default=["A", "B", "C", "D"])
    ap.add_argument("--modelo", default="typed-decisions")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--sufijo", default="")
    args = ap.parse_args()

    instancias = {i["id"]: i for i in json.loads((CARPETA / "instancias.json").read_text(encoding="utf-8"))["instancias"]}
    escenarios = json.loads((CARPETA / "escenarios.json").read_text(encoding="utf-8"))["escenarios"]
    if args.limite:
        ids = sorted({e["instancia"] for e in escenarios})[: args.limite]
        escenarios = [e for e in escenarios if e["instancia"] in ids]

    agente = laya.load(args.modelo)
    agente.predict("calentamiento", {"q": {"type": "noul", "instructions": "¿si?"}})
    for m in args.modalidades:
        # Avance fila por fila en un .jsonl: una corrida cortada se retoma donde quedo.
        avance = CARPETA / f"laya_{m}{args.sufijo}.avance.jsonl"
        filas = []
        if avance.exists():
            filas = [json.loads(l) for l in avance.read_text(encoding="utf-8").splitlines() if l.strip()]
        hechos = {(f["instancia"], f["escenario"]) for f in filas}
        t0 = time.perf_counter()
        for n, esc in enumerate(escenarios, 1):
            if (esc["instancia"], esc["escenario"]) in hechos:
                continue
            inst = instancias[esc["instancia"]]
            t = time.perf_counter()
            try:
                asign, confs = MODALIDADES[m](agente, inst, esc)
                error = None
            except Exception as exc:  # una falla de Laya en una lista se registra, no tumba la corrida
                # Una falta de memoria en GPU deja al agente con tensores repartidos entre
                # CPU y GPU y todo lo que sigue falla; se recarga y se reintenta una vez
                # con tandas mas chicas.
                error = f"{type(exc).__name__}: {exc}"[:300]
                agente = _recargar(lib_laya, args.modelo)
                global PREGUNTAS_POR_PASADA
                previas, PREGUNTAS_POR_PASADA = PREGUNTAS_POR_PASADA, 1
                try:
                    asign, confs = MODALIDADES[m](agente, inst, esc)
                    error = None
                except Exception as exc2:
                    asign, confs, error = {}, [], f"{error} | reintento: {type(exc2).__name__}: {exc2}"[:400]
                    agente = _recargar(lib_laya, args.modelo)
                finally:
                    PREGUNTAS_POR_PASADA = previas
            fila = {
                "instancia": esc["instancia"],
                "escenario": esc["escenario"],
                "modalidad": m,
                "asignacion": asign,
                "confianza_media": round(sum(confs) / len(confs), 4) if confs else None,
                "preguntas": len(confs),
                "segundos": round(time.perf_counter() - t, 4),
                "error": error,
            }
            filas.append(fila)
            if fila["segundos"] > 30 or error:
                print(f"  lento/error {esc['instancia']} {esc['escenario']}: {fila['segundos']:.0f}s {error}", flush=True)
            with avance.open("a", encoding="utf-8") as f:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            if n % 100 == 0:
                print(f"  {m}: {n}/{len(escenarios)} en {time.perf_counter() - t0:.0f}s", flush=True)
        salida = CARPETA / f"laya_{m}{args.sufijo}.json"
        salida.write_text(
            json.dumps({"modelo": args.modelo, "modalidad": m, "filas": filas}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        errores = sum(1 for f in filas if f["error"])
        print(f"{m}: {len(filas)} filas, {errores} errores, {time.perf_counter() - t0:.0f}s -> {salida.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
