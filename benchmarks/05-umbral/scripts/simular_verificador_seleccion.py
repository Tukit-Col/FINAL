"""Paso 5 — Prueba si un LLM puede ELEGIR el candidato correcto del pool
(no solo decir sí/no sobre el top-1), usando batching para ahorrar llamadas.

Contexto: calibration/simular_verificador.py midió un verificador binario
(¿el top-1 es razonable?) sobre los 354 ítems que hoy se auto-resuelven a
τ=0.630 -- 59.6% de recall sobre los 47 "mal elegidos", solo 3.4% de falsos
positivos. Pero ese verificador solo FILTRA: si dice "no", el ítem se pierde
y va a un humano, incluso en los 27 de esos 47 casos donde el producto
correcto SÍ estaba en el pool de 5 candidatos (el reranker solo lo puso en
la posición equivocada).

Este script prueba una versión más ambiciosa: darle al LLM el pool COMPLETO
(los 5 candidatos que trae Stage 2, no solo el top-1) y que ELIJA cuál es
el correcto, o diga "ninguno" si de verdad no hay ninguno bueno. Si funciona,
esos 27 casos se recuperan automáticamente en vez de perderse.

Para no volver a chocar límites de la API (ver docs/adr o la conversación:
15 peticiones/min y 500/día en el free tier), este script agrupa varios
ítems por llamada (batching) -- baja de ~354 llamadas a ~35-70, según el
tamaño de lote.

Métricas, sobre los 354 ítems (cada uno con sus 5 candidatos reales):

    Población con correcto en el pool (334 ítems, los que NO son "hueco de
    catálogo"):
        ACIERTO DE SELECCIÓN   LLM elige el candidato marcado es_correcto=1
        ELIGIÓ MAL             LLM elige un candidato incorrecto (tan malo
                                como hoy, pero ahora "bendecido" por el LLM)
        DIJO "NINGUNO" DE MÁS  LLM se niega a elegir aunque sí había uno
                                bueno -- pierde cobertura sin necesidad

    Población SIN correcto en el pool (20 ítems, hueco real de catálogo):
        DIJO "NINGUNO" BIEN    LLM reconoce que no hay nada bueno (correcto)
        ELIGIÓ ALGO IGUAL      LLM fuerza una elección donde no debía (malo)

Se compara contra la línea base de hoy: 307/354 = 86.7% de precisión con
100% de cobertura (ningún filtro).

Uso:
    python calibration/simular_verificador_seleccion.py                    # los 354, lote de 10
    python calibration/simular_verificador_seleccion.py --lote 5           # lote más chico
    python calibration/simular_verificador_seleccion.py --muestra-items 40 # prueba rápida y barata
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO, format="  [reintento] %(message)s", stream=sys.stdout)
_log = logging.getLogger("verificador_seleccion")

BASE = Path(__file__).resolve().parent
load_dotenv(BASE.parent / ".env")

CSV_ENTRADA = BASE / "gold_standard_final.csv"
SALIDA = BASE / "verificador_seleccion_resultados.csv"

TAU = 0.630
# Gemini 3.5 Flash Lite llegó a 416/500 peticiones del día (ver captura del
# usuario) -- se usa 3.1 Flash Lite, mismo nivel "Lite", cupo diario sin
# tocar hoy (0/500), mismo límite de 15/min.
MODEL_NAME = os.environ.get("GEMINI_MODEL_SELECCION", "gemini-3.1-flash-lite")
PETICIONES_POR_MINUTO = 14
ESPACIADO_SEGUNDOS = 60.0 / PETICIONES_POR_MINUTO
LETRAS = "ABCDE"

# v2 -- la v1 medía 96.0% de acierto cuando SÍ había un candidato correcto,
# pero solo reconocía el caso "ninguno corresponde" el 33.3% de las veces
# (12/18 ítems sin candidato bueno, el LLM igual forzaba una elección). Esta
# versión insiste explícitamente en que "ninguno" es una respuesta normal y
# esperada, con un ejemplo concreto, en vez de dejarlo como último recurso.
PROMPT_SISTEMA = """Eres un verificador de compras para una tienda de útiles \
escolares en Colombia. Te doy una LISTA de pedidos. Para cada uno, el pedido \
del padre y los candidatos de producto que el sistema encontró en el catálogo.

Para CADA pedido, elige la LETRA del candidato que mejor corresponde al \
pedido. Si NINGÚN candidato corresponde razonablemente, responde "ninguno" \
para ese pedido — es una respuesta VÁLIDA y ESPERADA en varios casos, no un \
último recurso. El catálogo no tiene todo; muchas veces la búsqueda trae \
solo productos parecidos, no lo que realmente se pidió.

Sé permisivo con diferencias de marca, color o presentación que el pedido no \
especificó — eso es normal y aceptable. Pero responde "ninguno" si:
  - ningún candidato es del TIPO de producto pedido (p. ej. pidieron
    cartuchera y todos los candidatos son mochilas), o
  - una restricción explícita del pedido (tamaño, cantidad, material, color
    específico) no se cumple en NINGÚN candidato, o
  - todos los candidatos son de una categoría distinta a lo pedido, aunque
    compartan alguna palabra con el pedido.

