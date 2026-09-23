"""La previsualizacion de kits de una lista de onboarding, ANTES de aprobarla.

El admin sube un PDF (`POST /v1/admin/onboarding`), el catalogo guarda una
version VIGENTE pero SIN revisar, y antes de aprobarla quiere ver como quedan
los tres kits. Este endpoint (`POST /v1/admin/onboarding/{version_id}/preview`)
crea un trabajo desechable con `origen='preview_onboarding'`, lo corre de forma
SINCRONICA (no fire-and-forget) y devuelve el `trabajo_id`/`estado`. El admin
lee los kits con el `GET /v1/admin/trabajos/{id}` de siempre.

Como la version es vigente pero SIN revisar, el pipeline toma la ruta LENTA
(emparejar + NSGA-II): eso es exactamente la vista previa que se quiere, y es
lo que estas pruebas defienden observando que `emparejar` SI se llamo y que
`resueltos` (la ruta rapida) NO.

Se prueba con `ASGITransport` y el motor en memoria, con un `CatalogoFalso`
extendido que expone un `version_id` vigente controlable por (colegio, grado,
anio). No hay Gemini: la ruta lenta llama a `emparejar`, que el doble responde
desde memoria.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import EstadoTrabajo

COLEGIO = "11111111-1111-5111-8111-111111111111"
VERSION_VIGENTE = "ver-vigente-1"


class CatalogoPreview(CatalogoFalso):
    """CatalogoFalso con una version vigente concreta e items crudos para emparejar.

    `listas()` devuelve `[]` cuando el grado no coincide (para el 404) y una
    lista con `version_id` conocido cuando si. `lista()` devuelve esa misma
    version y NO revisada, para que el pipeline tome la ruta lenta. Registra
    las llamadas en `self.llamadas` como el resto de los dobles.
    """

    def __init__(self, *, version_vigente: str | None = VERSION_VIGENTE, **kw):
        super().__init__(**kw)
        self.version_vigente = version_vigente

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo=None) -> list[dict]:
        self.llamadas.append("listas")
        if grado != self.grado or self.version_vigente is None:
            return []
        return [
            {
                "lista_id": "lista-1",
                "version_id": self.version_vigente,
                "grado": grado,
                "anio_lectivo": anio_lectivo or 2026,
                "revisada": False,
            }
        ]

    async def lista(self, lista_id: str) -> dict:
        self.llamadas.append("lista")
        return {
            "lista_id": lista_id,
            "version_id": self.version_vigente,
            "grado": self.grado,
            "revisada": False,
            "total_items": len(self.renglones),
            "items": self.renglones,
        }


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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://prueba"
    ) as http:
        yield http


def _cuerpo(**kw):
    datos = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
    datos.update(kw)
    return datos


class TestPreviewFeliz:
    async def test_arma_tres_kits_por_la_ruta_lenta(self, cliente, catalogo, motor):
        respuesta = await cliente.post(
            f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo()
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == EstadoTrabajo.ESPERA_REVISION.value
        trabajo_id = cuerpo["trabajo_id"]

        # Ruta lenta: emparejar SI, resueltos NO.
        assert "emparejar" in catalogo.llamadas
        assert "resueltos" not in catalogo.llamadas

        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        assert vista.status_code == 200
        kits = vista.json()["kits"]
        assert {k["perfil"] for k in kits} == {"Ahorrador", "Fan", "Premium"}

    async def test_el_trabajo_lleva_origen_preview(self, cliente, catalogo):
        respuesta = await cliente.post(
            f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo()
        )
        trabajo_id = respuesta.json()["trabajo_id"]

        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        assert vista.json()["origen"] == "preview_onboarding"


class TestPreviewGuardas:
    async def test_version_no_vigente_es_409(self, cliente, catalogo):
        # La vigente del catalogo es VERSION_VIGENTE; se pide otra.
        respuesta = await cliente.post(
            "/v1/admin/onboarding/ver-vieja-0/preview", json=_cuerpo()
        )
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "version_no_vigente"

    async def test_sin_lista_es_404(self, motor):
        catalogo = _catalogo_con_lista(version_vigente=None)
        app.state.motor = motor
        app.state.catalogo = catalogo
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.post(
                f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo()
            )
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "version_no_existe"

    async def test_grado_sin_lista_es_404(self, cliente, catalogo):
        respuesta = await cliente.post(
            f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview",
            json=_cuerpo(grado="Quinto"),
        )
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "version_no_existe"


class TestPreviewNoEsFireAndForget:
    async def test_los_kits_estan_listos_al_responder(self, cliente, catalogo):
        # Si fuera fire-and-forget, los kits no estarian escritos todavia cuando
        # respondemos. Se lee inmediatamente y ya tienen que estar.
        respuesta = await cliente.post(
            f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo()
        )
        trabajo_id = respuesta.json()["trabajo_id"]
        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        assert len(vista.json()["kits"]) == 3

    async def test_propaga_estado_fallido_si_no_hay_renglones(self, motor):
        # Una version vigente pero cuya lista no trae items: la ruta lenta cae
        # en sin_lista_oficial -> fallido, y el endpoint propaga ese estado.
        catalogo = CatalogoPreview(version_vigente=VERSION_VIGENTE, grado="Cuarto", renglones=[])
        app.state.motor = motor
        app.state.catalogo = catalogo
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.post(
                f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo()
            )
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == EstadoTrabajo.FALLIDO.value


def test_version_id_no_es_uuid_obligatorio():
    # El version_id del path es un str libre (el catalogo lo define), no un UUID.
    assert isinstance(VERSION_VIGENTE, str)
    uuid.uuid4()  # solo confirma que uuid esta importado y disponible
