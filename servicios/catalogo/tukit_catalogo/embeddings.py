"""El canal semantico de la busqueda hibrida: texto -> vector, y coseno.

El catalogo ya tenia la mitad lexica (trigramas, `_parecido`, la cabeza
anclada) y la columna `producto_canonico.embedding` esperando vacia. Aqui vive
la otra mitad: convertir un texto en el vector de 1024 flotantes que la columna
guarda, para que `clasificar` pueda sumar "cuanto se parece el SIGNIFICADO" a
"cuanto se parecen las PALABRAS".

Es un puerto con dos implementaciones y una sola forma: una lista de textos
entra, una lista de vectores unitarios sale.

- `embeder_gemini` es la de produccion. Usa la misma clave que la percepcion
  (`GEMINI_API_KEY`) por coherencia de procedencia: el mismo proveedor que leyo
  la lista es el que la situa en el espacio semantico. Pide 1024 dimensiones
  explicitamente porque asi lo declara la columna y el indice HNSW.
- `embeder_falso` es la de las pruebas. NO sale a la red y es determinista, dos
  cosas que el CI necesita. No es un vector al azar: se arma de los trigramas
  del texto, de modo que dos textos que comparten letras quedan cerca y dos que
  no, lejos. Es una semantica pobre pero suficiente y honesta para fijar que la
  fusion hace lo que dice —desempatar por significado un match que el lexico ya
  acerto— sin fingir un modelo que la prueba no tiene.

El vector siempre sale normalizado a norma 1. Con vectores unitarios el coseno
es el producto punto, que es lo que el operador `<=>` de pgvector calcula y lo
que `coseno` calcula aqui: una sola definicion de "cerca" en la base y en la
memoria.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence

from .modelos.base import DIMENSION_EMBEDDING

__all__ = [
    "DIMENSION_EMBEDDING",
    "Embeder",
    "EmbeddingFallido",
    "MODELO_FALSO",
    "MODELO_GEMINI",
    "coseno",
    "embeder_falso",
    "embeder_gemini",
    "modelo_de",
    "promedio",
    "texto_de_concepto",
    "texto_de_producto",
]

# Un puerto: recibe textos, devuelve un vector unitario de 1024 por cada uno.
Embeder = Callable[[Sequence[str]], list[list[float]]]

MODELO_GEMINI = "gemini-embedding-001"
MODELO_FALSO = "falso-trigramas-1024"

_URL_GEMINI = (
    "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:batchEmbedContents?key={clave}"
)
_TIEMPO_SEGUNDOS = 60
# Gemini acepta muchos textos por peticion; se parte en lotes para no armar un
# cuerpo gigante ni depender de un limite exacto que el proveedor puede mover.
_LOTE_GEMINI = 100


# ---------------------------------------------------------------------------
# El texto que se embebe
# ---------------------------------------------------------------------------


def _plano(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


def texto_de_producto(nombre: str, concepto: str | None = None, atributos: dict | None = None) -> str:
    """El texto canonico de un producto, que es lo que se embebe y se guarda.

    Se junta el nombre con el concepto y los atributos porque el nombre solo no
    situa bien: `Cosido 100 hojas Norma` y `Argollado 100 hojas` se parecen en
    letras pero son cuadernos distintos, y el atributo `rayado`/`tamano` es lo
    que los separa. Guardar este texto en `texto_embedding` deja ver DE QUE se
    calculo el vector, que es la unica forma de depurar por que dos cosas
    quedaron cerca o lejos.
    """
    partes = [nombre]
    if concepto:
        partes.append(concepto)
    for clave, valor in (atributos or {}).items():
        partes.append(f"{clave} {valor}")
    return " ".join(str(p) for p in partes if p)


def texto_de_concepto(nombre: str, sinonimos: Sequence[str] = ()) -> str:
    """El texto de un concepto: su nombre y como mas lo llama la gente."""
    return " ".join([nombre, *sinonimos])


# ---------------------------------------------------------------------------
# Coseno
# ---------------------------------------------------------------------------


def coseno(a: Sequence[float], b: Sequence[float]) -> float:
    """El coseno entre dos vectores. Con vectores unitarios es el producto punto.

    Se calcula el producto punto y se divide por las normas de todas formas, en
    vez de asumir que llegan normalizados, para que la funcion sea correcta con
    cualquier vector —el de la base pudo guardarse de otra fuente— y no un
    supuesto que se rompe en silencio.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    punto = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return punto / (na * nb)


def promedio(vectores: Sequence[Sequence[float]]) -> list[float] | None:
    """El centro normalizado de varios vectores, o None si no hay ninguno.

    El vector de un concepto se deriva del de sus productos: el centro de los
    cuadernos ES, en promedio, "cuaderno". Asi el canal semantico de
    `clasificar` reusa los embeddings ya poblados en `producto_canonico` y no
    necesita ni una columna nueva en `concepto` ni una llamada a la red por
    renglon.
    """
    utiles = [v for v in vectores if v]
    if not utiles:
        return None
    dim = len(utiles[0])
    suma = [0.0] * dim
    for v in utiles:
        if len(v) != dim:
            continue
        for i, x in enumerate(v):
            suma[i] += x
    return _normalizar(suma)


