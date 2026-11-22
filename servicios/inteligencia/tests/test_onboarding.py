from __future__ import annotations

import base64

import httpx
import pytest
from tukit_comun import derivar
from tukit_comun.http import ErrorDominio
from tukit_inteligencia.api import app
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida
from tukit_inteligencia.remoto import RemotoCaido
from tukit_inteligencia.routers.inteligencia import ColegioElegido

COLEGIO = "11111111-1111-5111-8111-111111111111"


class CatalogoImportador:

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
        colegio_datos: dict | None = None,
        contacto_referencia: str | None = None,
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
                "colegio_datos": colegio_datos,
                "contacto_referencia": contacto_referencia,
            }
        )
        return {"version_id": "ver-1", "tarea_id": "tar-1", "items": len(items), "revisada": False}


class IdentidadDirectorio:

    def __init__(self) -> None:
        self.directorio: dict[str, dict] = {}
        self.consultas: list[str] = []
        self.roles_por_token = {
            "tok-operador": ["operador"],
            "tok-admin": ["admin"],
            "tok-acudiente": ["acudiente"],
        }
        self.caida = False
        self.conocidos: list[dict] = []

    async def colegios_conocidos(self) -> list[dict]:
        return list(self.conocidos)

    async def datos_directorio(self, dane: str) -> dict | None:
        self.consultas.append(dane)
        return self.directorio.get(dane)

    async def sesion(self, token: str) -> dict | None:
        if self.caida:
            raise RemotoCaido("identidad", "simulada")
        if token not in self.roles_por_token:
            return None
        roles = [{"rol": r, "ambito": None} for r in self.roles_por_token[token]]
        return {"usuario_id": f"u-{token}", "roles": roles}


@pytest.fixture()
def catalogo():
    return CatalogoImportador()


@pytest.fixture()
def identidad():
    return IdentidadDirectorio()


@pytest.fixture()
def lecturas():
    return []


@pytest.fixture()
async def cliente(motor, catalogo, identidad, lecturas):
    app.state.motor = motor
    app.state.catalogo = catalogo
    app.state.identidad = identidad

    def _renderizar(_contenido: bytes) -> list[bytes]:
        return [b"p1"]

    def _leer(_png: bytes, numero: int) -> PaginaLeida:
        lecturas.append(numero)
        return PaginaLeida(
            grados=["Cuarto"],
            completa=True,
            items=[
                ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.91),
                ItemExtraido(descripcion="1 caja de colores", cantidad=None, confianza=0.8),
            ],
        )

    app.state.renderizar = _renderizar
    app.state.leer = _leer

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://prueba",
        headers={"Authorization": "Bearer tok-operador"},
    ) as http:
        yield http


def _multipart(contenido: bytes = b"%PDF-falso", **campos):
    datos = {"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": "2026"}
    datos.update({k: str(v) for k, v in campos.items()})
    datos = {k: v for k, v in datos.items() if v != "None"}
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


class TestGradoConfirmadoPorElAdmin:
    async def test_el_grado_confirmado_gana_sobre_lo_que_leyo_el_modelo(self, cliente, catalogo):
        def _leer(_png: bytes, _n: int) -> PaginaLeida:
            return PaginaLeida(grados=["Segundo"], items=[ItemExtraido(descripcion="cuaderno")])

        app.state.renderizar = lambda _c: [b"p1"]
        app.state.leer = _leer
        r = await cliente.post(
            "/v1/admin/onboarding", **_multipart(b"%PDF-m", grado="Octavo", grado_confirmado="1")
        )
        assert r.status_code == 200
        assert r.json()["grado"] == "Octavo"
        assert catalogo.llamadas[0]["grado"] == "Octavo"

    async def test_sin_confirmar_manda_lo_leido(self, cliente, catalogo):
        def _leer(_png: bytes, _n: int) -> PaginaLeida:
            return PaginaLeida(grados=["Segundo"], items=[ItemExtraido(descripcion="cuaderno")])

        app.state.renderizar = lambda _c: [b"p1"]
        app.state.leer = _leer
        r = await cliente.post("/v1/admin/onboarding", **_multipart(b"%PDF-n", grado="Octavo"))
        assert r.json()["grado"] == "Segundo"


