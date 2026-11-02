"""
Enfoque ACTUAL (baseline): parser de reglas sin LLM, portado fielmente de
producción:
  - Restricciones: regex de NL2C (services/api-gateway/nl2c/parser.py).
  - Ítems: heurística línea/por-frase de perception (PE-01) + sinónimos
    (PE-05) + cantidad por regex.
  - Matching al catálogo: TF-IDF de n-gramas de caracteres (emula el
    matching parcial de pg_trgm de producción) sobre los nombres.

Es 100% determinista, sin red, sin costo.
"""
import re
import unicodedata

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from benchmarks.nl2c_data import SINONIMOS_CATALOGO

_ACENTOS = str.maketrans("áéíóúüÁÉÍÓÚÜñÑ", "aeiouuAEIOUUnN")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return texto.translate(_ACENTOS)


# ── Restricciones (port de nl2c/parser.py) ────────────────────────────────
MARCAS_CONOCIDAS = (
    "norma", "bic", "maped", "staedtler", "faber-castell", "faber",
    "paper mate", "sharpie", "crayola", "artesco", "totto", "pelikan",
    "scribe", "ledesma", "pilot", "raya", "kimberly clark", "lider",
    "colkraft", "rayuela",
)

_PATRON_EXCLUSION = re.compile(
    r"(?i)\b(?:"
    r"sin|evitar|evita|excluye|excluir|fuera\s+de|"
    r"no\s+(?:comprar|quiero|quiera|uso|usar|necesito|deseo)"
    r")\s+(?P<candidatos>.+?)(?=,|;|\.|\bpero\b|\by\s+prefiero\b|\bya\b|\bsolo\b|$)"
)
_PATRON_PRECIO_MAX = re.compile(
    r"(?i)(?:presupuesto\s+(?:m[aá]ximo|max|tope)\s+(?:de\s+)?|"
    r"precio\s+m[aá]ximo\s+(?:de\s+)?|m[aá]ximo\s+|no\s+m[aá]s\s+de\s+|"
    r"hasta\s+|menos\s+de\s+|tope\s+(?:de\s+)?)\$?\s*(?P<monto>\d[\d.]*)\s*(mil)?")
_PATRON_GENERICA = re.compile(r"(?i)\bgen[eé]ric[oa]s?\b")


def _monto(monto: str, mil: str | None) -> float:
    limpio = monto.replace(".", "")
    valor = float(limpio)
    if mil and valor < 1000:
        valor *= 1000
    return valor


def extraer_restricciones(texto: str) -> dict:
    """Reglas NL2C de producción: exclusión de marcas, presupuesto máx."""
    t = _normalizar(texto)
    restricciones: dict = {}
    marcas: list[str] = []
    for match in _PATRON_EXCLUSION.finditer(t):
        candidatos = match.group("candidatos")
        for marca in MARCAS_CONOCIDAS:
            if re.search(rf"\b{re.escape(marca)}\b", candidatos):
                if marca not in marcas:
                    marcas.append(marca)
    if _PATRON_GENERICA.search(t):
        marcas.append("__GENERICA__")
    if marcas:
        restricciones["exclusion_marcas"] = marcas
    match_max = _PATRON_PRECIO_MAX.search(t)
    if match_max:
        restricciones["precio_max"] = _monto(match_max.group("monto"), match_max.group(2))
    # Categoría preferida (port de _detectar_categoria)
    for cat in ("cuadernos", "escritura", "colores", "cartuchera y útiles",
                "cartuchera", "maletería", "maleteria", "textos"):
        if re.search(rf"\b{cat}\b", t):
            restricciones["categoria"] = {
                "cuadernos": "Cuadernos", "escritura": "Escritura", "colores": "Colores",
                "cartuchera y útiles": "Cartuchera y útiles", "cartuchera": "Cartuchera y útiles",
                "maletería": "Maletería", "maleteria": "Maletería", "textos": "Textos",
            }[cat]
            break
    return restricciones


# ── Ítems (port de perception/extractor.py) ───────────────────────────────
_PATRON_CANTIDAD_LINEA = re.compile(r"^\s*(\d+)\s*[xX]?\s*[-.)]?\s*(.+)$")

# Cantidades en palabras (una lista escolar real las mezcla: "dos cuadernos").
_CANTIDADES_PALABRA = {
    "un": 1, "una": 1, "uno": 1, "unos": 1, "unas": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
}
_PATRON_CANTIDAD_PALABRA = re.compile(
    r"^\s*(?P<n>un|una|uno|unos|unas|dos|tres|cuatro|cinco)\s+(?P<desc>.+)$")


