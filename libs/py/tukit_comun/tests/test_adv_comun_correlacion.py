"""Fase 5 de QA, ADV-10: un `x-correlation-id` hostil o ajeno no rompe el hilo de la peticion.

El id lo pone el cliente (`http.py`, `cid = cabecera or uuid4().hex`) y se pega
en cada linea de log, en cada llamada saliente y en la respuesta. Que se acepte
sin sanear ya esta reproducido en `test_comun_http_arranque.py` (H-C-09, punto
4). Aqui se prueba lo que eso permitiria si el resto fallara:

- que una comilla, una barra o un salto de linea en el id no partan ni
  falsifiquen la linea del log JSON (un agregador la parsea sin regex);
- que con muchas peticiones a la vez ninguna respuesta, ningun log y ninguna
  llamada saliente lleven el id de OTRA peticion (el `contextvar` aisla).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Iterator

import httpx
import pytest
from tukit_comun.http import (
    CABECERA_CORRELACION,
    _sellar_correlacion,
    crear_app,
    fijar_correlacion,
    id_de_correlacion,
    reset_correlacion,
)
from tukit_comun.registro import _FiltroCorrelacion, _FormatoJSON

pytestmark = pytest.mark.nfr("NFR-SEG-06")

_log = logging.getLogger("tukit.prueba.adv10")


@pytest.fixture(autouse=True)
def _caso(record_property) -> None:
    record_property("caso_adv", "ADV-10")


@pytest.fixture
def registro_json() -> Iterator[io.StringIO]:
    """Un handler con el filtro y el formato JSON reales, escribiendo a un buffer."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.addFilter(_FiltroCorrelacion())
    handler.setFormatter(_FormatoJSON())
    nivel = _log.level
    _log.addHandler(handler)
    _log.setLevel(logging.INFO)
    yield buffer
    _log.removeHandler(handler)
    _log.setLevel(nivel)


class TestElLogNoSeParte:
    @pytest.mark.parametrize(
        "hostil",
        [
            'req" , "nivel": "CRITICAL',
            'req\\"}\n{"nivel": "ERROR", "mensaje": "falso"',
            "req\r\nERROR tukit.pago [otro] cobro duplicado",
            "req\u2028separador\u2029fin",
        ],
        ids=["comillas", "json-incrustado", "crlf", "separador-unicode"],
    )
    def test_un_id_hostil_deja_una_sola_linea_json_con_el_id_intacto(self, registro_json, hostil):
        token = fijar_correlacion(hostil)
        try:
            _log.info("pago aprobado")
        finally:
            reset_correlacion(token)

        # JSON Lines separa solo por `\n`. U+2028 y U+2029 salen literales
        # (`ensure_ascii=False`): un lector que corte con `str.splitlines()` si
        # partiria esta linea (`Tukit-QA/trazabilidad/adversariales.md`, ADV-10).
        lineas = registro_json.getvalue().rstrip("\n").split("\n")
        assert len(lineas) == 1
        cuerpo = json.loads(lineas[0])
        assert cuerpo["correlacion"] == hostil
        assert cuerpo["nivel"] == "INFO"
        assert cuerpo["mensaje"] == "pago aprobado"


class TestNingunIdAjeno:
    async def test_cincuenta_peticiones_a_la_vez_no_cruzan_sus_ids(self, registro_json, record_property):
        salientes: list[tuple[str, str]] = []

        def destino(peticion: httpx.Request) -> httpx.Response:
            salientes.append((peticion.url.params["de"], peticion.headers.get(CABECERA_CORRELACION, "")))
            return httpx.Response(200, json={})

        # El pool de un servicio, con el hook real, hacia un destino en memoria.
        pool = httpx.AsyncClient(
            transport=httpx.MockTransport(destino), event_hooks={"request": [_sellar_correlacion]}
        )
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.get("/eco/{nombre}")
        async def eco(nombre: str) -> dict:
            # Se cede el turno entre cada paso para que las peticiones se intercalen.
            await asyncio.sleep(0)
            _log.info("atiendo %s", nombre)
            await asyncio.sleep(0)
            await pool.get("http://otro.servicio.test/x", params={"de": nombre})
            await asyncio.sleep(0)
            return {"nombre": nombre, "cid": id_de_correlacion()}

        nombres = [f"req-{n:02d}" for n in range(50)]
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://prueba"
            ) as cliente:
                respuestas = await asyncio.gather(
                    *(
                        cliente.get(f"/eco/{nombre}", headers={CABECERA_CORRELACION: f"cid-{nombre}"})
                        for nombre in nombres
                    )
                )
        finally:
            await pool.aclose()

        cruzadas = [
            r.json()["nombre"]
            for r in respuestas
            if r.json()["cid"] != f"cid-{r.json()['nombre']}"
            or r.headers[CABECERA_CORRELACION] != f"cid-{r.json()['nombre']}"
        ]
        salientes_cruzadas = [de for de, cid in salientes if cid != f"cid-{de}"]
        logs = [json.loads(linea) for linea in registro_json.getvalue().rstrip("\n").split("\n")]
        logs_cruzados = [r for r in logs if r["correlacion"] != f"cid-{r['mensaje'].split()[-1]}"]
        record_property("peticiones", len(nombres))
        record_property("ids_cruzados", len(cruzadas) + len(salientes_cruzadas) + len(logs_cruzados))
        assert len(salientes) == len(logs) == len(nombres)
        assert cruzadas == []
        assert salientes_cruzadas == []
        assert logs_cruzados == []
        assert id_de_correlacion() is None

    async def test_la_respuesta_de_error_lleva_el_id_de_su_peticion_y_no_otro(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.get("/falla")
        async def falla() -> dict:
            await asyncio.sleep(0)
            raise ValueError("boom")

        transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
            primera, segunda = await asyncio.gather(
                cliente.get("/falla", headers={CABECERA_CORRELACION: "cid-a"}),
                cliente.get("/falla", headers={CABECERA_CORRELACION: "cid-b"}),
            )

        assert primera.status_code == segunda.status_code == 500
        assert "cid-b" not in primera.text + str(primera.headers)
        assert "cid-a" not in segunda.text + str(segunda.headers)
