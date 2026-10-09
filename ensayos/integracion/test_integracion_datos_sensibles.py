"""Lo que el stack guarda y escribe de los datos sensibles: tarjetas y el menor.

NFR-SEG-01 barre las cinco bases y los logs de `make arriba` buscando numeros de
tarjeta (Luhn y prefijo de una marca) despues de un pago completo. NFR-SEG-07
sigue un dato ficticio del menor por los dos caminos por donde entra: el apodo
del registro y el nombre escrito en la lista que sube el acudiente. Para ver lo
que saldria hacia el modelo se levanta una inteligencia aparte cuyo lector de
paginas graba lo que recibe (`inteligencia_lector_grabado.py`): sin clave de
Gemini y sin red.

Los logs que se barren son los que el stack escribe con `logging` (que vacia
cada linea); lo que un proceso imprima con `print` puede seguir en su bufer.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image, ImageDraw, PngImagePlugin
from sqlalchemy import text
from stack_vivo import GATEWAY, SERVICIOS_CON_BASE, conexion_a, instancia, logs_del_stack, orden_pagada

pytestmark = pytest.mark.integracion

_COLUMNAS = """
    select table_name, column_name, data_type from information_schema.columns
    where table_schema = 'public'
      and data_type in ('text', 'character varying', 'character', 'json', 'jsonb', 'bytea')
    order by table_name, column_name