class TestOnboardingRechazado:
    async def test_varios_grados_es_422_sin_devolver_el_archivo(self, cliente, catalogo):
        def _leer_multi(_png: bytes, numero: int) -> PaginaLeida:
            grado = "Cuarto" if numero == 1 else "Quinto"
            return PaginaLeida(grados=[grado], items=[ItemExtraido(descripcion="lapiz")])

        app.state.renderizar = lambda _c: [b"p1", b"p2"]
        app.state.leer = _leer_multi

        marcador = b"%PDF-marcador-secreto-del-cliente"
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(marcador))

        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "lista_de_varios_grados"
        assert cuerpo["grados_detectados"] == ["Cuarto", "Quinto"]
        assert base64.b64encode(marcador).decode() not in respuesta.text
        assert "marcador-secreto" not in respuesta.text
        assert catalogo.llamadas == []

    async def test_una_percepcion_rechazada_no_toca_el_catalogo(self, cliente, catalogo, lecturas):
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(b""))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "archivo_vacio"
        assert lecturas == []
        assert catalogo.llamadas == []


class TestOnboardingConElCatalogoCaido:

    async def test_es_503_y_dice_que_no_se_guardo(self, cliente, catalogo, monkeypatch):
        async def _caido(**_kw):
            raise RemotoCaido(
                "catalogo", "/v1/admin/listas/importar no respondio (All connection attempts failed)"
            )

        monkeypatch.setattr(catalogo, "importar_lista", _caido)
        marcador = b"%PDF-marcador-secreto-del-cliente"
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(marcador))

        assert respuesta.status_code == 503
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "servicio_no_disponible"
        assert "no se guardo" in cuerpo["mensaje"]
        assert "marcador-secreto" not in respuesta.text

    async def test_un_rechazo_del_catalogo_no_se_disfraza_de_caida(self, cliente, catalogo, monkeypatch):
        async def _rechazo(**_kw):
            raise RemotoCaido("catalogo", "/v1/admin/listas/importar respondio 422", estado=422)

        monkeypatch.setattr(catalogo, "importar_lista", _rechazo)
        with pytest.raises(RemotoCaido):
            await cliente.post("/v1/admin/onboarding", **_multipart())


DANE_SALITRE = "311001093652"


class TestOnboardingDeUnColegioQueTukitNoTiene:

    async def test_del_directorio_deriva_el_id_del_dane_y_manda_sus_datos(self, cliente, catalogo, identidad):
        identidad.directorio[DANE_SALITRE] = {
            "dane": DANE_SALITRE,
            "nombre": "COLEGIO AGUSTINIANO CIUDAD SALITRE",
            "direccion": "CL 23 C # 69 B - 01",
            "sitio_web": "www.agustinianosalitre.edu.co",
        }
        respuesta = await cliente.post(
            "/v1/admin/onboarding",
            **_multipart(colegio_id=None, colegio_dane=DANE_SALITRE, colegio_nombre="Agustiniano Salitre"),
        )

        assert respuesta.status_code == 200
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == str(derivar("colegio", DANE_SALITRE))
        assert llamada["colegio_datos"] == {
            "dane": DANE_SALITRE,
            "nombre": "Agustiniano Salitre",
            "direccion": "CL 23 C # 69 B - 01",
            "sitio_web": "www.agustinianosalitre.edu.co",
        }
        assert identidad.consultas == [DANE_SALITRE]
        assert llamada["origen"] == "onboarding"
        assert llamada["contacto_referencia"] is None

    async def test_escrito_a_mano_deriva_el_id_del_nombre_normalizado(self, cliente, catalogo, identidad):
        respuesta = await cliente.post(
            "/v1/admin/onboarding", **_multipart(colegio_id=None, colegio_nombre="  Gimnasio   del Bosque ")
        )

        assert respuesta.status_code == 200
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == str(derivar("colegio", "libre", "gimnasio del bosque"))
        assert llamada["colegio_datos"] == {"dane": None, "nombre": "Gimnasio del Bosque"}
        assert identidad.consultas == []

    async def test_escrito_a_mano_reusa_el_colegio_que_identidad_ya_tiene(self, cliente, catalogo, identidad):
        identidad.conocidos = [{"colegio_id": "c-bosque", "nombre": "Gimnasio del Bosque", "dane": None}]
        respuesta = await cliente.post(
            "/v1/admin/onboarding", **_multipart(colegio_id=None, colegio_nombre="gimnasio DEL bosque")
        )

        assert respuesta.status_code == 200
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == "c-bosque"
        assert llamada["colegio_datos"] is None

    async def test_con_colegio_id_no_viajan_datos_de_colegio(self, cliente, catalogo, identidad):
        await cliente.post("/v1/admin/onboarding", **_multipart(colegio_dane=DANE_SALITRE))

        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["colegio_datos"] is None
        assert identidad.consultas == []

    async def test_sin_colegio_es_422_y_no_toca_el_catalogo(self, cliente, catalogo):
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart(colegio_id=None))

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "colegio_requerido"
        assert catalogo.llamadas == []

    async def test_un_nombre_demasiado_largo_es_422(self, cliente, catalogo):
        respuesta = await cliente.post(
            "/v1/admin/onboarding", **_multipart(colegio_id=None, colegio_nombre="x" * 300)
        )

        assert respuesta.status_code == 422
        assert catalogo.llamadas == []


