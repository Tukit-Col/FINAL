from __future__ import annotations

import uuid

import httpx
import pytest
from conftest import CatalogoFalso, opcion, reconocido, renglon
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.remoto import RemotoCaido

COLEGIO = "11111111-1111-5111-8111-111111111111"
CONTACTO_ID = "44444444-4444-5444-8444-444444444444"
PADRE_ID = "22222222-2222-5222-8222-222222222222"


@pytest.fixture()
async def cliente(motor, monkeypatch):
    app.state.motor = motor
    lanzados: list[uuid.UUID] = []

    async def _lanzar_falso(_motor, trabajo_id):
        lanzados.append(trabajo_id)

    monkeypatch.setattr(trabajos, "lanzar", _lanzar_falso)
    app.state.catalogo = _catalogo()
    app.state.identidad = IdentidadDoble()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.lanzados = lanzados
        yield http
    del app.state.catalogo
    del app.state.identidad


class IdentidadDoble:
    def __init__(self) -> None:
        self.usuario_por_token: dict[str, str] = {}
        self.contactos: list[str] = []
        self.con_clave: set[str] = set()

    async def usuario_del_token(self, token: str) -> str | None:
        return self.usuario_por_token.get(token)

    async def sesion(self, token: str) -> dict | None:
        usuario = self.usuario_por_token.get(token)
        return None if usuario is None else {"usuario_id": usuario, "roles": []}

    async def tiene_credencial(self, usuario_id: str) -> bool:
        return usuario_id in self.con_clave

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.contactos.append(correo)
        return CONTACTO_ID


