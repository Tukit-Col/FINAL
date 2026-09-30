"""La previsualizacion de kits de una lista de onboarding, ANTES de aprobarla.

El admin sube un PDF (`POST /v1/admin/onboarding`), el catalogo guarda una
version VIGENTE pero SIN revisar, y antes de aprobarla quiere ver como quedan
los tres kits. Este endpoint (`POST /v1/admin/onboarding/{version_id}/preview`)
crea un trabajo desechable con `origen='preview_onboarding'`, lo corre de forma
SINCRONICA (no fire-and-forget) y devuelve el `trabajo_id`/`estado`. El admin
lee los kits con el `GET /v1/admin/trabajos/{id}` de siempre.

La version del PATH se previsualiza tal cual (vigente o borrador): el pipeline
lee sus items por `version_id` con `revision()`. Como llega SIN revisar, toma la
ruta LENTA (emparejar + NSGA-II): eso es exactamente la vista previa que se
quiere, y es lo que estas pruebas defienden observando que `emparejar` SI se
llamo y que `resueltos` (la ruta rapida) NO.

Se prueba con `ASGITransport` y el motor en memoria, con un `CatalogoFalso`
extendido que expone `revision(version_id)` por (colegio, grado, anio). No hay
Gemini: la ruta lenta llama a `emparejar`, que el doble responde desde memoria.
"""

from __future__ import annotations

import httpx
import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido

COLEGIO = "11111111-1111-5111-8111-111111111111"
VERSION_VIGENTE = "ver-vigente-1"


class CatalogoPreview(CatalogoFalso):
    """CatalogoFalso que resuelve versiones por id con `revision()`.

    `self.versiones` es el conjunto de version_id que EXISTEN para
    (COLEGIO, self.grado, 2026); `revision(vid)` devuelve la cabecera + items de
    una de ellas, o levanta `RemotoCaido` (que el endpoint traduce a 404) si no
    existe —igual que el catalogo real, que resuelve `/revision` por version_id
    sin importar si es la vigente—. Registra las llamadas en `self.llamadas`.
    """

    def __init__(self, *, version_vigente: str | None = VERSION_VIGENTE, versiones=None, **kw):
        super().__init__(**kw)
        if versiones is None:
            versiones = [] if version_vigente is None else [version_vigente]
        self.versiones = list(versiones)

    async def revision(self, version_id: str) -> dict:
        self.llamadas.append("revision")
        if version_id not in self.versiones:
            raise RemotoCaido("catalogo", "/revision respondio 404")
        return {
            "version_id": version_id,
            "lista_id": "lista-1",
            "colegio_id": COLEGIO,
            "grado": self.grado,
            "anio_lectivo": 2026,
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
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


def _cuerpo(**kw):
    datos = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
    datos.update(kw)
    return datos


class TestPreviewFeliz:
    async def test_arma_tres_kits_por_la_ruta_lenta(self, cliente, catalogo, motor):
        respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())

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
        respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
        trabajo_id = respuesta.json()["trabajo_id"]

        vista = await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")
        cuerpo = vista.json()
        assert cuerpo["origen"] == "preview_onboarding"
        # El hijo sintetico del preview guarda el version_id de su lista: es a
        # donde la consola enlaza para aprobarla (el preview no se publica).
        assert cuerpo["hijos"][0]["version_id"] == VERSION_VIGENTE


class TestPreviewVersionAware:
    async def test_previsualizar_un_borrador_no_vigente_funciona(self, motor):
        # El caso de EDITAR: el borrador nace SIN vigencia (el acudiente sigue
        # viendo la aprobada) y aun asi se previsualiza por su version_id. Antes
        # esto era un 409 "existe una version mas nueva"; ahora se arma.
        catalogo = _catalogo_con_lista()
        catalogo.versiones = ["ver-borrador-2"]  # el borrador, NO la vigente vieja
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
        # Un version_id que no existe en el catalogo: 404, no 409.
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
        # La version existe pero es del grado Cuarto; se pide previsualizarla
        # como si fuera de Quinto: no corresponde a ese (colegio, grado, anio).
        respuesta = await cliente.post(
            f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview",
            json=_cuerpo(grado="Quinto"),
        )
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "version_no_corresponde"


class TestPreviewNoEsFireAndForget:
    async def test_los_kits_estan_listos_al_responder(self, cliente, catalogo):
        # Si fuera fire-and-forget, los kits no estarian escritos todavia cuando
        # respondemos. Se lee inmediatamente y ya tienen que estar.
        respuesta = await cliente.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
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
            respuesta = await http.post(f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo())
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == EstadoTrabajo.FALLIDO.value


class TestPreviewEsIdempotente:
    async def test_tres_previews_dejan_uno_en_la_cola(self, cliente, catalogo):
        # El bug original: cada clic de "Previsualizar los 3 kits" dejaba un
        # trabajo desechable mas. Ahora previsualizar descarta el preview
        # anterior del mismo (colegio, grado, anio): 3 clics -> 1 trabajo.
        ids = []
        for _ in range(3):
            respuesta = await cliente.post(
                f"/v1/admin/onboarding/{VERSION_VIGENTE}/preview", json=_cuerpo()
            )
            assert respuesta.status_code == 200
            ids.append(respuesta.json()["trabajo_id"])

        # Tres trabajos distintos, pero solo el ultimo sigue vivo.
        assert len({*ids}) == 3
        cola = (await cliente.get("/v1/admin/cola")).json()
        vivos = [t["trabajo_id"] for t in cola["trabajos"]]
        assert ids[-1] in vivos
        assert ids[0] not in vivos and ids[1] not in vivos
        # Un solo preview de este (colegio, grado) en la cola.
        assert sum(1 for t in cola["trabajos"] if t["trabajo_id"] in ids) == 1
