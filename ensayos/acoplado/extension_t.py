"""Extension (fuera del barrido pedido): PD sobre las 5 listas con mas lineas, T mayores, limite 20 s.

uv run python ensayos/acoplado/extension_t.py   (agrega la clave "extension" a resultados.json)
"""
import json
import time

from acoplado import AQUI, Tiempo, pd_exacta, total_de
from comun import cargar_json, decidibles, optimo_ahorrador, renglones_de

inst = {i["id"]: i for i in cargar_json("instancias.json.gz")["instancias"]}
pres = {e["instancia"]: e["presupuesto"] for e in cargar_json("escenarios.json")["escenarios"] if e["escenario"] == "presupuesto"}
grandes = sorted(pres, key=lambda i: -len(decidibles(renglones_de(inst[i]))))[:5]
salida = []
for i in grandes:
    dec = decidibles(renglones_de(inst[i]))
    for T in (12, 16, 24, 32, 64):
        from comun import costo_linea
        from tukit_inteligencia.optimizador import _admisibles
        a = optimo_ahorrador(dec)
        _, tot = total_de(dec, a, T)
        pr = pres[i] + (tot - sum(costo_linea(r, next(c for c in _admisibles(r) if c.sku == a[str(r.orden)])) for r in dec))
        t = time.perf_counter()
        try:
            _, est = pd_exacta(dec, pr, T, limite_s=20.0)
            estado = "ok"
        except Tiempo as e:
            est, estado = int(e.args[0]), "tiempo"
        salida.append({"instancia": i, "lineas": len(dec), "T": T, "estado": estado, "estados": est, "s": round(time.perf_counter() - t, 3)})
        print(salida[-1], flush=True)
ruta = AQUI / "resultados.json"
d = json.loads(ruta.read_text())
d["extension"] = salida
ruta.write_text(json.dumps(d, indent=1, ensure_ascii=False))
