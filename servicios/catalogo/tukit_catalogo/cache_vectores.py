"""El vector de cada renglon, guardado en Redis (ADR 0047).

Las familias de un mismo colegio mandan los mismos renglones ("2 cuadernos
cuadriculados de 100 hojas"), y cada uno es un texto que el proveedor vuelve a
situar en el espacio semantico. El vector se guarda con el modelo, la dimension
y la huella SHA-256 del texto exacto que se le manda al proveedor, y un lote
lee todas sus claves de una vez y le pide al proveedor solo las que faltan, en
un lote y en orden.

**El valor** es el vector empacado en `float64` little-endian: el resultado
con cache es identico al de sin cache, flotante por flotante. Un valor de otro
largo cuenta como "no esta".

Solo se guarda lo que calcula un embeder con modelo declarado (`modelo_de`):
sin modelo no hay forma de saber que dos vectores son comparables. Si el
proveedor falla no se guarda nada, y quien llama degrada como siempre.

Sin Redis, o si no responde, todo falta y el proveedor recibe el lote entero,
como antes de que hubiera cache.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence

from tukit_comun.cache import cliente_redis, entero_de_entorno

from .embeddings import DIMENSION_EMBEDDING, Embeder, modelo_de

USO = "vector"
# 24 horas, el valor del SDD: cubre la temporada en que un colegio sube su
# lista sin guardar para siempre un vector de un modelo que puede cambiar.
TTL_POR_OMISION = 24 * 3600
_FORMATO = f"<{DIMENSION_EMBEDDING}d"


def clave(modelo: str, texto: str) -> str:
    """La clave del vector de `texto`, sin el prefijo del cliente."""
    return f"{USO}:{modelo}:{DIMENSION_EMBEDDING}:{hashlib.sha256(texto.encode()).hexdigest()}"


def a_bytes(vector: Sequence[float]) -> bytes:
    return struct.pack(_FORMATO, *vector)


def de_bytes(valor: bytes) -> list[float] | None:
    """El vector guardado en `valor`, o `None` si no tiene el largo de la dimension."""
    if len(valor) != struct.calcsize(_FORMATO):
        return None
    return list(struct.unpack(_FORMATO, valor))


async def vectores_guardados(renglones: Sequence[str], embeder: Embeder) -> list[list[float]]:
    """El vector de cada renglon, en orden: los guardados de Redis y los que
    faltan del proveedor. Si el proveedor falla, la excepcion sube sin guardar."""
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
