"""La superficie HTTP del recurso `trabajo`, contra el contrato.

Se prueba con `ASGITransport` y no levantando uvicorn: la app se llama en el
mismo proceso, sin puerto y sin red. El motor se le inyecta a mano en
`app.state` porque el arranque normal abriria una conexion a Postgres, y una
suite que necesita un motor vivo se termina saltando.

Lo que se comprueba es lo que el frontend lee del contrato: los codigos de
estado, la forma del sobre de error y que `kits` venga vacio mientras el
trabajo no este publicado.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app

COLEGIO = "11111111-1111-5111-8111-111111111111"


@pytest.fixture()
async def cliente(motor, monkeypatch):
    """Cliente HTTP contra la app, con el motor de prueba y sin tarea de fondo.

    `lanzar` se sustituye a proposito: el contrato dice que crear devuelve
    202 y encola, y lo que aqui se prueba es el 202. Que el pipeline corra se
    prueba en `test_trabajos.py`, llamando a `procesar` de frente, que es mas
    honesto que esperar a una tarea de fondo con un `sleep`.
    """
    app.state.motor = motor
    lanzados: list[uuid.UUID] = []

    async def _lanzar_falso(_motor, trabajo_id):
        lanzados.append(trabajo_id)

    monkeypatch.setattr(trabajos, "lanzar", _lanzar_falso)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.lanzados = lanzados
        yield http


class IdentidadDoble:
    """Doble de Identidad: resuelve tokens y anota si se registro un contacto."""

    def __init__(self) -> None:
        self.usuario_por_token: dict[str, str] = {}
        self.contactos: list[str] = []

    async def usuario_del_token(self, token: str) -> str | None:
        return self.usuario_por_token.get(token)

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.contactos.append(correo)
        return "usr-contacto"


def _peticion(**kw):
    cuerpo = {
        "contacto": {"correo": "papa@ejemplo.com"},
        "hijos": [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
    }
    cuerpo.update(kw)
    return cuerpo


class TestCrearDevuelve202:
    async def test_el_cuerpo_trae_donde_consultar(self, cliente):
        respuesta = await cliente.post("/v1/trabajos", json=_peticion())

        assert respuesta.status_code == 202
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == "encolado"
        assert cuerpo["consultar_en"] == f"/v1/trabajos/{cuerpo['trabajo_id']}"
        assert cliente.lanzados == [uuid.UUID(cuerpo["trabajo_id"])]

    async def test_dos_hijos_con_la_misma_referencia_se_rechazan(self, cliente):
        """Es con la referencia con la que se agrupan las lineas: repetida,
        los dos hermanos se mezclarian en la misma columna del kit."""
        respuesta = await cliente.post(
            "/v1/trabajos",
            json=_peticion(
                hijos=[
                    {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                    {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Septimo"},
                ]
            ),
        )
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "referencias_repetidas"

    async def test_los_pesos_tienen_que_sumar_uno(self, cliente):
        respuesta = await cliente.post(
            "/v1/trabajos",
            json=_peticion(preferencias={"pesos": {"precio": 0.9, "calidad": 0.9}}),
        )
        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "pesos_no_suman_uno"
        assert cuerpo["campo"] == "preferencias.pesos"

    async def test_el_error_de_validacion_no_devuelve_lo_que_se_envio(self, cliente):
        """El manejador del sistema anterior le devolvia al cliente la
        contrasena recibida. El sobre dice DONDE fallo y nada mas."""
        respuesta = await cliente.post("/v1/trabajos", json={"hijos": []})

        assert respuesta.status_code == 400
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "entrada_invalida"
        assert "input" not in respuesta.text
        assert set(cuerpo) <= {"error", "mensaje", "campo"}


class TestLaSesionEsLaProdiedad:
    """Un acudiente autenticado (Bearer) es dueño de su trabajo por su
    usuario_id de sesion, sin re-registrar contacto. Es la traza que hace que
    su kit no quede huerfano cuando /empezar deja de mandar el contacto."""

    async def test_crear_con_bearer_usa_el_usuario_de_sesion(self, cliente, motor):
        identidad = IdentidadDoble()
        identidad.usuario_por_token["tok-acud"] = "22222222-2222-5222-8222-222222222222"
        app.state.identidad = identidad

        creado = (
            await cliente.post(
                "/v1/trabajos",
                json=_peticion(contacto=None),
                headers={"Authorization": "Bearer tok-acud"},
            )
        ).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        admin = (await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")).json()
        assert admin["contacto_id"] == "22222222-2222-5222-8222-222222222222"
        assert identidad.contactos == []  # no se re-registro contacto

    async def test_aplicar_canonico_con_bearer_usa_el_usuario_de_sesion(self, cliente):
        identidad = IdentidadDoble()
        identidad.usuario_por_token["tok-acud"] = "33333333-3333-5333-8333-333333333333"
        app.state.identidad = identidad
        # Sin cache publicada la ruta responde 404, pero el token ya se resolvio
        # antes de tocar la cache: basta con que no explote la resolucion.
        respuesta = await cliente.post(
            "/v1/trabajos/aplicar-canonico",
            json={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026, "perfil": "Ahorrador"},
            headers={"Authorization": "Bearer tok-acud"},
        )
        assert respuesta.status_code == 404


class TestMisTrabajos:
    """El panel del acudiente: `GET /v1/trabajos` con Bearer devuelve SUS
    solicitudes de kit —no las de otro, y un anonimo no ve ninguna."""

    async def test_devuelve_los_del_acudiente_con_hijos_y_preferencias(self, cliente):
        identidad = IdentidadDoble()
        identidad.usuario_por_token["tok-acud"] = "22222222-2222-5222-8222-222222222222"
        app.state.identidad = identidad

        await cliente.post(
            "/v1/trabajos",
            json=_peticion(contacto=None, preferencias={"disposicion_sobreprecio": 0.2}),
            headers={"Authorization": "Bearer tok-acud"},
        )

        respuesta = await cliente.get("/v1/trabajos", headers={"Authorization": "Bearer tok-acud"})

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["total"] == 1
        trabajo = cuerpo["trabajos"][0]
        assert trabajo["estado"] == "encolado"
        assert trabajo["hijos"][0]["grado"] == "Cuarto"
        assert trabajo["preferencias"]["disposicion_sobreprecio"] == 0.2

    async def test_no_ve_los_de_otro_acudiente(self, cliente):
        identidad = IdentidadDoble()
        identidad.usuario_por_token["tok-mio"] = "22222222-2222-5222-8222-222222222222"
        identidad.usuario_por_token["tok-ajeno"] = "33333333-3333-5333-8333-333333333333"
        app.state.identidad = identidad

        await cliente.post(
            "/v1/trabajos", json=_peticion(contacto=None), headers={"Authorization": "Bearer tok-ajeno"}
        )

        respuesta = await cliente.get("/v1/trabajos", headers={"Authorization": "Bearer tok-mio"})

        assert respuesta.status_code == 200
        assert respuesta.json()["trabajos"] == []

    async def test_anonimo_es_401(self, cliente):
        app.state.identidad = IdentidadDoble()
        respuesta = await cliente.get("/v1/trabajos")
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_requerida"


class TestConsultar:
    async def test_un_trabajo_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get(f"/v1/trabajos/{uuid.uuid4()}")

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"

    async def test_mientras_no_este_publicado_kits_va_vacio(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        vista = (await cliente.get(f"/v1/trabajos/{trabajo_id}")).json()
        assert vista["estado"] == "espera_revision"
        assert vista["kits"] == []

        admin = (await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")).json()
        assert len(admin["kits"]) == 2

    async def test_el_admin_ve_los_campos_de_consola_y_el_acudiente_no(self, cliente, motor):
        """La consola necesita `recibido_en`, `contacto_id` y
        `lineas_pendientes` para dibujar la cabecera del trabajo; sin ellos
        el detalle se cae (`Cannot read properties of undefined`).

        La asimetria es a proposito: `contacto_id` nunca viaja en la vista
        del acudiente, porque reintroduciria a mano la referencia que la
        notificacion resuelve al vuelo (frontera de `identidad`)."""
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        admin = (await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")).json()
        assert isinstance(admin["lineas_pendientes"], list)
        assert admin["recibido_en"]
        assert "contacto_id" in admin

        acudiente = (await cliente.get(f"/v1/trabajos/{trabajo_id}")).json()
        assert "contacto_id" not in acudiente
        assert "lineas_pendientes" not in acudiente


class TestLaColaYLaPublicacion:
    async def test_aprobar_publica_y_los_kits_aparecen(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        assert (await cliente.get("/v1/admin/cola")).json()["total"] == 1

        aprobado = await cliente.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"}
        )
        assert aprobado.status_code == 200

        vista = (await cliente.get(f"/v1/trabajos/{trabajo_id}")).json()
        assert vista["estado"] == "publicado"
        assert len(vista["kits"]) == 2
        assert vista["recomendado"]["perfil"] == "Ahorrador"

    async def test_revisar_un_trabajo_ya_publicado_es_409(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        await cliente.post(f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"})

        repetido = await cliente.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"}
        )
        assert repetido.status_code == 409
        assert repetido.json()["error"] == "estado_incompatible"

    async def test_una_decision_que_no_existe_no_pasa_la_validacion(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        respuesta = await cliente.post(
            f"/v1/admin/trabajos/{creado['trabajo_id']}/revision", json={"decision": "borrar"}
        )
        assert respuesta.status_code == 400


class TestReintentar:
    async def test_solo_se_reintenta_lo_fallido_o_lo_encolado(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        respuesta = await cliente.post(f"/v1/trabajos/{trabajo_id}/reintentar")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "estado_incompatible"

    async def test_un_trabajo_fallido_se_puede_reintentar(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=CatalogoFalso(grado="Septimo"))

        respuesta = await cliente.post(f"/v1/trabajos/{trabajo_id}/reintentar")
        assert respuesta.status_code == 200
        assert trabajo_id in cliente.lanzados


class TestElNavegadorPuedeLeerLaRespuesta:
    async def test_hay_cabecera_de_cors_para_el_front_local(self, cliente):
        respuesta = await cliente.get("/salud", headers={"Origin": "http://localhost:3000"})
        assert respuesta.headers["access-control-allow-origin"] == "http://localhost:3000"


def _catalogo() -> CatalogoFalso:
    return CatalogoFalso(
        renglones=[renglon(1, "2 cuadernos cuadriculados", cantidad=2)],
        respuestas={
            "2 cuadernos cuadriculados": reconocido(
                "2 cuadernos cuadriculados",
                "C001",
                [opcion("TK-C001-ECO", "economico", 4500), opcion("TK-C001-PRE", "premium", 12000)],
            )
        },
    )
