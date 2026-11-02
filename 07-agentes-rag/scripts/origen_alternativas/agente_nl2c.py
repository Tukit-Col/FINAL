"""
Enfoque con AGENTE: un LLM (gpt-4o-mini) con function-calling que razona
sobre la solicitud, usa una herramienta de búsqueda en el catálogo para
aterrizar cada ítem (y desambiguar sinónimos), detecta restricciones y
entrega la lista estructurada con una herramienta de terminación.

Patrón de agente: loop autónomo "pensar → actuar → observar" con memoria de
mensajes; el agente decide cuándo terminar.
"""
import json
import os
import time

PRECIO_INPUT = 0.15   # USD por 1M tokens (gpt-4o-mini)
PRECIO_OUTPUT = 0.60  # USD por 1M tokens

SISTEMA = """Eres el agente de Tukit, una plataforma de compra de útiles escolares en Colombia.
El padre te escribe su lista de útiles en lenguaje natural. Tu trabajo:
1) Identifica CADA ítem mencionado con su cantidad, usando la herramienta buscar_producto
   para encontrar los productos del catálogo que correspondan (los nombres del catálogo
   pueden diferir de lo que escribe el padre: "esfero"/"bolígrafo" es "lapicero", etc.).
2) Detecta restricciones: exclusión de marcas ("sin marca X", "nada de la marca X",
   "sin marca genérica"), presupuesto ("presupuesto máximo de $150000", "no más de $X"),
   categoría preferida ("de preferencia en cuadernos").
3) Cuando estés seguro, llama a entregar_lista con los ítems (id_producto del catálogo,
   NO el nombre) y las restricciones detectadas.
Reglas: no inventes productos que no existan en el catálogo; si una descripción es
ambigua, usa buscar_producto para comparar candidatos y elige el más razonable.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_producto",
            "description": "Busca productos del catálogo de útiles escolares que coincidan con una descripción. Devuelve hasta 3 candidatos con id, nombre, categoría, marca y precio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descripcion": {"type": "string", "description": "Descripción del ítem buscado, p. ej. 'cuaderno cuadriculado' o 'esfero azul'."},
                },
                "required": ["descripcion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "entregar_lista",
            "description": "Termina la tarea entregando la lista estructurada de ítems (con ids del catálogo) y las restricciones detectadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id_producto": {"type": "string"},
                                "cantidad": {"type": "integer"},
                            },
                            "required": ["id_producto", "cantidad"],
                        },
                    },
                    "exclusion_marcas": {"type": "array", "items": {"type": "string"}},
                    "precio_max": {"type": "number"},
                    "precio_min": {"type": "number"},
                    "categoria": {"type": "string"},
                },
                "required": ["items"],
            },
        },
    },
]


class AgenteNL2C:
    def __init__(self, catalogo_lexico, modelo: str = "gpt-4o-mini",
                 api_key: str | None = None, max_iteraciones: int = 8) -> None:
        from openai import OpenAI
        self.catalogo = catalogo_lexico
        self.modelo = modelo
        self.max_iteraciones = max_iteraciones
        self._cliente = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def _ejecutar_tool(self, nombre: str, args: dict) -> str:
        if nombre == "buscar_producto":
            resultados = self.catalogo.buscar(args.get("descripcion", ""), k=3)
            return json.dumps(resultados, ensure_ascii=False)
        if nombre == "entregar_lista":
            return json.dumps({"ok": True})
        return json.dumps({"error": f"herramienta desconocida: {nombre}"})

    def resolver(self, texto: str) -> dict:
        """Ejecuta el loop de agente. Devuelve métricas y resultado."""
        mensajes = [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": texto},
        ]
        t0 = time.perf_counter()
        llamadas = 0
        resultado = None
        prompt_tokens = 0
        completion_tokens = 0
        for _ in range(self.max_iteraciones):
            respuesta = self._cliente.chat.completions.create(
                model=self.modelo, messages=mensajes, tools=TOOLS,
                tool_choice="auto",
            )
            if respuesta.usage:
                prompt_tokens += respuesta.usage.prompt_tokens or 0
                completion_tokens += respuesta.usage.completion_tokens or 0
            msg = respuesta.choices[0].message
            if not msg.tool_calls:
                # El agente contestó sin herramienta; fallback a JSON del content.
                try:
                    resultado = json.loads(msg.content)
                except Exception:  # noqa: BLE001
                    resultado = {"items": [], "_sin_herramienta": True}
                mensajes.append({"role": "assistant", "content": msg.content})
                break
            mensajes.append(msg)
            for tc in msg.tool_calls:
                llamadas += 1
                args = json.loads(tc.function.arguments or "{}")
                if tc.function.name == "entregar_lista":
                    resultado = args
                    mensajes.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": json.dumps({"ok": True}),
                    })
                    break
                salida = self._ejecutar_tool(tc.function.name, args)
                mensajes.append({
                    "role": "tool", "tool_call_id": tc.id, "content": salida,
                })
            if resultado is not None:
                break

        total_tokens = prompt_tokens + completion_tokens
        costo = (prompt_tokens / 1e6 * PRECIO_INPUT) + (completion_tokens / 1e6 * PRECIO_OUTPUT)

        return {
            "resultado": resultado or {"items": []},
            "llamadas_tool": llamadas,
            "latencia_s": round(time.perf_counter() - t0, 3),
            "tokens": {"prompt": prompt_tokens, "completion": completion_tokens,
                       "total": total_tokens},
            "costo_usd": round(costo, 5),
        }
