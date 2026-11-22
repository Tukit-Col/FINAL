"""Fase 6 de QA: lo que la puerta no limita y no corta (NFR-SEG-03 y NFR-DIS-05).

`test_gateway_proxy.py` caracteriza el reenvio tal como es: un `AsyncClient`
nuevo por peticion, sin pool ni disyuntor, con 300 s de espera y un 503 cuando
el de atras no esta. Aqui se escriben las pruebas de los patrones que la puerta
deberia aplicar, por ser el unico punto por el que pasa todo el trafico:

- **Tope del cuerpo (413).** SDD:1467-1475 pone 10 MB en el borde; hoy solo
  existe en el frontend (H-C-07). Un cuerpo de 11 MiB, por encima de 10 MB en
  cualquiera de sus dos lecturas, deberia cortarse sin tocar el destino.
- **Limite de tasa (429).** La matriz pide «429 tras N peticiones por origen».
  Desde 45dc0b7 N es el tope general de la puerta por IP (ADR 0047); antes se
  probaba con N = 100 sin respaldo en v2.0 (decision N-71, H-C-07).
- **Bulkhead.** Un destino colgado no frena a otro, porque no comparten nada.
  Lo que se anota es que tampoco hay tope: cada peticion abre su conexion.
- **Disyuntor.** Tras cinco fallos seguidos la puerta sigue tocando el destino
  (H-A-33; la prueba contra el stack vivo esta en `ensayos/integracion`).

Destinos de mentira (`_poner`, `httpx.MockTransport`): ninguna red.
"""

from __future__ import annotations

import asyncio
import hashlib

import httpx
import pytest
from test_gateway_proxy import SERVICIOS, _poner
from tukit_gateway import limite
from tukit_gateway.api import app

ORIGEN = ("203.0.113.7", 50000)  # TEST-NET-3 (RFC 5737): una IP de documentacion
MIB = 1024 * 1024


@pytest.fixture(autouse=True)
def _destinos_ficticios(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los mismos hosts ficticios de `test_gateway_proxy`: su autouse no viaja con el import."""
    for nombre in SERVICIOS:
        monkeypatch.setenv(f"TUKIT_{nombre.upper()}_URL", f"http://{nombre}.example.test")


def _puerta() -> httpx.AsyncClient:
    """Un cliente que llega a la puerta siempre desde la misma IP de origen."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=ORIGEN), base_url="http://prueba")


def _ok(peticion: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True})


@pytest.mark.nfr("NFR-SEG-03")
class TestElTopeDelCuerpo:
    async def test_un_cuerpo_de_un_mib_se_reenvia_intacto(self, monkeypatch, record_property):
        """El control: por debajo del tope, el cuerpo llega entero y byte a byte."""
        atras = _poner(monkeypatch, _ok)
        cuerpo = bytes(range(256)) * (MIB // 256)

        async with _puerta() as puerta:
            respuesta = await puerta.post(
                "/v1/listas/subir", content=cuerpo, headers={"content-type": "application/octet-stream"}
            )

        recibido = atras.peticiones[0].content
        record_property("bytes_enviados", len(cuerpo))
        record_property("bytes_recibidos_atras", len(recibido))
        assert respuesta.status_code == 200
        assert hashlib.sha256(recibido).hexdigest() == hashlib.sha256(cuerpo).hexdigest()

    # H-C-07 (413 en la puerta): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    async def test_un_cuerpo_de_mas_de_diez_mb_recibe_413_sin_tocar_el_destino(
        self, monkeypatch, record_property
    ):
        atras = _poner(monkeypatch, _ok)
        cuerpo = b"\0" * (11 * MIB)

        async with _puerta() as puerta:
            respuesta = await puerta.post(
                "/v1/listas/subir", content=cuerpo, headers={"content-type": "application/octet-stream"}
            )

        record_property("bytes_enviados", len(cuerpo))
        record_property("estado_http", respuesta.status_code)
        record_property("bytes_que_llegaron_atras", sum(len(p.content) for p in atras.peticiones))
        assert respuesta.status_code == 413, (
            f"la puerta respondio {respuesta.status_code} y reenvio {len(atras.peticiones[0].content)} bytes"
        )
        assert atras.peticiones == []


