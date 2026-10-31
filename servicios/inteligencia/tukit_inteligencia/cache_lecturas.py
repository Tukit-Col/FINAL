"""La lectura aceptada de una lista, guardada en Redis (ADR 0047).

Leer una lista cuesta una llamada a Gemini por pagina, y las familias de un
mismo colegio suben el mismo PDF. La lectura aceptada se guarda con la huella
SHA-256 del archivo y una version de la percepcion, y la siguiente subida del
mismo archivo la reaprovecha. Lo que viene despues (el cruce con el catalogo y
los precios) se recalcula siempre: la reverificacion de precio (ESC-10) no
cambia.

**La version** ata la lectura a lo que la produjo: los bytes de `paginas.py` (el
render), `gemini.py` (el prompt, el esquema y la validacion) y `percepcion.py`
(las reglas de grados, paginas y rechazos), la version de pypdfium2 y el modelo
efectivo. Cualquier cambio en esas piezas, aunque sea un comentario, vuelve a
leer: se prefiere una lectura de mas a una lectura vieja.

**El valor** son los `grados`, las `paginas` y los `items` de la `Percepcion`,
que es todo lo que trae una aceptada: ni el archivo, ni la cuenta, ni el
contacto, ni el hijo, que viven en la ruta. Los rechazos no se guardan: un
archivo ilegible hoy puede leerse con el modelo de manana.

Sin Redis, o si no responde, se lee como antes de que hubiera cache.
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
# 30 dias: una lista escolar vale un anio lectivo, y un mes cubre la temporada
# de compras sin que una lectura viva para siempre.
TTL_POR_OMISION = 30 * 24 * 3600
_PIEZAS = ("paginas.py", "gemini.py", "percepcion.py")


@functools.cache
def _huella_del_codigo() -> str:
    """El SHA-256 de las piezas que deciden como se lee y de la version de pypdfium2."""
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
    """La version de la percepcion: el codigo que lee y el modelo con que lee."""
    return hashlib.sha256(f"{_huella_del_codigo()}:{gemini.modelo()}".encode()).hexdigest()[:16]


def clave(contenido: bytes) -> str:
    """La clave de la lectura de `contenido`, sin el prefijo del cliente."""
    return f"{USO}:{version()}:{hashlib.sha256(contenido).hexdigest()}"


def a_bytes(percepcion: Percepcion) -> bytes:
    datos = {
        "grados": list(percepcion.grados),
        "paginas": percepcion.paginas,
        "items": [item.model_dump() for item in percepcion.items],
    }
    return json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()


def de_bytes(valor: bytes) -> Percepcion | None:
    """La `Percepcion` aceptada guardada en `valor`, o `None` si no se puede leer."""
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
    """La lectura de `contenido`: la guardada si la hay, y si no la de `percibir`,
    que se guarda si fue aceptada."""
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
