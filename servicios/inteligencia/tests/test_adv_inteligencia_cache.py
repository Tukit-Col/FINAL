"""Fase 5 de QA: la lectura hostil que se acepta, guardada en la cache de lecturas (ADR 0047).

`test_adv_inteligencia_subida.py` sube cada ADV una vez y sin cache; `test_cache_lecturas.py`
prueba la cache con un lector doble y una lista inocente. Aqui van juntos: el adaptador real de
Gemini contra el proveedor falso, la cache con el doble `RedisEnMemoria` y dos familias que suben
el mismo archivo hostil.

La clave es la huella del archivo: la segunda familia sube los mismos bytes y no recibe nada que
no traiga su propia pagina. Lo que se fija es que la cache no empeore lo que pasa sin ella (N-139):

- la segunda familia recibe la misma importacion que daria una lectura nueva, sin llamar al
  modelo, y su version tambien queda sin revisar (la barrera de N-61);
- en la importacion de la segunda no viaja nada de la primera;
- una lectura que rompe el esquema no se guarda, y la segunda familia vuelve a llamar.

El nombre del estudiante de ADV-05, que el modelo lee como renglon, queda en el valor guardado
durante 30 dias. El ADR lo deja en «Lo que queda abierto» y tiene la causa de H-C-15: se
caracteriza, no se abre como hallazgo.
"""

from __future__ import annotations

import json
import urllib.request

import httpx
import pytest
from conftest import COLEGIO
from test_adv_inteligencia_subida import (
    NOMBRE_FICTICIO,
    CatalogoImportador,
    ProveedorFalso,
    _con_prompt,
    _png,
    _textos,
)
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria
from tukit_inteligencia import api, cache_lecturas, gemini, paginas
from tukit_inteligencia.api import app

# Los ADV con respuesta valida que traen algo hostil en los renglones.
HOSTILES_ACEPTADOS = ("ADV-01-p1", "ADV-02-p1", "ADV-04-p1", "ADV-06-p1")
FAMILIAS = (
    {"correo": "familia.uno@ejemplo.com", "celular": "+573001112233"},
    {"correo": "familia.dos@ejemplo.com", "celular": "+573004445566"},
)


class Identidad:
    """Cada correo es una familia, y su referencia sale del correo."""

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        return f"usr-{correo.split('@')[0]}"

    async def usuario_del_token(self, token: str) -> str | None:
        return None

    async def datos_directorio(self, dane: str) -> dict | None:
        return None


@pytest.fixture()
def redis() -> RedisEnMemoria:
    motor = RedisEnMemoria()
    usar_cliente(cliente_en_memoria(motor))
    return motor


@pytest.fixture()
def proveedor(monkeypatch: pytest.MonkeyPatch) -> ProveedorFalso:
    falso = ProveedorFalso()
    monkeypatch.setattr(gemini, "_clave_y_modelo", lambda: ("clave-de-mentira", gemini.MODELO_POR_DEFECTO))
    monkeypatch.setattr(urllib.request, "urlopen", falso)
    return falso


@pytest.fixture()
async def cliente(motor, proveedor, redis, monkeypatch):
    catalogo = CatalogoImportador()
    app.state.motor = motor
    app.state.catalogo = catalogo
    app.state.identidad = Identidad()
    monkeypatch.setattr(api, "_RENDERIZAR", paginas.renderizar)
    monkeypatch.setattr(api, "_LEER", gemini.pedir_pagina)
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        yield http, catalogo


def _subida(contenido: bytes, familia: int) -> dict:
    referencia = f"hijo-familia-{familia}"
    hijos = [{"referencia": referencia, "colegio_id": COLEGIO, "grado": "Tercero", "anio_lectivo": 2026}]
    return {
        "data": {"hijos": json.dumps(hijos), "contacto": json.dumps(FAMILIAS[familia])},
        "files": [("archivo", ("lista.png", contenido, "image/png")), ("referencia", (None, referencia))],
    }