"""


async def _columnas(conexion: Any) -> list[tuple[str, str, str]]:
    return [tuple(fila) for fila in await conexion.execute(text(_COLUMNAS))]


# --------------------------------------------------------------- NFR-SEG-01

# 16 digitos seguidos o en cuatro grupos de cuatro: las dos formas en que se
# escribe una tarjeta. Los grupos no pueden venir pegados a un guion, para no
# leer los bloques de un UUID como una tarjeta.
_CANDIDATO = re.compile(r"(?<![\d-])(?:\d{4}[ -]){3}\d{4}(?![\d-])|(?<!\d)\d{13,19}(?!\d)")
_NOMBRES_DE_TARJETA = {"pan", "cvv", "cvc", "tarjeta", "card"}


def _luhn(numero: str) -> bool:
    suma = 0
    for posicion, caracter in enumerate(reversed(numero)):
        digito = int(caracter)
        if posicion % 2:
            digito = digito * 2 - 9 if digito > 4 else digito * 2
        suma += digito
    return suma % 10 == 0


def _marca(numero: str) -> str | None:
    largo = len(numero)
    if numero[0] == "4" and largo in (13, 16, 19):
        return "visa"
    if (51 <= int(numero[:2]) <= 55 or 2221 <= int(numero[:4]) <= 2720) and largo == 16:
        return "mastercard"
    if numero[:2] in ("34", "37") and largo == 15:
        return "amex"
    if (numero[:4] == "6011" or numero[:2] == "65" or 644 <= int(numero[:3]) <= 649) and 16 <= largo <= 19:
        return "discover"
    if (numero[:2] in ("36", "38") or 300 <= int(numero[:3]) <= 305) and largo == 14:
        return "diners"
    if 3528 <= int(numero[:4]) <= 3589 and 16 <= largo <= 19:
        return "jcb"
    return None


def _tarjetas_en(valor: str) -> set[str]:
    encontradas = set()
    for candidato in _CANDIDATO.findall(valor):
        numero = re.sub(r"[ -]", "", candidato)
        if _marca(numero) and _luhn(numero):
            encontradas.add(numero)
    return encontradas


async def _codigos_de_barras() -> set[str]:
    """EAN, ISBN y GTIN del catalogo: 13 digitos que a veces pasan por una Visa."""
    codigos: set[str] = set()
    async with conexion_a("catalogo") as conexion:
        for tabla, columna, _ in await _columnas(conexion):
            if re.search(r"(^|_)(ean|isbn|gtin|codigo_barras)($|_)", columna):
                filas = await conexion.execute(
                    text(f'select "{columna}"::text from "{tabla}" where "{columna}" is not null')
                )
                codigos.update(re.sub(r"\D", "", fila[0]) for fila in filas)
    return codigos


@pytest.fixture(scope="module")
def codigos_de_barras() -> set[str]:
    return asyncio.run(_codigos_de_barras())


@pytest.mark.nfr("NFR-SEG-01")
async def test_tras_un_pago_ninguna_base_guarda_un_numero_de_tarjeta(
    cliente: httpx.Client, sesiones: dict, producto: dict, codigos_de_barras: set[str], record_property
):
    orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    hallazgos: list[str] = []
    excluidos = 0
    columnas_barridas = 0
    for servicio in SERVICIOS_CON_BASE:
        async with conexion_a(servicio) as conexion:
            for tabla, columna, tipo in await _columnas(conexion):
                columnas_barridas += 1
                if tipo == "bytea":
                    consulta = f'select "{columna}" from "{tabla}" where "{columna}" is not null'
                else:
                    consulta = (
                        f'select "{columna}"::text from "{tabla}" where "{columna}"::text ~ \'[0-9]{{4}}\''
                    )
                for (valor,) in await conexion.execute(text(consulta)):
                    claro = valor.decode("latin-1") if isinstance(valor, bytes) else valor
                    for numero in _tarjetas_en(claro):
                        if numero in codigos_de_barras:
                            excluidos += 1
                        else:
                            hallazgos.append(
                                f"{servicio}.{tabla}.{columna}: {_marca(numero)} ...{numero[-4:]}"
                            )

    record_property("columnas_barridas", columnas_barridas)
    record_property("excluidos_codigo_de_barras", excluidos)
    record_property("coincidencias_pan", len(hallazgos))
    assert columnas_barridas > 0
    assert hallazgos == []


@pytest.mark.nfr("NFR-SEG-01")
async def test_ninguna_columna_se_llama_como_un_dato_de_tarjeta(record_property):
    sospechosas = []
    for servicio in SERVICIOS_CON_BASE:
        async with conexion_a(servicio) as conexion:
            filas = await conexion.execute(
                text(
                    "select table_name, column_name from information_schema.columns "
                    "where table_schema = 'public'"
                )
            )
            for tabla, columna in filas:
                if _NOMBRES_DE_TARJETA & set(columna.lower().split("_")):
                    sospechosas.append(f"{servicio}.{tabla}.{columna}")

    record_property("columnas_sospechosas", len(sospechosas))
    assert sospechosas == []


@pytest.mark.nfr("NFR-SEG-01")
def test_los_logs_del_stack_no_traen_numeros_de_tarjeta(codigos_de_barras: set[str], record_property):
    hallazgos = []
    for registro in logs_del_stack():
        for numero in _tarjetas_en(registro.read_text(errors="replace")):
            if numero not in codigos_de_barras:
                hallazgos.append(f"{registro.name}: {_marca(numero)} ...{numero[-4:]}")

    record_property("logs_barridos", len(logs_del_stack()))
    record_property("coincidencias_pan", len(hallazgos))
    assert hallazgos == []


# --------------------------------------------------------------- NFR-SEG-07: el apodo del registro


def _marca_ficticia() -> str:
    """Un nombre que no es de nadie, con sufijo unico para buscarlo sin ruido."""
    return f"Zorbalina{uuid.uuid4().hex[:10]}"


async def _apariciones(marca: str) -> list[str]:
    """`base.tabla.columna` de cada columna que contiene `marca` en claro."""
    encontradas = []
    for servicio in SERVICIOS_CON_BASE:
        async with conexion_a(servicio) as conexion:
            for tabla, columna, tipo in await _columnas(conexion):
                if tipo == "bytea":
                    condicion = f"position(convert_to(:marca, 'UTF8') in \"{columna}\") > 0"
                else:
                    condicion = f'strpos("{columna}"::text, :marca) > 0'
                consulta = text(f'select count(*) from "{tabla}" where {condicion}')
                if (await conexion.execute(consulta, {"marca": marca})).scalar_one():
                    encontradas.append(f"{servicio}.{tabla}.{columna}")
    return encontradas


@pytest.fixture(scope="module")
def colegio_aliado() -> str:
    colegios = httpx.get(f"{GATEWAY}/v1/colegios", timeout=30).json()["colegios"]
    if not colegios:
        pytest.fail("no hay colegios aliados sembrados; falta `make bd-sembrar`")
    return colegios[0]["colegio_id"]


@pytest.fixture
def registro_con_apodo(cliente: httpx.Client, colegio_aliado: str) -> str:
    """Registra un acudiente ficticio con un hijo de apodo unico; devuelve el apodo."""
    apodo = _marca_ficticia()
    respuesta = cliente.post(
        "/v1/registro",
        json={
            "correo": f"qa-{uuid.uuid4().hex[:10]}@example.test",
            "clave": "clave-ficticia-qa",
            "hijos": [{"colegio_id": colegio_aliado, "grado": "Primero", "apodo": apodo}],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return apodo


@pytest.mark.nfr("NFR-SEG-07")
@pytest.mark.xfail(
    condition="TUKIT_LLAVE_CIFRADO" not in os.environ,
    strict=True,
    reason="H-A-03: sin TUKIT_LLAVE_CIFRADO el apodo del hijo queda en claro en identidad.estudiante",
)
async def test_el_apodo_del_hijo_no_queda_en_claro_en_ninguna_base(registro_con_apodo: str, record_property):
    apariciones = await _apariciones(registro_con_apodo)

    record_property("apariciones", ";".join(apariciones) or "0")
    assert apariciones == []


@pytest.mark.nfr("NFR-SEG-07")
def test_el_apodo_del_hijo_no_aparece_en_los_logs(registro_con_apodo: str, record_property):
    con_apodo = [r.name for r in logs_del_stack() if registro_con_apodo in r.read_text(errors="replace")]

    record_property("logs_con_apodo", len(con_apodo))
    assert con_apodo == []


# --------------------------------------------------------------- NFR-SEG-07: la lista con el nombre


def _lista_png(nombre: str) -> bytes:
    """Una lista escolar de una pagina con el nombre del estudiante escrito.

    El nombre va en los pixeles, como en una lista real, y ademas en un
    fragmento de texto del PNG: asi se puede buscar en los bytes sin OCR.
    """
    imagen = Image.new("RGB", (900, 360), "white")
    lienzo = ImageDraw.Draw(imagen)
    lienzo.text((30, 30), "LISTA DE UTILES 2026 - GRADO PRIMERO", fill="black")
    lienzo.text((30, 70), f"Estudiante: {nombre}", fill="black")
    lienzo.text((30, 130), "2  Cuaderno cuadriculado de 100 hojas", fill="black")
    lienzo.text((30, 160), "1  Caja de colores x 12", fill="black")
    metadatos = PngImagePlugin.PngInfo()
    metadatos.add_text("Comment", f"Estudiante: {nombre}")
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", pnginfo=metadatos)
    return salida.getvalue()


@pytest.fixture(scope="module")
def inteligencia_grabada(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, Path]]:
    """Una inteligencia aparte que graba las paginas en vez de mandarlas a Gemini."""
    carpeta = tmp_path_factory.mktemp("lector-grabado")
    capturas = carpeta / "capturas"
    with instancia(
        "inteligencia_lector_grabado",
        carpeta / "inteligencia.log",
        PYTHONPATH=str(Path(__file__).resolve().parent),
        TUKIT_QA_CAPTURAS=str(capturas),
    ) as base:
        yield base, capturas


@pytest.fixture(scope="module")
def subida_grabada(inteligencia_grabada: tuple[str, Path], colegio_aliado: str) -> dict[str, Any]:
    """Sube la lista con el nombre ficticio y junta lo que salio y lo que quedo."""
    base, capturas = inteligencia_grabada
    nombre = _marca_ficticia()
    lista = _lista_png(nombre)
    respuesta = httpx.post(
        f"{base}/v1/listas/subir",
        data={
            "hijos": json.dumps([{"referencia": "hijo-1", "colegio_id": colegio_aliado, "grado": "Primero"}]),
            "referencia": "hijo-1",
        },
        files={"archivo": ("lista.png", lista, "image/png")},
        timeout=60,
    )
    captura = capturas / "pagina-1.bin"
    return {
        "nombre": nombre,
        "lista": lista,
        "respuesta": respuesta,
        "salida": captura.read_bytes() if captura.exists() else None,
    }


@pytest.mark.nfr("NFR-SEG-07")
def test_la_subida_llega_hasta_el_lector_y_el_catalogo(subida_grabada: dict[str, Any], record_property):
    """Control: la subida se acepta y la pagina pasa por el lector grabado."""
    respuesta = subida_grabada["respuesta"]

    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json()["subidas"][0]["version_id"]
    assert subida_grabada["salida"] is not None
    record_property("sha256_subida", hashlib.sha256(subida_grabada["lista"]).hexdigest())
    record_property("sha256_salida", hashlib.sha256(subida_grabada["salida"]).hexdigest())


@pytest.mark.nfr("NFR-SEG-07")
@pytest.mark.xfail(
    strict=True,
    reason="H-C-15: la pagina sale hacia el proveedor de IA tal como se subio, con el nombre del menor",
)
def test_la_pagina_que_sale_hacia_el_modelo_va_sin_el_nombre(subida_grabada: dict[str, Any]):
    salida = subida_grabada["salida"]

    assert salida is not None
    assert salida != subida_grabada["lista"], "ningun paso de depuracion cambio la pagina antes del modelo"
    assert subida_grabada["nombre"].encode() not in salida


@pytest.mark.nfr("NFR-SEG-07")
@pytest.mark.xfail(
    strict=True,
    reason="H-C-15: catalogo.tarea_importacion.documento guarda el archivo original con el nombre del menor",
)
async def test_el_catalogo_no_guarda_el_nombre_del_menor(subida_grabada: dict[str, Any], record_property):
    version_id = subida_grabada["respuesta"].json()["subidas"][0]["version_id"]
    async with conexion_a("catalogo") as conexion:
        documento = (
            await conexion.execute(
                text("select documento from tarea_importacion where version_id = :v"), {"v": version_id}
            )
        ).scalar_one()
    apariciones = await _apariciones(subida_grabada["nombre"])

    record_property("apariciones", ";".join(apariciones) or "0")
    assert documento is None or subida_grabada["nombre"].encode() not in documento
    assert apariciones == []


@pytest.mark.nfr("NFR-SEG-07")
@pytest.mark.xfail(
    strict=True,
    reason="H-A-36: el entorno no instala el extra `pdf` (pypdfium2) y el stack rechaza toda lista en PDF",
)
def test_el_stack_lee_una_lista_en_pdf(cliente: httpx.Client, colegio_aliado: str):
    """Con el render instalado, el PDF pasaria al lector; sin clave, el rechazo seria otro."""
    pdf = io.BytesIO()
    Image.new("RGB", (600, 300), "white").save(pdf, format="PDF")
    respuesta = cliente.post(
        "/v1/listas/subir",
        data={
            "hijos": json.dumps([{"referencia": "hijo-1", "colegio_id": colegio_aliado, "grado": "Primero"}]),
            "referencia": "hijo-1",
        },
        files={"archivo": ("lista.pdf", pdf.getvalue(), "application/pdf")},
        timeout=60,
    )

    assert respuesta.status_code in (202, 422), respuesta.text
    assert respuesta.json().get("error") != "pdf_ilegible", respuesta.text
