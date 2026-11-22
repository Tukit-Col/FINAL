"""Canal semantico de la busqueda hibrida: texto a vector, y coseno.

Decisiones:
- Es un puerto con dos implementaciones: una lista de textos entra y una lista de vectores unitarios
  sale. `embeder_gemini` es la de produccion (1024 dimensiones, como declara la columna y el indice
  HNSW); `embeder_falso` es determinista, no sale a la red y se arma de trigramas, para las pruebas.
- El vector siempre sale normalizado a norma 1, de modo que el coseno es el producto punto que
  calcula el operador `<=>` de pgvector.
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

Embeder = Callable[[Sequence[str]], list[list[float]]]

MODELO_GEMINI = "gemini-embedding-001"
MODELO_FALSO = "falso-trigramas-1024"

_URL_GEMINI = (
    "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:batchEmbedContents?key={clave}"
)
_TIEMPO_SEGUNDOS = 60
_LOTE_GEMINI = 100


def _plano(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


def texto_de_producto(nombre: str, concepto: str | None = None, atributos: dict | None = None) -> str:
    partes = [nombre]
    if concepto:
        partes.append(concepto)
    for clave, valor in (atributos or {}).items():
        partes.append(f"{clave} {valor}")
    return " ".join(str(p) for p in partes if p)


def texto_de_concepto(nombre: str, sinonimos: Sequence[str] = ()) -> str:
    return " ".join([nombre, *sinonimos])


def coseno(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    punto = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return punto / (na * nb)


def promedio(vectores: Sequence[Sequence[float]]) -> list[float] | None:
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


def _trigramas(texto: str) -> list[str]:
    plano = f" {_plano(texto)} "
    return [plano[i : i + 3] for i in range(len(plano) - 2)]


def embeder_falso(textos: Sequence[str]) -> list[list[float]]:
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


def _clave() -> str:
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise EmbeddingFallido(
            "Falta GEMINI_API_KEY. Sin ella no calculo embeddings, y no voy a "
            "inventar un vector que ponga cerca cosas que no lo estan."
        )
    return clave


class EmbeddingFallido(RuntimeError):
    pass


def embeder_gemini(textos: Sequence[str]) -> list[list[float]]:
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


embeder_gemini.modelo = MODELO_GEMINI  # type: ignore[attr-defined]
embeder_falso.modelo = MODELO_FALSO  # type: ignore[attr-defined]


def _modelo_gemini() -> str:
    return os.environ.get("GEMINI_MODELO_EMBEDDING", MODELO_GEMINI).strip() or MODELO_GEMINI


def modelo_de(embeder: Embeder) -> str | None:
    if embeder is embeder_gemini:
        return _modelo_gemini()
    modelo = getattr(embeder, "modelo", None)
    return modelo if isinstance(modelo, str) and modelo else None
