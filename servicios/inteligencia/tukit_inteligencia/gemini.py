"""Adaptador de Gemini. Un puerto con una sola implementacion.

La percepcion no sabe que existe este archivo. Le pasa los bytes de una
pagina a una funcion y recibe una `PaginaLeida`. Si el dia de manana el
modelo cambia, cambia este archivo y las reglas de grados y de truncamiento
siguen donde estan, que es en `percepcion.py`.

No hay reintento escondido ni respuesta inventada. Si la llamada no vuelve,
o vuelve algo que no es el JSON que pedimos, se alza `PercepcionFallida` y
el trabajo queda fallido y reintentable. Eso es lo que el contrato pide de
esta dependencia.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from pydantic import ValidationError

from .percepcion import PaginaLeida, PercepcionFallida

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={clave}"
_TIEMPO_SEGUNDOS = 60

# Se le pide el JSON dos veces, en el texto y en el esquema, porque el
# esquema es lo que la API valida y el texto es lo que el modelo usa para
# no partir una fila de la tabla en dos renglones.
_PROMPT = """Lee esta pagina de una lista de utiles escolares colombiana.
La pagina es una imagen: leela como tabla, no como texto suelto. Una fila es un item, aunque ocupe dos lineas.
No cortes una descripcion a la mitad. Si la fila dice "Diccionario de sinonimos", eso es el item entero.
En `cantidad` pon el numero de la columna de cantidad. Si no hay columna, dejala en null y no inventes una.
En `grados` lista cada grado o curso distinto que aparezca en la pagina, con su nombre (Cuarto, no 4°).
Si la pagina esta cortada, borrosa o no alcanzas a leerla toda, pon `completa` en false.
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


def _clave_y_modelo() -> tuple[str, str]:
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise PercepcionFallida(
            "Falta GEMINI_API_KEY. Sin ella no leo la lista, y no voy a inventar los renglones."
        )
    return clave, os.environ.get("GEMINI_MODELO", MODELO_POR_DEFECTO).strip() or MODELO_POR_DEFECTO


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
    try:
        with urllib.request.urlopen(pedido, timeout=_TIEMPO_SEGUNDOS) as respuesta:
            crudo = json.loads(respuesta.read().decode())
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode(errors="replace")[:300]
        raise PercepcionFallida(f"Gemini respondio {exc.code}: {detalle}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PercepcionFallida(f"Gemini no respondio: {exc}") from exc

    try:
        texto = crudo["candidates"][0]["content"]["parts"][0]["text"]
        return PaginaLeida.model_validate_json(texto)
    except (KeyError, IndexError, ValidationError, json.JSONDecodeError) as exc:
        raise PercepcionFallida(f"La respuesta no trae los items pedidos: {exc}") from exc
