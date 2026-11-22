from __future__ import annotations

import httpx
import pytest
from _ayudas_inteligencia import CatalogoPreview
from conftest import opcion, reconocido, renglon
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import EstadoTrabajo

COLEGIO = "11111111-1111-5111-8111-111111111111"
VERSION_VIGENTE = "ver-vigente-1"


def _catalogo_con_lista(version_vigente: str | None = VERSION_VIGENTE) -> CatalogoPreview:
    return CatalogoPreview(
        version_vigente=version_vigente,
        grado="Cuarto",
        renglones=[
            renglon(1, "2 cuadernos cuadriculados", cantidad=2),
            renglon(2, "1 cartuchera"),
        ],
        respuestas={
            "2 cuadernos cuadriculados": reconocido(
                "2 cuadernos cuadriculados",
                "C001",
                [
                    opcion("TK-C001-ECO", "economico", 4500),
                    opcion("TK-C001-CON", "confiable", 6000),
                ],
            ),
            "1 cartuchera": reconocido(
                "1 cartuchera",
                "C009",
                [
                    opcion("TK-C009-ECO", "economico", 8000),
                    opcion("TK-C009-CON", "confiable", 15000),
                ],
            ),
        },
    )


@pytest.fixture()
def catalogo():
    return _catalogo_con_lista()


@pytest.fixture()
async def cliente(motor, catalogo):
    app.state.motor = motor
    app.state.catalogo = catalogo
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


def _cuerpo(**kw):
    datos = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
    datos.update(kw)
    return datos


class TestPreviewFeliz:
    async def test_arma_ahorrador_y_premium_por_la_ruta_lenta(self, cliente, catalogo, motor):
        respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == EstadoTrabajo.ESPERA_REVISION.value
        trabajo_id = cuerpo["trabajo_id"]

        assert "emparejar" in catalogo.llamadas
        assert "resueltos" not in catalogo.llamadas

        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        assert vista.status_code == 200
        kits = vista.json()["kits"]
        assert {k["perfil"] for k in kits} == {"Ahorrador", "Premium"}

    async def test_el_trabajo_lleva_origen_preview(self, cliente, catalogo):
        respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
        trabajo_id = respuesta.json()["trabajo_id"]

        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        cuerpo = vista.json()
        assert cuerpo["origen"] == "preview_onboarding"
        assert cuerpo["hijos"][0]["version_id"] == VERSION_VIGENTE


class TestPreviewVersionAware:
    async def test_previsualizar_un_borrador_no_vigente_funciona(self, motor):
        catalogo = _catalogo_con_lista()
        catalogo.versiones = ["ver-borrador-2"]
        app.state.motor = motor
        app.state.catalogo = catalogo
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.post("/v1/admin/onboarding/ver-borrador-2/preview", json=_cuerpo())
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == EstadoTrabajo.ESPERA_REVISION.value


class TestPreviewGuardas:
    async def test_version_inexistente_es_404(self, cliente, catalogo):
        respuesta = await cliente.post("/v1/admin/onboarding/ver-que-no-existe/preview", json=_cuerpo())
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "version_no_existe"

    async def test_sin_lista_es_404(self, motor):
        catalogo = _catalogo_con_lista(version_vigente=None)
        app.state.motor = motor
        app.state.catalogo = catalogo
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "version_no_existe"

    async def test_version_de_otro_grado_es_409(self, cliente, catalogo):
        respuesta = await cliente.post(
            f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview",
            json=_cuerpo(grado="Quinto"),
        )
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "version_no_corresponde"


class TestPreviewNoEsFireAndForget:
    async def test_los_kits_estan_listos_al_responder(self, cliente, catalogo):
        respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
        trabajo_id = respuesta.json()["trabajo_id"]
        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        assert len(vista.json()["kits"]) == 2

    async def test_propaga_estado_fallido_si_no_hay_renglones(self, motor):
        catalogo = CatalogoPreview(version_vigente=VERSION_VIGENTE, grado="Cuarto", renglones=[])
        app.state.motor = motor
        app.state.catalogo = catalogo
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == EstadoTrabajo.FALLIDO.value


class TestPreviewEsIdempotente:
    async def test_tres_previews_dejan_uno_en_la_cola(self, cliente, catalogo):
        ids = []
        for _ in range(3):
            respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
            assert respuesta.status_code == 200
            ids.append(respuesta.json()["trabajo_id"])

        assert len({*ids}) == 3
        cola = (await cliente.get("/v1/admin/cola")).json()
        vivos = [t["trabajo_id"] for t in cola["trabajos"]]
        assert ids[-1] in vivos
        assert ids[0] not in vivos and ids[1] not in vivos
        assert sum(1 for t in cola["trabajos"] if t["trabajo_id"] in ids) == 1
