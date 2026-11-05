"""
08_generar_tabla_latex.py
Lee los resultados consolidados de resultados_benchmark_10.json,
calcula las métricas (usando lógica de 06_comparar_enfoques) e inyecta la tabla en seccion_benchmark.tex
"""
import json
import re
from pathlib import Path
import sys

# Importar calcular_prf1 de 06_comparar_enfoques
base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir))
import importlib
comp = importlib.import_module("06_comparar_enfoques")

def evaluar_enfoque_local(resultados_lista):
    return comp.evaluar_enfoque(resultados_lista)

def main():
    gs_path = base_dir.parent / "corpus" / "resultados_benchmark_10.json"
    tex_path = base_dir.parent.parent / "documento_maestro" / "seccion_percepcion.tex"
    if not tex_path.exists():
        tex_path = base_dir.parent.parent / "documento_maestro" / "seccion_benchmark.tex"
    if not tex_path.exists():
        tex_path = base_dir.parent / "seccion_benchmark.tex"

    if not gs_path.exists():
        print(f"No existe {gs_path}")
        return

    with open(gs_path, "r", encoding="utf-8") as f:
        resultados = json.load(f)

    lineas_tabla = []
    
    orden = ["OCR Baseline", "Google Vision", "Baidu GOT-OCR", "Docling", "Gemini (LMM)"]
    privacidad_map = {
        "OCR Baseline": r"\textit{Offline}",
        "Google Vision": "Cloud",
        "Baidu GOT-OCR": r"\textit{Offline}",
        "Docling": r"\textit{Offline}",
        "Gemini (LMM)": "Cloud (\\sim\\$0.002)"
    }
    
    nombres_latex = {
        "OCR Baseline": "OCR Tipográfico y Tesseract",
        "Google Vision": "Google Cloud Vision API",
        "Baidu GOT-OCR": "Baidu GOT-OCR2.0 (Format)",
        "Docling": "Docling Layout Analysis",
        "Gemini (LMM)": "Gemini 3.5 Flash (LMM)"
    }

    for nombre in orden:
        if nombre not in resultados or not resultados[nombre]:
            continue
            
        metricas = evaluar_enfoque_local(resultados[nombre])
        
        p_micro = metricas["micro"]["precision"]
        r_micro = metricas["micro"]["recall"]
        f1_micro = metricas["micro"]["f1"]
        
        p_macro = metricas["macro"]["precision"]
        r_macro = metricas["macro"]["recall"]
        f1_macro = metricas["macro"]["f1"]
        
        lat_p50 = metricas["latencia"]["p50_s"]
        privacidad = privacidad_map[nombre]
        
        fila = f"    {nombres_latex[nombre]} & {p_micro:.3f} & {r_micro:.3f} & {f1_micro:.3f} & {p_macro:.3f} & {r_macro:.3f} & {f1_macro:.3f} & {lat_p50:.2f} & {privacidad} \\\\"
        lineas_tabla.append(fila)

    # Inyectar en LaTeX
    with open(tex_path, "r", encoding="utf-8") as f:
        tex_content = f.read()

    # Buscar el inicio y fin de la tabla
    patron = r"(\\midrule\n).*?(\\bottomrule)"
    # Escapar las diagonales para re.sub
    reemplazo = r"\g<1>" + "\n".join(lineas_tabla).replace("\\", "\\\\") + r"\n    \g<2>"
    
    nuevo_tex = re.sub(patron, reemplazo, tex_content, flags=re.DOTALL)
    
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(nuevo_tex)
        
    print(f"Métricas inyectadas en {tex_path.name} exitosamente.")

if __name__ == "__main__":
    main()
