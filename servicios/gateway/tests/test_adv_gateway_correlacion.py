"""Fase 5 de QA, ADV-10 en la puerta: lo que hace con un `x-correlation-id` que no puso ella.

La puerta es el borde: reenvia a los servicios de atras el id que el middleware
leyo de la peticion (`api.py`, «aqui se acuña el id de correlacion»). Lo que el
cliente escribe en esa cabecera llega asi a cada servicio, a cada log y a cada
llamada que esos servicios hagan despues. Se prueba con destinos de mentira
(`_poner` de `test_gateway_proxy.py`, ninguna red):

- que peticiones simultaneas con ids propios no se los cruzan, y que sin id
  cada una recibe uno distinto;
- que un id hostil no llega crudo a los servicios de atras (H-C-09, punto 4);
- que un byte no ASCII en una cabecera no tumba la peticion (H-A-51).
"""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest
from test_gateway_proxy import SERVICIOS, _poner
from tukit_comun.http import crear_app
from tukit_gateway.api import app

pytestmark = pytest.mark.nfr("NFR-SEG-06")

ID_SANO = re.compile(r"[A-Za-z0-9._-]{1,128}")


@pytest.fixture(autouse=True)
def _caso(record_property, monkeypatch: pytest.MonkeyPatch) -> None:
    record_property("caso_adv", "ADV-10")
    for nombre in SERVICIOS:
        monkeypatch.setenv(f"TUKIT_{nombre.upper()}_URL", f"http://{nombre}.example.test")


def _cliente() -> httpx.AsyncClient:
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transporte, base_url="http://prueba")


class TestLosIdsNoSeCruzan:
    async def test_treinta_peticiones_a_la_vez_llevan_cada_una_su_id_hasta_atras(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200, json={"de": p.url.params["de"]}))

        async with _cliente() as cliente:
            respuestas = await asyncio.gather(
                *(
                    cliente.get(
                        "/v1/catalogo/conceptos", params={"de": n}, headers={"x-correlation-id": f"cid-{n}"}
                    )
                    for n in range(30)
                )
            )

        cruzadas = [
            r.json()["de"] for r in respuestas if r.headers["x-correlation-id"] != f"cid-{r.json()['de']}"
        ]
        atras_cruzadas = [
            p.url.params["de"]
            for p in atras.peticiones
            if p.headers["x-correlation-id"] != f"cid-{p.url.params['de']}"
        ]
        assert len(atras.peticiones) == 30
        assert cruzadas == atras_cruzadas == []

    async def test_sin_id_treinta_peticiones_a_la_vez_reciben_treinta_ids_distintos(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        async with _cliente() as cliente:
            respuestas = await asyncio.gather(*(cliente.get("/v1/catalogo/conceptos") for _ in range(30)))

        acunados = {r.headers["x-correlation-id"] for r in respuestas}
        assert len(acunados) == 30
        assert {p.headers["x-correlation-id"] for p in atras.peticiones} == acunados
        assert all(ID_SANO.fullmatch(cid) for cid in acunados)


class TestElIdHostil:
    @pytest.mark.xfail(
        strict=True,
        reason="H-C-09 (punto 4): la puerta reenvia a los servicios de atras el x-correlation-id del "
        "cliente tal cual, sin sanearlo ni acotarlo",
    )
    @pytest.mark.parametrize(
        "hostil",
        ['req" , "nivel": "CRITICAL', "a" * 5000, "<script>alert(1)</script>"],
        ids=["comillas", "gigante", "html"],
    )
    async def test_un_id_hostil_no_llega_crudo_a_los_servicios_de_atras(
        self, monkeypatch, hostil, record_property
    ):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        async with _cliente() as cliente:
            respuesta = await cliente.get("/v1/catalogo/conceptos", headers={"x-correlation-id": hostil})

        recibido = atras.peticiones[0].headers["x-correlation-id"]
        record_property("largo_recibido_atras", len(recibido))
        assert respuesta.status_code == 200
        assert ID_SANO.fullmatch(recibido), f"atras recibe {recibido[:60]!r} ({len(recibido)} caracteres)"


class TestUnByteNoAscii:
    @pytest.mark.xfail(
        strict=True,
        reason="H-A-51: la puerta reenvia las cabeceras con httpx, que las codifica en ASCII; un byte no "
        "ASCII en cualquier cabecera reenviada (tambien x-correlation-id) es un UnicodeEncodeError y un 500",
    )
    @pytest.mark.parametrize(
        "cabecera",
        [
            {"x-correlation-id": "acudiente-ñandú".encode()},
            {"x-correlation-id": "ok", "x-nota": "Muñoz".encode("latin-1")},
        ],
        ids=["en-la-correlacion", "en-otra-cabecera"],
    )
    async def test_la_peticion_no_se_cae_con_un_500(self, monkeypatch, cabecera, record_property):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200, json={"ok": True}))

        async with _cliente() as cliente:
            respuesta = await cliente.get("/v1/catalogo/conceptos", headers=cabecera)

        record_property("status", respuesta.status_code)
        record_property("llegaron_atras", len(atras.peticiones))
        assert respuesta.status_code != 500, (
            f"500 con {len(atras.peticiones)} peticiones atras: {respuesta.text}"
        )

    async def test_un_servicio_de_atras_si_la_tolera(self):
        """El contraste: el middleware compartido la acepta; lo que falla es el reenvio de la puerta."""
        servicio = crear_app(titulo="Prueba", descripcion="banco")

        @servicio.get("/hola")
        async def hola() -> dict:
            return {"ok": True}

        transporte = httpx.ASGITransport(app=servicio, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
            respuesta = await cliente.get("/hola", headers={"x-correlation-id": "acudiente-ñandú".encode()})

        assert respuesta.status_code == 200