class TestOnboardingExigeStaff:

    @pytest.mark.parametrize(
        ("cabeceras", "estado", "error"),
        [
            ({"Authorization": ""}, 401, "sesion_invalida"),
            ({"Authorization": "Bearer tok-vencido"}, 401, "sesion_invalida"),
            ({"Authorization": "Bearer tok-acudiente"}, 403, "acceso_denegado"),
        ],
    )
    async def test_sin_staff_no_percibe_ni_importa(
        self, cliente, catalogo, lecturas, cabeceras, estado, error
    ):
        respuesta = await cliente.post("/v1/admin/onboarding", headers=cabeceras, **_multipart())

        assert respuesta.status_code == estado
        assert respuesta.json()["error"] == error
        assert lecturas == []
        assert catalogo.llamadas == []

    async def test_identidad_caida_falla_cerrada(self, cliente, catalogo, identidad, lecturas):
        identidad.caida = True
        respuesta = await cliente.post("/v1/admin/onboarding", **_multipart())

        assert respuesta.status_code == 503
        assert lecturas == []
        assert catalogo.llamadas == []

    async def test_un_admin_tambien_sube(self, cliente, catalogo):
        respuesta = await cliente.post(
            "/v1/admin/onboarding", headers={"Authorization": "Bearer tok-admin"}, **_multipart()
        )

        assert respuesta.status_code == 200
        assert len(catalogo.llamadas) == 1


class TestColegioElegido:

    def test_el_colegio_id_gana(self):
        elegido = ColegioElegido(colegio_id=COLEGIO, colegio_dane=DANE_SALITRE, colegio_nombre="X")
        assert elegido.resolver_colegio() == (COLEGIO, None)

    def test_el_dane_deriva_el_id_y_lleva_el_nombre(self):
        elegido = ColegioElegido(colegio_dane=DANE_SALITRE, colegio_nombre=" Salitre ")
        assert elegido.resolver_colegio() == (
            str(derivar("colegio", DANE_SALITRE)),
            {"dane": DANE_SALITRE, "nombre": "Salitre"},
        )

    def test_el_dane_sin_nombre_deja_el_nombre_vacio(self):
        assert ColegioElegido(colegio_dane=DANE_SALITRE).resolver_colegio()[1] == {
            "dane": DANE_SALITRE,
            "nombre": None,
        }

    def test_sin_nada_es_colegio_requerido(self):
        with pytest.raises(ErrorDominio) as error:
            ColegioElegido(colegio_nombre="   ").resolver_colegio()
        assert error.value.error == "colegio_requerido"
