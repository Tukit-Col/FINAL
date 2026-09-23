"""La superficie minima de Identidad, y sobre todo lo que NO expone.

La prueba mas util de este archivo es la ultima: comprueba que ninguna ruta
devuelva un estudiante, un nombre de menor ni una matricula. Identidad es la
frontera de cumplimiento del sistema, asi que abrir esa superficie sin
autenticacion ni control por clasificacion de dato seria justo el defecto que
el Anexo M documenta. Que hoy no exista es una decision, y una decision hay
que poder verificarla.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.api import GRADOS, app
from tukit_identidad.modelos import Base, Colegio, Sede


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        colegio = Colegio(id=derivar("colegio", "2.4"), nombre="Colegio San Pedro")
        sesion.add(colegio)
        await sesion.flush()
        sesion.add(Sede(id=derivar("sede", "2.4", "Sede unica"), colegio_id=colegio.id, nombre="Sede unica"))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


class TestElAcudienteEscogeColegioYGrado:
    async def test_los_colegios_traen_su_numero_de_sedes(self, cliente):
        cuerpo = (await cliente.get("/v1/colegios")).json()

        assert cuerpo["total"] == 1
        assert cuerpo["colegios"][0]["nombre"] == "Colegio San Pedro"
        assert cuerpo["colegios"][0]["sedes"] == 1

    async def test_el_identificador_es_el_derivado_que_usa_catalogo(self, cliente):
        """Es lo que hace que `lista_oficial.colegio_id` resuelva de verdad:
        los dos cargadores derivan el mismo UUID del mismo codigo."""
        cuerpo = (await cliente.get("/v1/colegios")).json()
        assert cuerpo["colegios"][0]["colegio_id"] == str(derivar("colegio", "2.4"))

    async def test_un_colegio_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get(f"/v1/colegios/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "colegio_no_existe"

    async def test_los_grados_van_en_orden_escolar_y_no_alfabetico(self, cliente):
        cuerpo = (await cliente.get("/v1/grados")).json()
        assert cuerpo["grados"] == list(GRADOS)
        assert cuerpo["grados"][0] == "Parvulos"
        assert cuerpo["grados"][-1] == "Once"


class TestElContactoSeVuelveUnIdentificador:
    async def test_devuelve_un_id_y_no_repite_el_correo(self, cliente):
        """El trabajo del pipeline guarda `usuario_id` y nunca el correo: es
        lo que hace que el derecho al olvido lo alcance en un solo sitio."""
        respuesta = await cliente.post("/v1/contactos", json={"correo": "papa@ejemplo.com"})

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["creado"] is True
        assert uuid.UUID(cuerpo["usuario_id"])
        assert "papa@ejemplo.com" not in respuesta.text

    async def test_el_mismo_correo_no_crea_dos_cuentas(self, cliente):
        primero = (await cliente.post("/v1/contactos", json={"correo": "papa@ejemplo.com"})).json()
        segundo = (await cliente.post("/v1/contactos", json={"correo": "PAPA@Ejemplo.com "})).json()

        assert segundo["usuario_id"] == primero["usuario_id"]
        assert segundo["creado"] is False

    @pytest.mark.parametrize("correo", ["papa@ejemplo", "papa ejemplo.com", "@ejemplo.com"])
    async def test_lo_que_no_es_un_correo_no_crea_cuenta(self, cliente, correo):
        """422 y no 400: la entrada es valida como cadena y es el dominio
        quien la rechaza. El contrato separa los dos casos a proposito."""
        respuesta = await cliente.post("/v1/contactos", json={"correo": correo})
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "correo"

    async def test_una_cadena_demasiado_corta_la_para_la_validacion_de_forma(self, cliente):
        respuesta = await cliente.post("/v1/contactos", json={"correo": "a@b"})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"


class TestLaSuperficieDeMenoresNoEstaAbierta:
    @pytest.mark.parametrize(
        "ruta",
        ["/v1/estudiantes", "/v1/matriculas", "/v1/usuarios", "/v1/colegios/2.4/estudiantes"],
    )
    async def test_no_hay_ruta_que_devuelva_datos_de_menores(self, cliente, ruta):
        assert (await cliente.get(ruta)).status_code in {404, 422}

    def test_el_esquema_publicado_no_anuncia_ninguna(self):
        """Se mira el OpenAPI y no solo las respuestas: una ruta que existe
        y hoy nadie llama es una ruta que alguien llama manana."""
        rutas = set(app.openapi()["paths"])
        assert rutas == {
            "/salud",
            "/v1/colegios",
            "/v1/colegios/{colegio_id}",
            "/v1/grados",
            "/v1/contactos",
            # Autenticacion (seccion 12.4). Devuelven quien es el portador y sus
            # ROLES, nunca un estudiante ni un nombre de menor: la superficie
            # sensible sigue cerrada, es lo que fija la prueba de arriba.
            "/v1/sesiones",
            "/v1/sesiones/actual",
            "/v1/sesiones/cierre",
        }
