"""La lectura aceptada de una lista, guardada en Redis.

Decisiones:
- Leer una lista cuesta una llamada a Gemini por pagina y las familias de un colegio suben el mismo
  PDF: la lectura aceptada se guarda con la huella SHA-256 del archivo y una version de la
  percepcion. El cruce con el catalogo y los precios se recalcula siempre.
- La version ata la lectura a lo que la produjo (render, prompt y validacion, reglas de percepcion,
  version de pypdfium2 y modelo efectivo): cualquier cambio vuelve a leer, porque se prefiere una
  lectura de mas a una lectura vieja.
- Se guardan solo `grados`, `paginas` e `items`; ni el archivo, ni la cuenta, ni el contacto, ni el
  hijo. Los rechazos no se guardan.
- Sin Redis, o si no responde, se lee como si no hubiera cache.
"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Callable
from importlib import metadata
from pathlib import Path

from pydantic import ValidationError
from tukit_comun.cache import cliente_redis, entero_de_entorno

from . import gemini
from .percepcion import ItemExtraido, Percepcion

USO = "percepcion"
TTL_POR_OMISION = 30 * 24 * 3600
_PIEZAS = ("paginas.py", "gemini.py", "percepcion.py")


@functools.cache
def _huella_del_codigo() -> str:
    huella = hashlib.sha256()
    carpeta = Path(__file__).parent
    for nombre in _PIEZAS:
        huella.update(nombre.encode() + b"\0" + (carpeta / nombre).read_bytes() + b"\0")
    try:
        pdfium = metadata.version("pypdfium2")
    except metadata.PackageNotFoundError:
        pdfium = "sin-pypdfium2"
    huella.update(f"pypdfium2={pdfium}".encode())
    return huella.hexdigest()


def version() -> str:
    return hashlib.sha256(f"{_huella_del_codigo()}:{gemini.modelo()}".encode()).hexdigest()[:16]


def clave(contenido: bytes) -> str:
    return f"{USO}:{version()}:{hashlib.sha256(contenido).hexdigest()}"


def a_bytes(percepcion: Percepcion) -> bytes:
    datos = {
        "grados": list(percepcion.grados),
        "paginas": percepcion.paginas,
        "items": [item.model_dump() for item in percepcion.items],
    }
    return json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()


def de_bytes(valor: bytes) -> Percepcion | None:
    try:
        datos = json.loads(valor)
        return Percepcion(
            aceptada=True,
            grados=tuple(str(grado) for grado in datos["grados"]),
            paginas=int(datos["paginas"]),
            items=tuple(ItemExtraido.model_validate(item) for item in datos["items"]),
        )
    except (ValueError, KeyError, TypeError, ValidationError):
        return None


async def percibir_guardada(contenido: bytes, percibir: Callable[[bytes], Percepcion]) -> Percepcion:
    ttl = entero_de_entorno("TUKIT_CACHE_PERCEPCION_SEGUNDOS", TTL_POR_OMISION)
    if not contenido or ttl <= 0:
        return percibir(contenido)
    cliente = cliente_redis()
    llave = clave(contenido)
    guardado = await cliente.leer(USO, llave)
    if guardado is not None:
        percepcion = de_bytes(guardado)
        if percepcion is not None:
            return percepcion
    percepcion = percibir(contenido)
    if percepcion.aceptada:
        await cliente.guardar(USO, llave, a_bytes(percepcion), ttl)
    return percepcion
