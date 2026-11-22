"""El vector de cada renglon, guardado en Redis.

Decisiones:
- La clave lleva el modelo, la dimension y la huella SHA-256 del texto exacto que se manda al
  proveedor; un lote lee todas sus claves de una vez y pide solo las que faltan.
- El valor es el vector empacado en `float64` little-endian, de modo que el resultado con cache es
  identico al de sin cache. Un valor de otro largo cuenta como "no esta".
- Solo se guarda lo que calcula un embeder con modelo declarado; si el proveedor falla no se guarda
  nada. Sin Redis, el proveedor recibe el lote entero.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence

from tukit_comun.cache import cliente_redis, entero_de_entorno

from .embeddings import DIMENSION_EMBEDDING, Embeder, modelo_de

USO = "vector"
TTL_POR_OMISION = 24 * 3600
_FORMATO = f"<{DIMENSION_EMBEDDING}d"


def clave(modelo: str, texto: str) -> str:
    return f"{USO}:{modelo}:{DIMENSION_EMBEDDING}:{hashlib.sha256(texto.encode()).hexdigest()}"


def a_bytes(vector: Sequence[float]) -> bytes:
    return struct.pack(_FORMATO, *vector)


def de_bytes(valor: bytes) -> list[float] | None:
    if len(valor) != struct.calcsize(_FORMATO):
        return None
    return list(struct.unpack(_FORMATO, valor))


async def vectores_guardados(renglones: Sequence[str], embeder: Embeder) -> list[list[float]]:
    modelo = modelo_de(embeder)
    ttl = entero_de_entorno("TUKIT_CACHE_VECTORES_SEGUNDOS", TTL_POR_OMISION)
    if modelo is None or ttl <= 0:
        return list(embeder(list(renglones)))

    cliente = cliente_redis()
    claves = [clave(modelo, texto) for texto in renglones]
    guardados = [de_bytes(v) if v is not None else None for v in await cliente.leer_varias(USO, claves)]
    faltan = [i for i, vector in enumerate(guardados) if vector is None]
    nuevos: dict[int, list[float]] = {}
    if faltan:
        nuevos = dict(zip(faltan, embeder([renglones[i] for i in faltan]), strict=True))
        pares = {claves[i]: a_bytes(v) for i, v in nuevos.items() if len(v) == DIMENSION_EMBEDDING}
        await cliente.guardar_varias(USO, pares, ttl)
    return [vector if vector is not None else nuevos[i] for i, vector in enumerate(guardados)]
