"""Foto de cifras, macros \\cal*, citas y refs del cuerpo. Uso: cifras.py snapshot > x.json | cifras.py diff x.json"""
import json, re, sys, collections, pathlib
B = pathlib.Path(__file__).resolve().parents[2] / "sections"
F = "introduccion descripcionGeneral contextoProyecto analisisProblema disenoSolucion desarrolloSolucion optimizacion nl2c resultados calidad oe5 conclusiones covers/abstract_resumen".split()
def foto():
    out = {}
    for f in F:
        t = re.sub(r"(?m)(?<!\\)%.*$", "", (B / f"{f}.tex").read_text(encoding="utf-8"))
        c = collections.Counter()
        c.update("n:" + m for m in re.findall(r"(?<![\w\\])\d+(?:[.,]\d+)*", t))
        c.update("m:" + m for m in re.findall(r"\\cal[A-Za-z]+", t))
        for ks in re.findall(r"\\cite[pt]?\{([^}]*)\}", t): c.update("c:" + k.strip() for k in ks.split(","))
        c.update("r:" + m for m in re.findall(r"\\ref\{([^}]*)\}", t))
        out[f] = dict(c)
    return out
if sys.argv[1] == "snapshot": print(json.dumps(foto(), ensure_ascii=False))
else:
    a, b = json.load(open(sys.argv[2])), foto()
    tot = lambda d: sum((collections.Counter(v) for v in d.values()), collections.Counter())
    ta, tb = tot(a), tot(b)
    perd = {k: ta[k] - tb[k] for k in ta if ta[k] > tb[k]}
    nuev = {k: tb[k] - ta[k] for k in tb if tb[k] > ta[k]}
    print("DESAPARECEN DEL CUERPO:", sorted(k for k in perd if k not in tb))
    print("NUEVAS EN EL CUERPO:", sorted(k for k in nuev if k not in ta))
    print("menos apariciones:", len(perd), "| más apariciones:", len(nuev))