def _peticion(**kw):
    cuerpo = {
        "contacto": {"correo": "papa@ejemplo.com"},
        "hijos": [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
    }
    cuerpo.update(kw)
    return cuerpo


async def _crear_del_acudiente(cliente, motor, token: str = "tok-acud") -> uuid.UUID:
    identidad = app.state.identidad
    identidad.usuario_por_token[token] = PADRE_ID
    identidad.con_clave.add(PADRE_ID)
    creado = (
        await cliente.post(
            "/v1/trabajos", json=_peticion(contacto=None), headers={"Authorization": f"Bearer {token}"}
        )
    ).json()
    trabajo_id = uuid.UUID(creado["trabajo_id"])
    await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
    return trabajo_id


class TestCrearDevuelve202:
    async def test_el_cuerpo_trae_donde_consultar(self, cliente):
        respuesta = await cliente.post("/v1/trabajos", json=_peticion())

        assert respuesta.status_code == 202
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == "encolado"
        assert cuerpo["consultar_en"] == f"/v1/trabajos/{cuerpo['trabajo_id']}"
        assert cliente.lanzados == [uuid.UUID(cuerpo["trabajo_id"])]

    async def test_el_apodo_de_cada_hijo_se_guarda_y_el_get_lo_devuelve(self, cliente):
        creado = await cliente.post(
            "/v1/trabajos",
            json=_peticion(
                hijos=[
                    {"referencia": "hijo-0", "colegio_id": COLEGIO, "grado": "Cuarto", "apodo": "  Sofía "},
                    {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto", "apodo": "Lucía"},
                ]
            ),
        )
        assert creado.status_code == 202
        vista = (await cliente.get(creado.json()["consultar_en"])).json()
        assert [h.get("apodo") for h in vista["hijos"]] == ["Sofía", "Lucía"]

    async def test_la_vista_admin_no_trae_el_apodo_y_la_del_dueno_si(self, cliente):
        creado = await cliente.post(
            "/v1/trabajos",
            json=_peticion(
                hijos=[{"referencia": "hijo-0", "colegio_id": COLEGIO, "grado": "Cuarto", "apodo": "Sofía"}]
            ),
        )
        trabajo_id = creado.json()["trabajo_id"]
        dueno = (await cliente.get(creado.json()["consultar_en"])).json()
        admin = (await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")).json()
        assert dueno["hijos"][0]["apodo"] == "Sofía"
        assert all("apodo" not in h for h in admin["hijos"])
        assert admin["hijos"][0]["referencia"] == "hijo-0"
        assert "Sofía" not in str(admin)

    @pytest.mark.parametrize(
        "personaje_por_hijo",
        [
            {"hijo-1": ["x" * 61]},
            {"hijo-1": ["a", "b", "c", "d", "e", "f"]},
            {f"hijo-{i}": ["spiderman"] for i in range(11)},
        ],
    )
    async def test_personaje_por_hijo_tiene_tope(self, cliente, personaje_por_hijo):
        respuesta = await cliente.post(
            "/v1/trabajos", json=_peticion(preferencias={"personaje_por_hijo": personaje_por_hijo})
        )
        assert respuesta.status_code in (400, 422)

    async def test_un_apodo_de_mas_de_40_caracteres_se_rechaza(self, cliente):
        respuesta = await cliente.post(
            "/v1/trabajos",
            json=_peticion(
                hijos=[{"referencia": "hijo-0", "colegio_id": COLEGIO, "grado": "Cuarto", "apodo": "x" * 41}]
            ),
        )
        assert respuesta.status_code in (400, 422)

    async def test_dos_hijos_con_la_misma_referencia_se_rechazan(self, cliente):
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
        respuesta = await cliente.post("/v1/trabajos", json={"hijos": []})

        assert respuesta.status_code == 400
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "entrada_invalida"
        assert "input" not in respuesta.text
        assert set(cuerpo) <= {"error", "mensaje", "campo"}


class TestSinListaSeRechazaAlCrear:
    async def test_ningun_hijo_con_lista_es_422_y_no_encola(self, cliente):
        respuesta = await cliente.post(
            "/v1/trabajos",
            json=_peticion(hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Primero"}]),
        )

        assert respuesta.status_code == 422
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "sin_lista_oficial"
        assert "Sube el archivo de la lista" in cuerpo["mensaje"]
        assert cliente.lanzados == []

    async def test_basta_con_que_un_hijo_tenga_lista(self, cliente):
        respuesta = await cliente.post(
            "/v1/trabajos",
            json=_peticion(
                hijos=[
                    {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                    {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Primero"},
                ]
            ),
        )
        assert respuesta.status_code == 202
        assert respuesta.json()["estado"] == "encolado"
        assert cliente.lanzados == [uuid.UUID(respuesta.json()["trabajo_id"])]

    async def test_con_el_catalogo_caido_se_encola_sin_verificar_la_lista(self, cliente):
        class CatalogoCaido:
            async def listas(self, **_kw):
                raise RemotoCaido("catalogo", "simulado")

        app.state.catalogo = CatalogoCaido()
        respuesta = await cliente.post(
            "/v1/trabajos",
            json=_peticion(hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Primero"}]),
        )
        assert respuesta.status_code == 202
        assert len(cliente.lanzados) == 1


class TestLaSesionEsLaProdiedad:
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
        assert identidad.contactos == []

    async def test_aplicar_canonico_con_bearer_usa_el_usuario_de_sesion(self, cliente):
        identidad = IdentidadDoble()
        identidad.usuario_por_token["tok-acud"] = "33333333-3333-5333-8333-333333333333"
        app.state.identidad = identidad
        respuesta = await cliente.post(
            "/v1/trabajos/aplicar-canonico",
            json={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026, "perfil": "Ahorrador"},
            headers={"Authorization": "Bearer tok-acud"},
        )
        assert respuesta.status_code == 404

    async def test_aplicar_canonico_rechaza_un_apodo_de_mas_de_40(self, cliente):
        respuesta = await cliente.post(
            "/v1/trabajos/aplicar-canonico",
            json={
                "colegio_id": COLEGIO,
                "grado": "Cuarto",
                "anio_lectivo": 2026,
                "perfil": "Ahorrador",
                "apodo": "x" * 41,
            },
        )
        assert respuesta.status_code in (400, 422)


class TestMisTrabajos:
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

    async def test_listar_trabajos_sin_sesion_responde_401_sesion_requerida(self, cliente):
        app.state.identidad = IdentidadDoble()
        respuesta = await cliente.get("/v1/trabajos")
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_requerida"


class TestConsultar:
    async def test_un_trabajo_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get(f"/v1/trabajos/{uuid.uuid4()}")

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"

    async def test_abrir_borrador_de_un_trabajo_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.post(f"/v1/admin/trabajos/{uuid.uuid4()}/borrador")

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"

    async def test_mientras_no_este_publicado_kits_va_vacio(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)

        vista = (
            await cliente.get(f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-acud"})
        ).json()
        assert vista["estado"] == "espera_revision"
        assert vista["kits"] == []

        admin = (await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")).json()
        assert len(admin["kits"]) == 2

    async def test_el_admin_ve_los_campos_de_consola_y_el_acudiente_no(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)

        admin = (await cliente.get(f"/v1/admin/trabajos/{trabajo_id}")).json()
        assert isinstance(admin["lineas_pendientes"], list)
        assert admin["recibido_en"]
        assert "contacto_id" in admin

        acudiente = (
            await cliente.get(f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-acud"})
        ).json()
        assert "contacto_id" not in acudiente
        assert "lineas_pendientes" not in acudiente


class TestQuienLeeUnTrabajo:
    OTRO_ID = "33333333-3333-5333-8333-333333333333"
    STAFF_ID = "55555555-5555-5555-8555-555555555555"

    async def _publicar(self, cliente, trabajo_id):
        await cliente.post(f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"})

    async def _primer_renglon(self, cliente, trabajo_id, token="tok-acud"):
        vista = (
            await cliente.get(f"/v1/trabajos/{trabajo_id}", headers={"Authorization": f"Bearer {token}"})
        ).json()
        kit = vista["kits"][0]
        return kit["perfil"], kit["lineas"][0]["item_id"]

    async def test_el_dueno_con_clave_lee_su_kit(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)
        respuesta = await cliente.get(
            f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-acud"}
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["trabajo_id"] == str(trabajo_id)

    async def test_otra_cuenta_recibe_404_y_no_403(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)
        app.state.identidad.usuario_por_token["tok-ajeno"] = self.OTRO_ID

        respuesta = await cliente.get(
            f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-ajeno"}
        )
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "trabajo_no_existe"
        assert "kits" not in respuesta.json()

    async def test_ver_un_trabajo_sin_sesion_responde_401_sesion_requerida(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)
        respuesta = await cliente.get(f"/v1/trabajos/{trabajo_id}")
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_requerida"

    async def test_token_invalido_de_un_dueno_con_clave_es_401(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)
        respuesta = await cliente.get(
            f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer revocado"}
        )
        assert respuesta.status_code == 401

    async def test_dueno_contacto_sin_clave_lee_por_id(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        assert app.state.identidad.contactos == ["papa@ejemplo.com"]
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        assert (await cliente.get(f"/v1/trabajos/{trabajo_id}")).status_code == 200

    async def test_anonimo_sin_dueno_lee_por_id(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion(contacto=None))).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())

        assert (await cliente.get(f"/v1/trabajos/{trabajo_id}")).status_code == 200

    async def test_el_staff_lee_el_kit_de_cualquiera(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)

        async def sesion_staff(token):
            if token == "tok-staff":
                return {"usuario_id": self.STAFF_ID, "roles": [{"rol": "operador"}]}
            return await IdentidadDoble.sesion(app.state.identidad, token)

        app.state.identidad.sesion = sesion_staff
        respuesta = await cliente.get(
            f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-staff"}
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["trabajo_id"] == str(trabajo_id)

    async def test_identidad_caida_con_dueno_con_clave_falla_cerrada(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)

        async def caida(*_a, **_k):
            raise RemotoCaido("identidad", "simulado")

        app.state.identidad.sesion = caida
        app.state.identidad.tiene_credencial = caida
        respuesta = await cliente.get(
            f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-acud"}
        )
        assert respuesta.status_code == 503

    async def test_identidad_caida_no_afecta_al_trabajo_sin_dueno(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion(contacto=None))).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])

        async def caida(*_a, **_k):
            raise RemotoCaido("identidad", "simulado")

        app.state.identidad.sesion = caida
        app.state.identidad.tiene_credencial = caida
        assert (await cliente.get(f"/v1/trabajos/{trabajo_id}")).status_code == 200

    async def test_opciones_dueno_200_ajeno_404_sin_sesion_401(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)
        await self._publicar(cliente, trabajo_id)
        perfil, item = await self._primer_renglon(cliente, trabajo_id)
        ruta = f"/v1/trabajos/{trabajo_id}/kits/{perfil}/lineas/{item}/opciones"
        app.state.identidad.usuario_por_token["tok-ajeno"] = self.OTRO_ID

        assert (await cliente.get(ruta, headers={"Authorization": "Bearer tok-acud"})).status_code == 200
        assert (await cliente.get(ruta, headers={"Authorization": "Bearer tok-ajeno"})).status_code == 404
        assert (await cliente.get(ruta)).status_code == 401

    async def test_opciones_de_un_contacto_se_leen_por_id(self, cliente, motor):
        creado = (await cliente.post("/v1/trabajos", json=_peticion())).json()
        trabajo_id = uuid.UUID(creado["trabajo_id"])
        await trabajos.procesar(motor, trabajo_id, catalogo=_catalogo())
        await self._publicar(cliente, trabajo_id)
        vista = (await cliente.get(f"/v1/trabajos/{trabajo_id}")).json()
        kit = vista["kits"][0]

        respuesta = await cliente.get(
            f"/v1/trabajos/{trabajo_id}/kits/{kit['perfil']}/lineas/{kit['lineas'][0]['item_id']}/opciones"
        )
        assert respuesta.status_code == 200
        elegido = kit["lineas"][0]["producto_elegido"]["sku"]
        assert elegido in {o["sku"] for o in respuesta.json()["opciones"]}


class TestLaColaYLaPublicacion:
    async def test_aprobar_publica_y_los_kits_aparecen(self, cliente, motor):
        trabajo_id = await _crear_del_acudiente(cliente, motor)

        assert (await cliente.get("/v1/admin/cola")).json()["total"] == 1

        aprobado = await cliente.post(
            f"/v1/admin/trabajos/{trabajo_id}/revision", json={"decision": "aprobar"}
        )
        assert aprobado.status_code == 200

        vista = (
            await cliente.get(f"/v1/trabajos/{trabajo_id}", headers={"Authorization": "Bearer tok-acud"})
        ).json()
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