def _normalizar(vector: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vector))
    if norma == 0.0:
        return vector
    return [x / norma for x in vector]


# ---------------------------------------------------------------------------
# Embeder falso (pruebas, sin red)
# ---------------------------------------------------------------------------


def _trigramas(texto: str) -> list[str]:
    plano = f" {_plano(texto)} "
    return [plano[i : i + 3] for i in range(len(plano) - 2)]


def embeder_falso(textos: Sequence[str]) -> list[list[float]]:
    """Vector determinista de trigramas, unitario, sin salir a la red.

    Cada trigrama del texto cae en una posicion del vector por su hash, con un
    signo tambien derivado del hash para que las colisiones no se sumen siempre
    a favor. Dos textos que comparten trigramas —`bloc`/`block`, `lapiz`/
    `lapices`— acaban con vectores parecidos; dos que no, ortogonales. Es lo
    justo para probar la fusion sin fingir el modelo de produccion.
    """
    salida: list[list[float]] = []
    for texto in textos:
        vector = [0.0] * DIMENSION_EMBEDDING
        for grama in _trigramas(texto):
            golpe = int.from_bytes(hashlib.blake2b(grama.encode(), digest_size=8).digest(), "big")
            indice = golpe % DIMENSION_EMBEDDING
            signo = 1.0 if (golpe >> 17) & 1 else -1.0
            vector[indice] += signo
        salida.append(_normalizar(vector))
    return salida


# ---------------------------------------------------------------------------
# Embeder de Gemini (produccion)
# ---------------------------------------------------------------------------


def _clave() -> str:
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise EmbeddingFallido(
            "Falta GEMINI_API_KEY. Sin ella no calculo embeddings, y no voy a "
            "inventar un vector que ponga cerca cosas que no lo estan."
        )
    return clave


class EmbeddingFallido(RuntimeError):
    """La llamada al proveedor no volvio, o volvio algo que no es un vector."""


def embeder_gemini(textos: Sequence[str]) -> list[list[float]]:
    """Embeddings de Gemini, en lotes, a 1024 dimensiones y normalizados.

    Se piden 1024 dimensiones explicitamente porque asi lo declara la columna y
    el indice HNSW; el modelo por omision saca mas y guardarlas romperia la
    forma. No hay reintento escondido: si el proveedor no responde, se alza
    `EmbeddingFallido` y quien llama decide, igual que hace la percepcion.
    """
    clave = _clave()
    modelo = _modelo_gemini()
    salida: list[list[float]] = []
    for inicio in range(0, len(textos), _LOTE_GEMINI):
        lote = textos[inicio : inicio + _LOTE_GEMINI]
        cuerpo = {
            "requests": [
                {
                    "model": f"models/{modelo}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": DIMENSION_EMBEDDING,
                }
                for t in lote
            ]
        }
        pedido = urllib.request.Request(
            _URL_GEMINI.format(modelo=modelo, clave=clave),
            data=json.dumps(cuerpo).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=_TIEMPO_SEGUNDOS) as respuesta:
                crudo = json.loads(respuesta.read().decode())
        except urllib.error.HTTPError as exc:
            detalle = exc.read().decode(errors="replace")[:300]
            raise EmbeddingFallido(f"Gemini respondio {exc.code}: {detalle}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise EmbeddingFallido(f"Gemini no respondio: {exc}") from exc

        try:
            vectores = [e["values"] for e in crudo["embeddings"]]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingFallido(f"La respuesta no trae los vectores pedidos: {exc}") from exc
        if len(vectores) != len(lote):
            raise EmbeddingFallido(f"Se pidieron {len(lote)} vectores y volvieron {len(vectores)}.")
        salida.extend(_normalizar(list(v)) for v in vectores)
    return salida


# Cada embeder declara con QUE modelo marca sus vectores. Quien puebla la base
# lee este atributo (no la identidad de la funcion, que un envoltorio pierde)
# para escribir `embedding_model` y para saber recalcular si el modelo cambia.
embeder_gemini.modelo = MODELO_GEMINI  # type: ignore[attr-defined]
embeder_falso.modelo = MODELO_FALSO  # type: ignore[attr-defined]


def _modelo_gemini() -> str:
    return os.environ.get("GEMINI_MODELO_EMBEDDING", MODELO_GEMINI).strip() or MODELO_GEMINI


def modelo_de(embeder: Embeder) -> str | None:
    """El modelo con que `embeder` calcula de verdad, o `None` si no declara uno.

    Para `embeder_gemini` es el de `GEMINI_MODELO_EMBEDDING` si esta puesto: el
    atributo `modelo` es solo el de por omision. La cache de vectores (ADR 0047)
    lo lleva en la clave, y un embeder sin modelo conocido no se cachea."""
    if embeder is embeder_gemini:
        return _modelo_gemini()
    modelo = getattr(embeder, "modelo", None)
    return modelo if isinstance(modelo, str) and modelo else None