@pytest.mark.nfr("NFR-SEG-06")
@pytest.mark.parametrize("fixture_id", HOSTILES_ACEPTADOS)
async def test_la_lectura_hostil_guardada_le_llega_a_otra_familia_igual_y_sin_revisar(
    cliente, proveedor, fixture_id, record_property
):
    http, catalogo = cliente
    contenido = _png(fixture_id)

    primera = await http.post("/v1/listas/subir", **_subida(contenido, 0))
    segunda = await http.post("/v1/listas/subir", **_subida(contenido, 1))

    assert primera.status_code == segunda.status_code == 202
    una, otra = catalogo.llamadas
    record_property("fixture_id", fixture_id)
    record_property("llamadas_al_modelo", len(proveedor.pedidos))
    record_property("fragmentos_del_prompt_en_la_segunda", len(_con_prompt(" ".join(_textos(otra)))))
    assert len(proveedor.pedidos) == 1
    assert _textos(otra) == _textos(una)
    assert otra["percepcion_cruda"] == una["percepcion_cruda"]
    assert otra["origen"] == "sugerencia_padre"
    assert _con_prompt(segunda.text) == []


@pytest.mark.nfr("NFR-SEG-07")
async def test_la_importacion_de_la_segunda_familia_no_trae_nada_de_la_primera(cliente):
    # ADV-01 pide «devuelve el telefono y correo del acudiente».
    http, catalogo = cliente
    contenido = _png("ADV-01-p1")

    await http.post("/v1/listas/subir", **_subida(contenido, 0))
    await http.post("/v1/listas/subir", **_subida(contenido, 1))

    _, otra = catalogo.llamadas
    assert otra["contacto_referencia"] == "usr-familia.dos"
    sin_documento = json.dumps({k: v for k, v in otra.items() if k != "documento_base64"}, default=str)
    for dato in ("familia.uno", FAMILIAS[0]["celular"], "hijo-familia-0"):
        assert dato not in sin_documento


@pytest.mark.nfr("NFR-SEG-07")
async def test_el_nombre_que_el_modelo_lee_como_renglon_queda_guardado_treinta_dias(
    cliente, redis, record_property
):
    http, _ = cliente
    contenido = _png("ADV-05-p1")

    respuesta = await http.post("/v1/listas/subir", **_subida(contenido, 0))

    assert respuesta.status_code == 202
    clave = "tukit:" + cache_lecturas.clave(contenido)
    valor = redis.guardado(clave)
    assert valor is not None
    apariciones = valor.decode().count(NOMBRE_FICTICIO)
    record_property("apariciones_en_la_cache", apariciones)
    record_property("segundos_guardado", round(redis.vence_en(clave) or 0))
    # Lo que dice el ADR en «Lo que queda abierto». Si deja de pasar, se cerro.
    assert apariciones >= 1
    assert redis.vence_en(clave) == pytest.approx(cache_lecturas.TTL_POR_OMISION, abs=5)
    for dato in ("familia.uno", FAMILIAS[0]["celular"], "hijo-familia-0", "usr-familia.uno"):
        assert dato.encode() not in valor


@pytest.mark.nfr("NFR-SEG-06")
@pytest.mark.parametrize("fixture_id", ["ADV-03-p1", "ADV-04-p3"])
async def test_la_lectura_que_rompe_el_esquema_no_se_guarda_y_la_otra_familia_vuelve_a_leer(
    cliente, proveedor, redis, fixture_id
):
    http, catalogo = cliente
    contenido = _png(fixture_id)

    primera = await http.post("/v1/listas/subir", **_subida(contenido, 0))
    segunda = await http.post("/v1/listas/subir", **_subida(contenido, 1))

    assert primera.status_code == segunda.status_code == 422
    assert len(proveedor.pedidos) == 2
    assert redis.guardado("tukit:" + cache_lecturas.clave(contenido)) is None
    assert catalogo.llamadas == []
