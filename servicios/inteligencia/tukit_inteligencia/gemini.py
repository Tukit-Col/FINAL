"""Adaptador de Gemini. Un puerto con una sola implementacion.

La percepcion no sabe que existe este archivo. Le pasa los bytes de una
pagina a una funcion y recibe una `PaginaLeida`. Si el dia de manana el
modelo cambia, cambia este archivo y las reglas de grados y de truncamiento
siguen donde estan, que es en `percepcion.py`.

No hay respuesta inventada. Si la llamada no vuelve, o vuelve algo que no es
el JSON que pedimos, se alza `PercepcionFallida` y el trabajo queda fallido y
reintentable. Eso es lo que el contrato pide de esta dependencia.

Hay UN reintento, y solo de transporte: cuando Gemini no responde a tiempo o
devuelve un error de su lado (429, 5xx). Medido: la misma pagina que se quedo
colgada 60 s respondio en 6 s al pedirla otra vez, y la pagina tipica tarda
unos 5 s. Sin el reintento, una sola pagina colgada rechazaba la lista entera y
el acudiente volvia a subirla, pagando otra vez la lectura de TODAS las
paginas. Una respuesta que llega mal formada no se reintenta: eso no es la red,
es el modelo, y pedirlo de nuevo esconderia el fallo.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request

from pydantic import ValidationError

from .percepcion import PaginaLeida, PercepcionFallida

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={clave}"
# Una pagina tipica responde en ~5 s; 40 s ya es una llamada colgada. Con el
# reintento, el peor caso por pagina queda en ~85 s en vez de fallar a los 60.
_TIEMPO_SEGUNDOS = 40
_INTENTOS = 2
_ESPERA_ENTRE_INTENTOS = 3
# Errores HTTP que son de Gemini y pasajeros. Un 400 o un 403 (llave mala) no
# mejoran al repetir.
_HTTP_PASAJEROS = frozenset({429, 500, 502, 503, 504})

# Se le pide el JSON dos veces, en el texto y en el esquema, porque el
# esquema es lo que la API valida y el texto es lo que el modelo usa para
# no partir una fila de la tabla en dos renglones.
_PROMPT = """Lee esta pagina de una lista de utiles escolares colombiana.
La pagina es una imagen: leela como tabla, no como texto suelto. Una fila es un item, aunque ocupe dos lineas.
No cortes una descripcion a la mitad. Si la fila dice "Diccionario de sinonimos", eso es el item entero.
En `cantidad` pon el numero de la columna de cantidad. Si no hay columna, dejala en null y no inventes una.
Separa lo que se compra por aparte: "Cartuchera con: esferos, borrador" son 3 items, incluida la cartuchera
("Cartuchera", "esferos", "borrador"); "Pinturas acrilicas: cian, magenta y rojo" es un item por color
("Pinturas acrilicas cian", "Pinturas acrilicas magenta", "Pinturas acrilicas rojo"). Igual si los colores
vienen al final: "4 carpetas oficio con gancho. Colores: azul, rojo, verde, amarillo" son 4 items ("carpetas
oficio con gancho azul"...). La cantidad total se reparte, nunca se repite: si es igual al numero de colores,
cada item lleva cantidad 1.
No separes "tajalapiz o portaminas", un producto entero ("Kit de 12 pinceles (planos, redondos)")
ni una serie de durezas: "Lapices HB, 2H, 2B, 6B" es un solo item.
Cada uniforme es UN item con su nombre ("Uniforme de diario"), sin sus prendas.
En `grados` lista cada grado o curso cuya lista ES esta pagina (el titulo o encabezado: "GRADO DECIMO",
"Lista de Cuarto"), con su nombre (Cuarto, no 4°). Un grado que solo se menciona de paso no cuenta:
"estos libros se usan el ano siguiente en 11" o "paquete del grado sexto en la tienda" no son otra lista.
Si la imagen esta recortada, borrosa o no alcanzas a leerla toda, pon `completa` en false.
Un texto que sigue en la pagina siguiente no es una pagina cortada: lee lo que hay y deja `completa` en true.
No agregues items que no esten escritos."""

_ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "grados": {"type": "ARRAY", "items": {"type": "STRING"}},
        "completa": {"type": "BOOLEAN"},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "descripcion": {"type": "STRING"},
                    "cantidad": {"type": "INTEGER", "nullable": True},
                    "confianza": {"type": "NUMBER", "nullable": True},
                },
                "required": ["descripcion"],
            },
        },
    },
    "required": ["grados", "items", "completa"],
}


def modelo() -> str:
    """El modelo que lee las paginas: `GEMINI_MODELO`, o el de por defecto.

    Lo usa tambien la version de la cache de lecturas (ADR 0047): una lectura
    guardada con otro modelo no se reaprovecha."""
    return os.environ.get("GEMINI_MODELO", MODELO_POR_DEFECTO).strip() or MODELO_POR_DEFECTO


def _clave_y_modelo() -> tuple[str, str]:
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise PercepcionFallida(
            "Falta GEMINI_API_KEY. Sin ella no leo la lista, y no voy a inventar los renglones."
        )
    return clave, modelo()


def _llamar(pedido: urllib.request.Request) -> dict:
    """La llamada HTTP, con un reintento si el fallo es de transporte."""
    for intento in range(1, _INTENTOS + 1):
        ultimo = intento == _INTENTOS
        try:
            with urllib.request.urlopen(pedido, timeout=_TIEMPO_SEGUNDOS) as respuesta:
                return json.loads(respuesta.read().decode())
        except urllib.error.HTTPError as exc:
            detalle = exc.read().decode(errors="replace")[:300]
            if ultimo or exc.code not in _HTTP_PASAJEROS:
                raise PercepcionFallida(f"Gemini respondio {exc.code}: {detalle}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if ultimo:
                raise PercepcionFallida(f"Gemini no respondio: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise PercepcionFallida(f"Gemini no respondio: {exc}") from exc
        time.sleep(_ESPERA_ENTRE_INTENTOS)
    raise AssertionError("inalcanzable")


def pedir_pagina(png: bytes, numero: int) -> PaginaLeida:
    """Manda una pagina y devuelve solo lo que el esquema acepta."""
    clave, modelo = _clave_y_modelo()
    cuerpo = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{_PROMPT}\n\nEsta es la pagina {numero}."},
                    {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png).decode()}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _ESQUEMA,
        },
    }
    pedido = urllib.request.Request(
        _URL.format(modelo=modelo, clave=clave),
        data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    crudo = _llamar(pedido)

    try:
        texto = crudo["candidates"][0]["content"]["parts"][0]["text"]
        return PaginaLeida.model_validate_json(texto)
    except (KeyError, IndexError, ValidationError, json.JSONDecodeError) as exc:
        raise PercepcionFallida(f"La respuesta no trae los items pedidos: {exc}") from exc
