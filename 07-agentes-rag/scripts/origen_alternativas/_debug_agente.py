import re
import sys

sys.path.insert(0, ".")
from benchmarks.agente_local import AgenteLocalNL2C, SISTEMA_LOCAL
from benchmarks.baseline_actual import CatalogoLexico
from benchmarks.data import generar_catalogo
from benchmarks.nl2c_data import generar_casos

prod = generar_catalogo(semilla=7)
casos = generar_casos(prod, semilla=11)[:1]
cat = CatalogoLexico(prod)
ag = AgenteLocalNL2C(cat, r"C:\Users\DANIEL~1\AppData\Local\Temp\opencode\models\qwen2.5-1.5b-instruct-q4_k_m.gguf")

texto = casos[0]["texto"]
print("CASO:", texto[:120])
print("=" * 60)
mensajes = [
    {"role": "system", "content": SISTEMA_LOCAL},
    {"role": "user", "content": texto},
]
for i in range(5):
    resp = ag._llm.create_chat_completion(messages=mensajes, temperature=0.0, max_tokens=300)
    contenido = (resp["choices"][0]["message"].get("content") or "").strip()
    print(f"--- TURNO {i} ({resp['usage']['total_tokens']} tok) ---")
    print(contenido[:700])
    print()
    mensajes.append({"role": "assistant", "content": contenido})
    acts = re.findall(r'"accion"\s*:\s*"(\w+)"', contenido)
    if "entregar_lista" in acts:
        mensajes.append({"role": "user", "content": "[Validacion fallida]: ids invalidos. Debes llamar buscar_producto. "})
    else:
        mensajes.append({"role": "user", "content": "[Resultado de buscar_producto]: sin resultados validos."})
