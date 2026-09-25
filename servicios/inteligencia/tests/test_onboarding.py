"""El onboarding multipart: un PDF entra, percepcion decide, catalogo recibe.

Se prueba con `ASGITransport` y el motor de prueba, igual que el resto de la
superficie HTTP. Los dos puertos de percepcion (`renderizar` y `leer`) se
sustituyen por dobles para no depender ni de pypdfium2 ni de una llave de
Gemini, y el cliente del catalogo se inyecta en `app.state` como una
implementacion en memoria que registra la llamada a `importar_lista`.

Lo que se fija aqui es el contrato entre servicios: que percepcion se llame
con los bytes subidos, que un `descripcion` se mapee a `texto_original`, que
una `cantidad` en null se vuelva 1, que el PDF viaje en base64 y que un
archivo de varios grados se rechace con 422 sin devolver el archivo.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from tukit_inteligencia import api
from tukit_inteligencia.api import app
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida, Percepcion

COLEGIO = "11111111-1111-5111-8111-111111111111"


class CatalogoImportador:
    """Doble del puerto del catalogo que solo necesita `importar_lista`."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    async def importar_lista(
        self,
        *,
        colegio_id: str,
        grado: str,
        anio_lectivo: int,
        items: list[dict],
        documento_base64: str,
        percepcion_cruda: list[dict],
        origen: str = "onboarding",
        **_extra: object,
    ) -> dict:
        self.llamadas.append(
            {
                "colegio_id": colegio_id,
                "grado": grado,
                "anio_lectivo": anio_lectivo,
                "items": items,
                "documento_base64": documento_base64,
                "percepcion_cruda": percepcion_cruda,
                "origen": origen,
            }
        )
        return {"version_id": "ver-1", "tarea_id": "tar-1", "items": len(items), "revisada": False}


@pytest.fixture()
def catalogo():
    return CatalogoImportador()


@pytest.fixture()
async def cliente(motor, catalogo, monkeypatch):
    app.state.motor = motor
    app.state.catalogo = catalogo

    # Los dos puertos de percepcion se sustituyen por dobles: una pagina con
    # un grado y dos items, uno de ellos sin cantidad.
    def _renderizar(_contenido: bytes) -> list[bytes]:
        return [b"p1"]

    def _leer(_png: bytes, _numero: int) -> PaginaLeida:
        return PaginaLeida(
            grados=["Cuarto"],
            completa=True,
            items=[
                ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.91),
                ItemExtraido(descripcion="1 caja de colores", cantidad=None, confianza=0.8),
            ],
        )

    monkeypatch.setattr(api, "_RENDERIZAR", _renderizar)
    monkeypatch.setattr(api, "_LEER", _leer)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


def _multipart(contenido: bytes = b"%PDF-falso", **campos):
    datos = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": "2026"}
    datos.update({k: str(v) for k, v in campos.items()})
    return {"data": datos, "files": {"archivo": ("lista.pdf", contenido, "application/pdf")}}


class TestOnboardingFeliz:
    async def test_percibe_mapea_e_importa(self, cliente, catalogo):
        pdf = b"%PDF-1.4 contenido"
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(pdf))

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["version_id"] == "ver-1"
        assert cuerpo["grado"] == "Cuarto"
        assert cuerpo["items"] == 2

        assert len(catalogo.llamadas) == 1
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["grado"] == "Cuarto"
        assert llamada["anio_lectivo"] == 2026

    async def test_mapea_descripcion_y_cantidad_nula(self, cliente, catalogo):
        await cliente.post("/v1/admin/onboarding", **_multipart(b"%PDF-x"))

        items = catalogo.llamadas[0]["items"]
        assert items[0]["texto_original"] == "2 cuadernos cuadriculados"
        assert items[0]["cantidad"] == 2
        assert items[0]["confianza"] == 0.91
        # Una cantidad en null se vuelve 1: un item pedido al menos una vez.
        assert items[1]["texto_original"] == "1 caja de colores"
        assert items[1]["cantidad"] == 1

    async def test_el_pdf_viaja_en_base64_y_hay_evidencia_por_pagina(self, cliente, catalogo):
        pdf = b"%PDF-1.4 bytes crudos"
        await cliente.post("/v1/admin/onboarding", **_multipart(pdf))

        llamada = catalogo.llamadas[0]
        assert base64.b64decode(llamada["documento_base64"]) == pdf
        cruda = llamada["percepcion_cruda"]
        assert len(cruda) == 1
        assert cruda[0]["pagina"] == 1
        assert "crudo" in cruda[0]


class TestOnboardingRechazado:
    async def test_varios_grados_es_422_sin_devolver_el_archivo(self, cliente, catalogo, monkeypatch):
        def _leer_multi(_png: bytes, numero: int) -> PaginaLeida:
            grado = "Cuarto" if numero == 1 else "Quinto"
            return PaginaLeida(grados=[grado], items=[ItemExtraido(descripcion="lapiz")])

        monkeypatch.setattr(api, "_RENDERIZAR", lambda _c: [b"p1", b"p2"])
        monkeypatch.setattr(api, "_LEER", _leer_multi)

        marcador = b"%PDF-marcador-secreto-del-cliente"
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(marcador))

        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "lista_de_varios_grados"
        assert cuerpo["grados_detectados"] == ["Cuarto", "Quinto"]
        # El archivo del cliente NUNCA vuelve en el error.
        assert base64.b64encode(marcador).decode() not in respuesta.text
        assert "marcador-secreto" not in respuesta.text
        assert catalogo.llamadas == []

    async def test_una_percepcion_rechazada_no_toca_el_catalogo(self, cliente, catalogo, monkeypatch):
        def _percibir(_contenido, **_kw):
            return Percepcion(
                aceptada=False,
                error="archivo_vacio",
                mensaje="El archivo llego vacio.",
            )

        monkeypatch.setattr(api, "_percibir_onboarding", _percibir)
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(b""))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "archivo_vacio"
        assert catalogo.llamadas == []