def _aplicar_sinonimos(descripcion: str) -> str:
    texto = " " + descripcion.lower().strip() + " "
    for sinonimo, canonico in SINONIMOS_CATALOGO.items():
        texto = re.sub(rf"\b{re.escape(sinonimo)}\b", canonico, texto)
    return texto.strip()


def _dividir_frases(texto: str, restricciones: dict) -> list[str]:
    """Quita las cláusulas de restricción y separa frases de ítems."""
    t = texto
    for marca in restricciones.get("exclusion_marcas", []):
        if marca == "__GENERICA__":
            t = re.sub(r"(?i)\bsin\s+marca\s+gen[eé]ric[oa]s?\b", "", t)
        else:
            t = re.sub(rf"(?i)(?:sin\s+marca\s+|nada\s+de\s+la\s+marca\s+)"
                       rf"{re.escape(marca)}", "", t)
    m = _PATRON_PRECIO_MAX.search(t)
    if m:
        t = t[:m.start()] + " " + t[m.end():]
    frases = re.split(r"(?i)[,;\.\n]|\b(?:y|e|tambi[eé]n|adem[aá]s)\b", t)
    salida = []
    for f in frases:
        f = f.strip(" -–—")
        if len(f) >= 2:
            salida.append(f)
    return salida


_VERBOS_INTRO = (
    r"\b(?:por\s+favor|necesito|necesita|incluye|incluyo|incluya|me\s+pidieron|"
    r"piden|pidieron|comprar|compro|busco|quiero|requiero|prefiero|"
    r"tambi[eé]n|adem[aá]s|para|la\s+lista\s+de\s+[úu]tiles)\b")


def _limpiar_descripcion(descripcion: str) -> str:
    descripcion = re.sub(r"\bpara\b.*$", "", descripcion).strip()
    descripcion = re.sub(r"\b(en|de|para)\s+la\s+compra\b.*$", "", descripcion).strip()
    descripcion = re.sub(_VERBOS_INTRO, " ", descripcion)
    descripcion = re.sub(r"\b(?:de|del|la|el|los|las|un|una|unos|unas)\b", " ", descripcion)
    descripcion = re.sub(r"\s+", " ", descripcion).strip()
    return _aplicar_sinonimos(descripcion)


def extraer_items(texto: str) -> list[dict]:
    """Devuelve [{descripcion, cantidad}] con la heurística de reglas."""
    restricciones = extraer_restricciones(texto)
    items = []
    for frase in _dividir_frases(texto, restricciones):
        m = _PATRON_CANTIDAD_LINEA.match(frase)
        if m:
            cantidad = int(m.group(1))
            descripcion = m.group(2)
        else:
            m = _PATRON_CANTIDAD_PALABRA.match(frase)
            if m:
                cantidad = _CANTIDADES_PALABRA[m.group("n")]
                descripcion = m.group("desc")
            else:
                cantidad = 1
                descripcion = frase
        descripcion = _limpiar_descripcion(descripcion)
        if descripcion:
            items.append({"descripcion": descripcion, "cantidad": cantidad})
    return items


# ── Matching al catálogo (n-gram TF-IDF, approx. pg_trgm) ─────────────────
class CatalogoLexico:
    def __init__(self, productos: list[dict]) -> None:
        self.productos = productos
        nombres = [_normalizar(p["nombre"]) for p in productos]
        self._vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                    strip_accents="unicode", lowercase=True)
        self._X = self._vec.fit_transform(nombres)

    def buscar(self, descripcion: str, k: int = 3) -> list[dict]:
        q = self._vec.transform([_normalizar(descripcion)])
        sims = cosine_similarity(q, self._X)[0]
        top = sims.argsort()[::-1][:k]
        return [
            {**self.productos[i], "score": round(float(sims[i]), 4)}
            for i in top if sims[i] > 0
        ]

    def mapear_items(self, items: list[dict], umbral: float = 0.30) -> list[dict]:
        """Top-1 por descripción si supera el umbral de similitud."""
        resultado = []
        for it in items:
            mejores = self.buscar(it["descripcion"], k=1)
            if mejores and mejores[0]["score"] >= umbral:
                resultado.append({
                    "id": mejores[0]["id"],
                    "cantidad": it["cantidad"],
                    "descripcion": it["descripcion"],
                    "score": mejores[0]["score"],
                })
            else:
                resultado.append({
                    "id": None, "cantidad": it["cantidad"],
                    "descripcion": it["descripcion"], "score": 0.0,
                })
        return resultado