@pytest.mark.nfr("NFR-SEG-03")
class TestElLimiteDeTasa:
    # Salio de H-C-07 en `b6b6fe7` (corrida oe5 C3, clase a, N-185): 45dc0b7 pone el limite de
    # tasa en la puerta (ADR 0047, `limite.py`) con un tope general de 1.200 por IP cada 60 s.
    # Las 100 de N-71 no llegan a ese tope y seguian en 200 por eso, no por falta de limite: la
    # rafaga es ahora el tope por omision mas una, desde la misma IP.
    async def test_una_rafaga_desde_un_origen_que_pasa_el_tope_recibe_429(self, monkeypatch, record_property):
        atras = _poner(monkeypatch, _ok)
        general, _ = limite.niveles()

        async with _puerta() as puerta:
            estados = [
                (await puerta.get("/v1/catalogo/conceptos")).status_code for _ in range(general.por_ip + 1)
            ]

        record_property("tope_por_ip", general.por_ip)
        record_property("peticiones", len(estados))
        record_property("respuestas_429", estados.count(429))
        record_property("llegaron_al_destino", len(atras.peticiones))
        assert estados[:-1] == [200] * general.por_ip
        assert estados[-1] == 429, f"{estados.count(200)} de {len(estados)} respondieron 200; ninguna 429"
        assert len(atras.peticiones) == general.por_ip


@pytest.mark.nfr("NFR-DIS-05")
class TestUnDestinoColgadoNoFrenaAOtro:
    async def test_con_catalogo_colgado_identidad_sigue_respondiendo(self, monkeypatch, record_property):
        soltar = asyncio.Event()

        async def responder(peticion: httpx.Request) -> httpx.Response:
            if peticion.url.host == "catalogo.example.test":
                await soltar.wait()
            return httpx.Response(200, json={"servicio": peticion.url.host})

        atras = _poner(monkeypatch, responder)
        async with _puerta() as puerta:
            colgadas = [asyncio.create_task(puerta.get("/v1/catalogo/conceptos")) for _ in range(30)]
            for _ in range(100):
                if sum(p.url.host == "catalogo.example.test" for p in atras.peticiones) == 30:
                    break
                await asyncio.sleep(0)
            en_vuelo = sum(p.url.host == "catalogo.example.test" for p in atras.peticiones)

            respuestas = await asyncio.wait_for(
                asyncio.gather(*(puerta.get("/v1/colegios") for _ in range(10))), timeout=5.0
            )
            pendientes = sum(not t.done() for t in colgadas)
            soltar.set()
            al_final = await asyncio.wait_for(asyncio.gather(*colgadas), timeout=5.0)

        record_property("en_vuelo_hacia_catalogo_colgado", en_vuelo)
        record_property("pendientes_de_catalogo", pendientes)
        record_property("respuestas_de_identidad", sum(r.status_code == 200 for r in respuestas))
        # Sin pool no hay tope: las 30 llegan a la vez al destino colgado (H-A-33).
        assert en_vuelo == 30
        assert pendientes == 30
        assert [r.status_code for r in respuestas] == [200] * 10
        assert [r.status_code for r in al_final] == [200] * 30


@pytest.mark.nfr("NFR-DIS-05")
class TestLaPuertaCortaUnDestinoCaido:
    # H-A-33 (disyuntor): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    async def test_tras_cinco_fallos_las_siguientes_no_tocan_el_destino(self, monkeypatch, record_property):
        def caido(peticion: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("conexion rechazada", request=peticion)

        atras = _poner(monkeypatch, caido)
        async with _puerta() as puerta:
            estados = [(await puerta.get("/v1/catalogo/conceptos")).status_code for _ in range(8)]

        record_property("peticiones", len(estados))
        record_property("toques_al_destino_caido", len(atras.peticiones))
        assert estados == [503] * 8
        assert len(atras.peticiones) <= 5, f"{len(atras.peticiones)} de 8 peticiones tocaron el destino caido"
