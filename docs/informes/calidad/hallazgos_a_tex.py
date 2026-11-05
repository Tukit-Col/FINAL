"""Genera la tabla de hallazgos vigentes del anexo desde el registro oficial del repo Tukit-QA.

Fuente: Tukit-QA/trazabilidad/hallazgos.md (índice), copiado a hallazgos_qa_oficial.csv con
id, título, tipo, severidad y estado. Vigente = estado que no empieza por «cerrado».
Uso: python docs/informes/calidad/hallazgos_a_tex.py > docs/memoria/sections/anexo_hallazgos_tabla.tex
"""
import csv
import re
from collections import Counter
from pathlib import Path

ORDEN = ["alta", "media", "baja"]


def tex(s: str) -> str:
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = s if len(s) <= 140 else s[:137].rsplit(" ", 1)[0] + "@@L@@"
    for a, b in [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"), ("~", "\\~{}")]:
        s = s.replace(a, b)
    return s.replace("@@L@@", "\\ldots")


filas = list(csv.DictReader(open(Path(__file__).with_name("hallazgos_qa_oficial.csv"), encoding="utf-8")))
vig = [f for f in filas if not f["estado"].startswith("cerrado")]
c = Counter(f["id"][:3] for f in vig)
print("% Generado por docs/informes/calidad/hallazgos_a_tex.py; no editar a mano.")
print("\\begin{longtable}{@{}p{1.3cm}p{10.6cm}p{2.6cm}@{}}")
print(f"\\caption{{Hallazgos vigentes del control de calidad al 5 de noviembre de 2026: {len(vig)} ({c['H-C']} H-C, {c['H-A']} H-A y {c['H-B']} H-B), "
      f"más {len(filas) - len(vig)} cerrados. Fuente: registro de hallazgos del repositorio Tukit-QA.}}\\label{{tab:hallazgos-abiertos}}\\\\")
print("\\toprule ID & Hallazgo & Tipo \\\\ \\midrule \\endfirsthead")
print("\\toprule ID & Hallazgo & Tipo \\\\ \\midrule \\endhead")
for sev in ORDEN:
    grupo = [f for f in vig if f["sev"] == sev]
    print(f"\\multicolumn{{3}}{{@{{}}l}}{{\\textbf{{Severidad {sev}}} ({len(grupo)})}} \\\\")
    for f in grupo:
        print(f"{f['id']} & {tex(f['titulo'])} & {tex(f['tipo'])} \\\\")
print("\\bottomrule\n\\end{longtable}")
