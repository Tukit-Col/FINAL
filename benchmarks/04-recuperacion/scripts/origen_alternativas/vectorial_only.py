"""
Enfoque SOLO BASE VECTORIAL (sin parser de reglas, sin LLM) para NL2C.

Hipótesis a verificar en el benchmark: ¿un pipeline 100% basado en la base
vectorial (embeddings + búsqueda por similitud de coseno) alcanza la calidad
del parser de reglas (enfoque actual) o del agente LLM local, sin ingeniería
de reglas ni ~20 s/caso de latencia LLM?

Diseño ("RAG sin generación"):
  1. Chunking genérico: el texto se divide en cláusulas/ítems candidatos por
     saltos de línea y conectores (`,`, `;`, `.`, `y`, `e`, `también`,
     `además`). A diferencia del parser de reglas, NO se usa el mapeo de
     sinónimos ni el stripping de verbos de intro: la semántica la pone SOLO
     el modelo de embeddings.
  2. Las cláusulas de restricción (marcas, presupuesto, categoría) se
     separan con la MISMA regex de producción (extraer_restricciones). Esto
     es un problema de forma, no de semántica, y se documenta: la hipótesis
     vectorial aplica al mapeo texto→producto, no a las restricciones.
  3. Por cada cláusula se extrae la cantidad con una regex mínima y el resto
     se EMBEBE y se recupera el top-1 del catálogo por similitud de coseno
     (>= umbral). La base vectorial es la ÚNICA fuente del mapeo texto→
     producto: no hay catálogo léxico (n-gramas) ni reglas de matching.

Es determinista, sin red ni costo (solo el modelo de embeddings local).
"""
import re
import unicodedata

from benchmarks.baseline_actual import extraer_restricciones

# Conectores que separan ítems en el formato "prosa". El "lista" se separa
# por saltos de línea. Es el chunking estándar de cualquier pipeline RAG.
_PATRON_CONECTORES = re.compile(r"(?i)[,;.\n]|\b(?:y|e|tambi[eé]n|adem[aá]s)\b")

# Cantidad mínima: número al inicio o palabra de cantidad. No hay más parseo.
_PATRON_CANTIDAD_NUM = re.compile(r"^\s*(\d+)\s*[xX]?\s*[-.)]?\s*(.+)$")
_CANTIDADES_PALABRA = {
    "un": 1, "una": 1, "uno": 1, "unos": 1, "unas": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
}
_PATRON_CANTIDAD_PALABRA = re.compile(
    r"^\s*(?P<n>un|una|uno|unos|unas|dos|tres|cuatro|cinco)\s+(?P<desc>.+)$")


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _quitar_restricciones(texto: str, restricciones: dict) -> str:
    """Quita las cláusulas de restricción para que no se embedan como ítems."""
    t = texto
    for marca in restricciones.get("exclusion_marcas", []):
        if marca == "__GENERICA__":
            t = re.sub(r"(?i)\bsin\s+marca\s+gen[eé]ric[oa]s?\b", "", t)
        else:
            t = re.sub(
                rf"(?i)(?:sin\s+marca\s+|nada\s+de\s+la\s+marca\s+){re.escape(marca)}",
                "", t)
    if "precio_max" in restricciones:
        m = re.search(r"(?i)(?:presupuesto\s+m[aá]ximo\s+(?:de\s+)?|\$?\s*\d[\d.]*)", t)
        if m:
            t = t[:m.start()] + " " + t[m.end():]
    return t


def _chunkear(texto: str, restricciones: dict) -> list[str]:
    """Divide el mensaje en cláusulas candidatas de ítems (sin restricciones)."""
    t = _quitar_restricciones(texto, restricciones)
    clausulas = []
    for trozo in _PATRON_CONECTORES.split(t):
        trozo = trozo.strip(" -–—")
        if len(trozo) >= 3:
            clausulas.append(trozo)
    return clausulas


def _cantidad_y_descripcion(clausula: str) -> tuple[int, str]:
    m = _PATRON_CANTIDAD_NUM.match(clausula)
    if m:
        return int(m.group(1)), m.group(2).strip()
    m = _PATRON_CANTIDAD_PALABRA.match(clausula)
    if m:
        return _CANTIDADES_PALABRA[m.group("n")], m.group("desc").strip()
    return 1, clausula.strip()


class NL2CVectorial:
    """NL2C con SOLO la base vectorial para el mapeo texto→producto.

    `catalogo` es un CatalogoSemantico (embeddings e5/MiniLM); el resto de la
    extracción (chunking, cantidad, restricciones) es mínima y se documenta.
    """

    def __init__(self, catalogo, umbral: float = 0.30) -> None:
        self.catalogo = catalogo
        self.umbral = umbral

    def resolver(self, texto: str) -> dict:
        """Devuelve {"items": [{id, cantidad, descripcion, score}],
        "restricciones": {...}}."""
        import time

        t0 = time.perf_counter()
        restricciones = extraer_restricciones(texto)
        items = []
        for clausula in _chunkear(texto, restricciones):
            cantidad, descripcion = _cantidad_y_descripcion(clausula)
            if not descripcion:
                continue
            mejores = self.catalogo.buscar(descripcion, k=1)
            if mejores and mejores[0]["score"] >= self.umbral:
                items.append({
                    "id": mejores[0]["id"], "cantidad": cantidad,
                    "descripcion": descripcion, "score": mejores[0]["score"],
                })
            else:
                items.append({
                    "id": None, "cantidad": cantidad,
                    "descripcion": descripcion, "score": 0.0,
                })
        return {
            "items": items,
            "restricciones": restricciones,
            "latencia_s": round(time.perf_counter() - t0, 4),
        }