Antes de elegir una letra, pregúntate: "¿ESTE candidato es de verdad lo que \
el padre pidió, o solo es lo más parecido que había disponible?". Si es solo \
lo más parecido pero no calza con lo pedido, responde "ninguno".

Ejemplo: pedido "vinilo de color neón" con candidatos que son solo vinilos \
de colores comunes (rojo, azul, verde), sin ninguna opción neón -> "ninguno", \
aunque todos sean vinilos del tipo correcto de producto.

Responde SOLO con un JSON, sin texto adicional, mapeando cada id de pedido a \
su respuesta:
{"<id>": "<letra o 'ninguno'>", "<id>": "<letra o 'ninguno'>", ...}
"""


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(_log, logging.INFO),
)
def _llamar_gemini(contenido: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[contenido],
        config=types.GenerateContentConfig(
            system_instruction=PROMPT_SISTEMA,
            temperature=0.0,
            max_output_tokens=800,
        ),
    )
    return response.text or ""


def _construir_prompt_lote(items: list[dict]) -> str:
    bloques = []
    for it in items:
        lineas = [f'[{it["item_id"]}] Pedido: "{it["descripcion"]}"']
        for letra, cand in zip(LETRAS, it["pool"]):
            lineas.append(f'  {letra}) {cand["nombre_producto"]} (marca: {cand["marca"] or "sin marca"})')
        bloques.append("\n".join(lineas))
    return "\n\n".join(bloques)


def _parsear_respuesta_lote(texto: str, ids_esperados: list[str]) -> dict[str, str | None]:
    match = re.search(r"\{[\s\S]*\}", texto)
    if not match:
        return {i: None for i in ids_esperados}
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {i: None for i in ids_esperados}
    resultado = {}
    for i in ids_esperados:
        val = data.get(i)
        if isinstance(val, str) and (val.strip().upper() in LETRAS or val.strip().lower() == "ninguno"):
            resultado[i] = val.strip().upper() if val.strip().upper() in LETRAS else "ninguno"
        else:
            resultado[i] = None  # no vino en la respuesta o valor no reconocible
    return resultado


_CAMPOS_CSV = ["item_id", "descripcion", "letra_elegida", "sku_elegido", "es_correcto_elegido",
               "hay_correcto_en_pool", "sin_match", "raw_error", "segundos_lote", "lote_idx"]


async def _procesar_lote(lote_idx: int, items: list[dict], escritor: csv.DictWriter, archivo) -> None:
    ids = [it["item_id"] for it in items]
    contenido = _construir_prompt_lote(items)
    t0 = time.monotonic()
    try:
        texto = await asyncio.to_thread(_llamar_gemini, contenido)
        elecciones = _parsear_respuesta_lote(texto, ids)
        error = None
    except Exception as exc:  # noqa: BLE001
        elecciones = {i: None for i in ids}
        error = str(exc)
    segundos = time.monotonic() - t0

    for it in items:
        letra = elecciones.get(it["item_id"])
        hay_correcto = any(c["es_correcto"] == 1 for c in it["pool"])
        if letra in (None, "ninguno"):
            sku_elegido = None
            es_correcto_elegido = None
        else:
            cand = it["pool"][LETRAS.index(letra)]
            sku_elegido = cand["sku"]
            es_correcto_elegido = bool(cand["es_correcto"])

        fila = {
            "item_id": it["item_id"], "descripcion": it["descripcion"],
            "letra_elegida": letra if letra is not None else "ERROR",
            "sku_elegido": sku_elegido or "", "es_correcto_elegido": es_correcto_elegido,
            "hay_correcto_en_pool": hay_correcto, "sin_match": it["sin_match"],
            "raw_error": error or "", "segundos_lote": round(segundos, 1), "lote_idx": lote_idx,
        }
        escritor.writerow(fila)

        estado = "ERROR" if letra is None else ("ninguno" if letra == "ninguno" else f"{letra}->{'OK' if es_correcto_elegido else 'MAL'}")
        print(f"    {it['item_id'][:8]} {it['descripcion'][:35]!r:<37} -> {estado}", flush=True)
    archivo.flush()


async def _correr(lotes: list[list[dict]], escritor: csv.DictWriter, archivo) -> None:
    total = len(lotes)
    for i, lote in enumerate(lotes, 1):
        print(f"  [lote {i}/{total}] ({len(lote)} ítems)", flush=True)
        await _procesar_lote(i, lote, escritor, archivo)
        if i < total:
            await asyncio.sleep(ESPACIADO_SEGUNDOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", type=int, default=10, help="Ítems por llamada (batching)")
    ap.add_argument("--muestra-items", type=int, default=None,
                     help="Probar solo sobre una muestra aleatoria de N ítems (prueba rápida/barata)")
    ap.add_argument("--solo-huecos", action="store_true",
                     help="Probar SOLO los ítems sin candidato correcto en el pool (hueco de catálogo) "
                          "-- para validar el ajuste del prompt sin gastar cupo en los 322 ya validados")
    args = ap.parse_args()

    df = pd.read_csv(CSV_ENTRADA)
    df["marca"] = df["marca"].fillna("")

    top1 = df[df["rank_rerank"] == 1]
    ids_poblacion = top1[top1["rerank_score"] >= TAU]["item_id"].tolist()
    print(f"Población auto-resuelta a τ={TAU}: {len(ids_poblacion)} ítems")

    global SALIDA
    if args.solo_huecos:
        con_hueco = df[df["item_id"].isin(ids_poblacion) & (df["sin_match"] == 1)]["item_id"].unique().tolist()
        ids_poblacion = con_hueco
        print(f"Filtrando a solo huecos de catálogo: {len(ids_poblacion)} ítems")
        SALIDA = BASE / "verificador_seleccion_v2_huecos.csv"

    if args.muestra_items:
        import random
        random.seed(42)
        ids_poblacion = random.sample(ids_poblacion, min(args.muestra_items, len(ids_poblacion)))
        print(f"Usando muestra de {len(ids_poblacion)} ítems")

    items = []
    for item_id in ids_poblacion:
        filas = df[df["item_id"] == item_id].sort_values("rank_rerank").to_dict("records")
        items.append({
            "item_id": item_id, "descripcion": filas[0]["descripcion"], "sin_match": bool(filas[0]["sin_match"]),
            "pool": [{"nombre_producto": f["nombre_producto"], "marca": f["marca"],
                      "sku": f["sku"], "es_correcto": f["es_correcto"]} for f in filas],
        })

    lotes = [items[i:i + args.lote] for i in range(0, len(items), args.lote)]
    minutos_estimados = len(lotes) / PETICIONES_POR_MINUTO
    print(f"Modelo: {MODEL_NAME} | {len(items)} ítems en {len(lotes)} lotes de hasta {args.lote} "
          f"| ~{minutos_estimados:.1f} min estimados", flush=True)

    with open(SALIDA, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=_CAMPOS_CSV)
        escritor.writeheader()
        archivo.flush()
        asyncio.run(_correr(lotes, escritor, archivo))

    print(f"\nResultados guardados en: {SALIDA}")

    out = pd.read_csv(SALIDA)
    errores = out[out["letra_elegida"] == "ERROR"]
    validos = out[out["letra_elegida"] != "ERROR"]
    if len(errores):
        print(f"  ({len(errores)} ítems con error de llamada/parseo, excluidos de las métricas)")

    con_correcto = validos[validos["hay_correcto_en_pool"] == True]  # noqa: E712
    sin_correcto = validos[validos["hay_correcto_en_pool"] == False]  # noqa: E712

    acierto = (con_correcto["es_correcto_elegido"] == True).sum()  # noqa: E712
    elige_mal = con_correcto["letra_elegida"].isin(list(LETRAS)) & (con_correcto["es_correcto_elegido"] == False)  # noqa: E712
    elige_mal = elige_mal.sum()
    ninguno_de_mas = (con_correcto["letra_elegida"] == "ninguno").sum()

    ninguno_bien = (sin_correcto["letra_elegida"] == "ninguno").sum()
    elige_igual = sin_correcto["letra_elegida"].isin(list(LETRAS)).sum()

    print(f"\n=== Población CON correcto en el pool: {len(con_correcto)} ítems ===")
    print(f"  ✔ acierto de selección:      {acierto} ({acierto/len(con_correcto):.1%})" if len(con_correcto) else "")
    print(f"  ✘ eligió mal:                {elige_mal} ({elige_mal/len(con_correcto):.1%})" if len(con_correcto) else "")
    print(f"  ✘ dijo 'ninguno' de más:     {ninguno_de_mas} ({ninguno_de_mas/len(con_correcto):.1%})" if len(con_correcto) else "")

    print(f"\n=== Población SIN correcto en el pool (hueco catálogo): {len(sin_correcto)} ítems ===")
    print(f"  ✔ dijo 'ninguno' (bien):     {ninguno_bien} ({ninguno_bien/len(sin_correcto):.1%})" if len(sin_correcto) else "")
    print(f"  ✘ eligió algo de todas formas: {elige_igual} ({elige_igual/len(sin_correcto):.1%})" if len(sin_correcto) else "")

    auto_resueltos_nuevo = acierto + elige_mal + elige_igual
    precision_nueva = acierto / auto_resueltos_nuevo if auto_resueltos_nuevo else float("nan")
    cobertura_nueva = auto_resueltos_nuevo / len(validos) if len(validos) else float("nan")

    print(f"\n=== Comparación contra la línea base (top-1 sin verificador) ===")
    print(f"  Hoy (sin verificador):     cobertura 100.0% | precisión 86.7% (307/354)")
    print(f"  Con selección del LLM:     cobertura {cobertura_nueva:.1%} | precisión {precision_nueva:.1%} "
          f"({acierto}/{auto_resueltos_nuevo})")


if __name__ == "__main__":
    main()
