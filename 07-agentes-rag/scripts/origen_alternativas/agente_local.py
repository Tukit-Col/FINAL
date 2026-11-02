"""
Enfoque con AGENTE local: la extracción NL2C la hace un LLM y la
recuperación al catálogo la hace una HERRAMIENTA determinista.

Diseño ("plan-then-execute con grounding"):
  1. El agente (LLM) lee el mensaje y produce un ÚNICO JSON con los ítems
     (descripcion + cantidad) y las restricciones. No emite ids.
  2. El orquestador invoca la herramienta `buscar_producto` (el mismo
     CatalogoLexico del enfoque actual) para CADA descripción y resuelve el
     id real del catálogo por top-1. Así es imposible alucinar ids.

Por qué no se usa el loop ReAct multi-turno puro: con Qwen2.5-1.5B
(Q4_K_M) se observó que el modelo emite TODO el plan (varias
buscar_producto + entregar_lista con ids inventados "123456") en un solo
turno y nunca espera los resultados de las herramientas, repitiéndose en
bucle hasta agotar las iteraciones (ver _debug_agente.py). Esa evidencia
queda documentada en el reporte; un modelo frontier sí soporta el
tool-calling multi-turno (ver agente_nl2c.py, requiere API key).

Motor: Qwen2.5-Instruct (Q4_K_M) vía llama-cpp-python en CPU — sin API ni
costo.
"""
import json
import time


SISTEMA_LOCAL = """Eres un asistente que convierte una lista de útiles escolares escrita en lenguaje natural en un JSON estructurado.

Lee el mensaje y emite UN SOLO objeto JSON, sin texto adicional, sin markdown, con esta forma:
{"items": [{"descripcion": "<descripción corta del ítem sin marca>", "cantidad": <número entero>}],
 "exclusion_marcas": ["<marca>", ...],
 "precio_max": <monto>,
 "precio_min": <monto>,
 "categoria": "<categoría>"}

Reglas:
- "items": TODOS los útiles mencionados, sin omitir ninguno. "cantidad" siempre como número entero (dos → 2, tres → 3, un → 1).
- IMPORTANTE: la cantidad es la que pide el usuario (un, dos, tres, 2, 3...). El "x10"/"x12" que forma parte del nombre del producto (p. ej. "plumones x10", "colores x12") NO es la cantidad.
- "exclusion_marcas": solo si el texto dice "sin marca X", "nada de la marca X", "sin genéricas" (usa "generica").
- "precio_max"/"precio_min": solo si mencionan presupuesto o monto.
- "categoria": solo si se menciona una categoría (p. ej. cuadernos, escritura, colores, maletería, textos).
- Omite los campos que no apliquen.
- NO inventes ids ni nombres de catálogo: solo descripciones.

Ejemplo:
Usuario: "Necesito 2 cuadernos cuadriculados y 1 esfero azul para el colegio, sin marca BIC y presupuesto máximo de 100 mil."
Salida: {"items": [{"descripcion": "cuaderno cuadriculado", "cantidad": 2}, {"descripcion": "esfero azul", "cantidad": 1}], "exclusion_marcas": ["bic"], "precio_max": 100000}

Ejemplo con cantidad en el NOMBRE del producto (no confundir):
Usuario: "Necesito un plumones x10, dos colores x12 y un cuaderno cuadriculado de 100 hojas."
Salida: {"items": [{"descripcion": "plumones x10", "cantidad": 1}, {"descripcion": "colores x12", "cantidad": 2}, {"descripcion": "cuaderno cuadriculado de 100 hojas", "cantidad": 1}]}
En "un plumones x10", la cantidad es 1 (el usuario pidió UNO); el "x10" es parte del nombre. En "dos colores x12", la cantidad es 2; el "x12" es parte del nombre. En "un cuaderno cuadriculado de 100 hojas", la cantidad es 1; "100 hojas" es parte del nombre."""


def _extraer_jsons(texto: str) -> list[str]:
    """Divide el texto en objetos JSON consecutivos, escaneando profundidad de
    llaves y comillas para respetar objetos anidados."""
    chunks: list[str] = []
    depth = 0
    en_string = False
    escape = False
    inicio = None
    for i, ch in enumerate(texto or ""):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            en_string = not en_string
            continue
        if en_string:
            continue
        if ch == "{":
            if depth == 0:
                inicio = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and inicio is not None:
                chunks.append(texto[inicio:i + 1])
                inicio = None
    return chunks


def _parsear_extraccion(contenido: str) -> dict | None:
    for chunk in _extraer_jsons(contenido):
        try:
            extraccion = json.loads(chunk)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(extraccion, dict) and isinstance(extraccion.get("items"), list):
            return extraccion
    return None


class AgenteLocalNL2C:
    def __init__(self, catalogo_lexico, model_path: str,
                 n_threads: int = 2, n_ctx: int = 4096,
                 max_tokens: int = 600, temperature: float = 0.0,
                 umbral_score: float = 0.30) -> None:
        from llama_cpp import Llama
        self.catalogo = catalogo_lexico
        self.umbral = umbral_score
        self._llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads,
                          verbose=False)
        self._max_tokens = max_tokens
        self._temperature = temperature

    def _ejecutar_tool(self, descripcion: str) -> dict:
        """Herramienta de recuperación: top-1 del catálogo por similitud."""
        mejores = self.catalogo.buscar(descripcion, k=1)
        if mejores and mejores[0]["score"] >= self.umbral:
            return {"id": mejores[0]["id"], "score": mejores[0]["score"]}
        return {"id": None, "score": 0.0}

    def resolver(self, texto: str) -> dict:
        mensajes = [
            {"role": "system", "content": SISTEMA_LOCAL},
            {"role": "user", "content": texto},
        ]
        t0 = time.perf_counter()
        resp = self._llm.create_chat_completion(
            messages=mensajes, max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        u = resp.get("usage") or {}
        contenido = (resp["choices"][0]["message"].get("content") or "").strip()
        extraccion = _parsear_extraccion(contenido)

        if extraccion is None:
            return {
                "resultado": {"items": [], "_sin_accion": True, "_content": contenido[:200]},
                "llamadas_tool": 0,
                "latencia_s": round(time.perf_counter() - t0, 3),
                "tokens": {"prompt": u.get("prompt_tokens", 0),
                           "completion": u.get("completion_tokens", 0),
                           "total": u.get("total_tokens", 0)},
                "costo_usd": 0.0,
            }

        items_final = []
        llamadas = 0
        for it in extraccion.get("items", []):
            descripcion = (it.get("descripcion") or "").strip()
            if not descripcion:
                continue
            cantidad = it.get("cantidad", 1) or 1
            try:
                cantidad = int(cantidad)
            except (TypeError, ValueError):
                cantidad = 1
            llamadas += 1
            match = self._ejecutar_tool(descripcion)
            items_final.append({"id": match["id"], "cantidad": cantidad,
                                "descripcion": descripcion, "score": match["score"]})

        restricciones = {k: v for k, v in extraccion.items()
                         if k in ("exclusion_marcas", "precio_max", "precio_min", "categoria")
                         and v not in (None, [], "")}
        resultado = {**restricciones, "items": items_final}

        return {
            "resultado": resultado,
            "llamadas_tool": llamadas,
            "latencia_s": round(time.perf_counter() - t0, 3),
            "tokens": {"prompt": u.get("prompt_tokens", 0),
                       "completion": u.get("completion_tokens", 0),
                       "total": u.get("total_tokens", 0)},
            "costo_usd": 0.0,
        }
