"""RAG sin LLM (§8 del REPORTE de Alternativas) sin servidor y con un puntaje estricto.

Corre `scripts/rag_bench.py` tal cual, pero con los embeddings calculados en el
mismo proceso (fastembed + multilingual-e5-large, el mismo modelo que sirve
`kag/embeddings_server.py`) en vez de pedirlos por HTTP al puerto 8081. Despues
vuelve a puntuar la recuperacion con un criterio estricto:

- El puntaje original de precio busca los DIGITOS del oro dentro del texto
  recuperado. Seis de las 16 preguntas tienen oro "$0" (precio no publicado),
  y cualquier contexto que tenga un "0" en algun lado cuenta como acierto. La
  pregunta de disponibilidad (oro "si") pasa igual con cualquier "Disponible: si".
- El criterio estricto exige que el chunk del producto preguntado este entre
  los k recuperados (precio, marca, URL); para el mas barato, que este el chunk
  del producto oro con su precio; para disponibilidad, un chunk de la tienda
  preguntada, de maletas o loncheras, disponible.

    FASTEMBED_CACHE_PATH=... python rag_sin_llm_offline.py <raiz de Isis2610-G19-Tukit-Alternativas>
        -> ../resultados/rag_sin_llm.json
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent / "resultados" / "rag_sin_llm.json"


def _cargar_rag(raiz: Path):
    spec = importlib.util.spec_from_file_location("rag_bench", raiz / "scripts" / "rag_bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def estricto(rag, q, ctx) -> bool:
    n = rag._norm
    tipo = q["tipo"]
    if tipo == "categoria":
        return rag._eval_recuperacion(q, ctx)[0]
    if tipo in ("precio_producto", "marca", "referencia_compra"):
        objetivo = n(f"Producto: {q['producto']}.")
        return any(n(c).startswith(objetivo) for c in ctx)
    if tipo == "min_precio":
        nombre, precio = q["gold"].rsplit("$", 1)
        objetivo = n(f"Producto: {nombre.strip()}.")
        digitos = rag._digitos(precio)
        return any(n(c).startswith(objetivo) and f"precio: {digitos} cop" in n(c) for c in ctx)
    if tipo == "disponibilidad":
        tienda = "panamericana" if "panamericana" in n(q["pregunta"]) else "exito"
        return any(
            f"proveedor: {tienda}" in n(c)
            and "disponible: si" in n(c)
            and re.search(r"categoria: [^.]*(maleter|lonchera|maleta)", n(c))
            for c in ctx
        )
    return rag._eval_recuperacion(q, ctx)[0]


def main() -> int:
    raiz = Path(sys.argv[1]).resolve()
    rag = _cargar_rag(raiz)
    from fastembed import TextEmbedding

    modelo = TextEmbedding(model_name="intfloat/multilingual-e5-large")
    rag._embeddings = lambda textos: [v.tolist() for v in np.asarray(list(modelo.embed(textos)))]
    original = SALIDA.with_name("rag_sin_llm_salida_original.json")
    sys.argv = ["rag_bench.py", "--salida", str(original)]
    rag.main()
    res = json.loads(original.read_text(encoding="utf-8"))
    preguntas = json.loads((raiz / "datos" / "preguntas.json").read_text(encoding="utf-8"))["preguntas"]
    detalle = []
    for q, fila in zip(preguntas, res["detalles"], strict=True):
        detalle.append(
            {
                "tipo": q["tipo"],
                "gold": q["gold"],
                "hit_original": bool(fila["hit_recuperacion"]),
                "hit_estricto": bool(estricto(rag, q, fila["contexto"])),
            }
        )
    oro_cero = [d for d in detalle if d["gold"] == "$0"]
    resumen = {
        "preguntas": len(detalle),
        "hits_original": sum(d["hit_original"] for d in detalle),
        "hits_estricto": sum(d["hit_estricto"] for d in detalle),
        "preguntas_con_oro_cero": len(oro_cero),
        "hits_original_en_oro_cero": sum(d["hit_original"] for d in oro_cero),
        "hits_estricto_en_oro_cero": sum(d["hit_estricto"] for d in oro_cero),
        "tiempo_recuperacion_promedio_s": res["tiempo_recuperacion_promedio_s"],
        "detalle": detalle,
    }
    SALIDA.write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in resumen.items() if k != "detalle"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
