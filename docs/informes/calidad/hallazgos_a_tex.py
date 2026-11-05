"""Genera la tabla de hallazgos abiertos del anexo desde hallazgos_qa.csv.

hallazgos_qa.csv sale de leer, sin ejecutar, las pruebas xfail(strict=True) de la rama
a/fases-2-6-oe5 (corrida de QA del 4-nov-2026): cada reason empieza por el ID del hallazgo.
Uso: python docs/informes/calidad/hallazgos_a_tex.py > docs/memoria/sections/anexo_hallazgos_tabla.tex
"""
import csv, re
from pathlib import Path

CAR = {  # ID -> característica ISO/IEC 25010
    **{k: "Seguridad" for k in "H-C-06 H-C-07 H-C-08 H-C-09 H-C-15 H-A-03 H-A-04 H-A-34 H-A-37 H-A-43 H-A-49 H-A-65 H-A-17 H-A-51".split()},
    **{k: "Fiabilidad" for k in "H-A-02 H-A-24 H-A-26 H-A-29 H-A-33 H-A-54 H-A-55 H-A-56 H-A-57 H-A-58 H-A-48 H-A-41".split()},
    **{k: "Mantenibilidad" for k in "H-C-13 H-A-05 H-A-31 H-A-36".split()},
    **{k: "Privacidad (adecuación legal)" for k in "H-A-14 H-A-15 H-A-16 H-A-66 H-A-67".split()},
}
ORDEN = ["Seguridad", "Privacidad (adecuación legal)", "Fiabilidad", "Adecuación funcional", "Mantenibilidad"]

def tex(s):
    s = re.sub(r"^H-[AC]-\d+:\s*", "", s)
    s = re.sub(r"\s*\([^)]*\.py[^)]*\)", "", s)  # quita referencias a archivo:linea
    s = s if len(s) <= 150 else s[:147].rsplit(" ", 1)[0] + "\\ldots"
    for a, b in [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"), ("`", ""), ("~", "\\~{}")]:
        if a == "\\" and "\\ldots" in s:
            s = s.replace("\\ldots", "@@L@@")
        s = s.replace(a, b)
    return s.replace("@@L@@", "\\ldots")

filas = list(csv.DictReader(open(Path(__file__).with_name("hallazgos_qa.csv"))))
print("% Generado por docs/informes/calidad/hallazgos_a_tex.py; no editar a mano.")
print("\\begin{longtable}{@{}p{1.3cm}p{13.2cm}@{}}")
print(f"\\caption{{Hallazgos abiertos de la corrida de QA del 4 de noviembre de 2026 ({len(filas)} hallazgos, cada uno fijado por una prueba que falla mientras el defecto exista).}}\\label{{tab:hallazgos-abiertos}}\\\\")
print("\\toprule ID & Qué falla \\\\ \\midrule \\endfirsthead")
print("\\toprule ID & Qué falla \\\\ \\midrule \\endhead")
for c in ORDEN:
    grupo = [f for f in filas if CAR.get(f["id"], "Adecuación funcional") == c]
    print(f"\\multicolumn{{2}}{{@{{}}l}}{{\\textbf{{{c}}} ({len(grupo)})}} \\\\")
    for f in grupo:
        print(f"{f['id']} & {tex(f['motivo'])} \\\\")
print("\\bottomrule\n\\end{longtable}")
