"""La sesion: correo+clave -> token con roles, y la revocacion por version.

Fija tres cosas que el diseño promete y que son faciles de romper sin notar:

- El token lleva `version_permisos` y `GET /v1/sesiones/actual` la compara: si
  la cuenta subio de version, el token viejo deja de valer aunque no haya
  expirado (ADR 0016). Es la revocacion, y sin prueba se degrada a nada.
- El mensaje de credenciales invalidas NO distingue "correo no existe" de
  "clave mala": distinguirlos deja enumerar cuentas.
- La respuesta trae los ROLES resueltos desde `asignacion_rol`, que es lo que
  el frontend usa para enrutar por app (ADR 0008), y nunca datos de menores.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_identidad.api import app
from tukit_identidad.dominio.sesiones import (
    emitir_token,
    hashear_clave,
    leer_token,
    verificar_clave,
)
from tukit_identidad.modelos import AsignacionRol, Base, Usuario


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        # Un acudiente con clave y un rol de ambito global, para no depender de
        # que exista un colegio en esta base.
        u = Usuario(correo="mama@ejemplo.com", clave_hash=hashear_clave("demo1234"))
        sesion.add(u)
        await sesion.flush()
        sesion.add(
            AsignacionRol(usuario_id=u.id, rol_codigo="acudiente", ambito_tipo="global", ambito_id=None)
        )
        # Un contacto sin credencial, como el que crea `registrar_contacto`.
        sesion.add(Usuario(correo="invitado@ejemplo.com", clave_hash="sin-credencial"))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


class TestHashDeClave:
    def test_verifica_la_correcta_y_rechaza_la_mala(self):
        h = hashear_clave("secreta")
        assert verificar_clave("secreta", h)
        assert not verificar_clave("otra", h)

    def test_el_centinela_sin_credencial_no_valida_contra_nada(self):
        """`clave_hash="sin-credencial"` es un contacto invitado: no puede
        entrar, aunque alguien mande esa cadena como clave."""
        assert not verificar_clave("sin-credencial", "sin-credencial")

    def test_dos_hashes_de_la_misma_clave_difieren_por_la_sal(self):
        assert hashear_clave("igual") != hashear_clave("igual")


class TestTokenFirmado:
    def test_ida_y_vuelta(self):
        import uuid

        uid = uuid.uuid4()
        token = emitir_token(uid, version_permisos=1, ahora=1000.0)
        payload = leer_token(token, ahora=1000.0)
        assert payload is not None
        assert payload["sub"] == str(uid)
        assert payload["vp"] == 1

    def test_un_token_vencido_no_vale(self):
        import uuid

        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=1000.0)
        assert leer_token(token, ahora=1000.0 + 10**9) is None

    def test_una_firma_alterada_no_vale(self):
        import uuid

        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=1000.0)
        cuerpo, _firma = token.split(".")
        assert leer_token(f"{cuerpo}.firmafalsa", ahora=1000.0) is None


class TestIniciarSesion:
    async def test_entra_y_devuelve_roles_y_token(self, cliente):
        respuesta = await cliente.post(
            "/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "demo1234"}
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["sesion"]["roles"][0]["rol"] == "acudiente"
        assert cuerpo["token"]
        # La respuesta trae el correo propio (para saludar) pero jamas un
        # estudiante, matricula ni nombre de menor.
        assert "estudiante" not in respuesta.text
        assert "matricula" not in respuesta.text

    async def test_clave_mala_y_correo_inexistente_dan_el_mismo_error(self, cliente):
        mala = await cliente.post("/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "nop"})
        inexistente = await cliente.post("/v1/sesiones", json={"correo": "nadie@ejemplo.com", "clave": "x"})
        assert mala.status_code == inexistente.status_code == 401
        assert mala.json()["error"] == inexistente.json()["error"] == "credenciales_invalidas"

    async def test_un_contacto_sin_credencial_no_puede_entrar(self, cliente):
        respuesta = await cliente.post(
            "/v1/sesiones", json={"correo": "invitado@ejemplo.com", "clave": "loquesea"}
        )
        assert respuesta.status_code == 401


class TestSesionActualYRevocacion:
    async def test_el_token_reciente_resuelve_la_sesion(self, cliente):
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "demo1234"})
        ).json()["token"]
        respuesta = await cliente.get("/v1/sesiones/actual", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 200
        assert respuesta.json()["correo"] == "mama@ejemplo.com"

    async def test_sin_token_es_401(self, cliente):
        assert (await cliente.get("/v1/sesiones/actual")).status_code == 401

    async def test_subir_la_version_de_permisos_revoca_el_token_viejo(self, cliente):
        """La palanca de revocacion del ADR 0016: el token viejo lleva vp=1;
        si la cuenta pasa a vp=2, el token deja de valer sin haber expirado."""
        from sqlalchemy import update

        token = (
            await cliente.post("/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "demo1234"})
        ).json()["token"]

        async with app.state.motor.engine.begin() as conexion:
            await conexion.execute(update(Usuario).values(version_permisos=2))

        respuesta = await cliente.get("/v1/sesiones/actual", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_revocada"

    async def test_cerrar_sesion_responde_204(self, cliente):
        assert (await cliente.post("/v1/sesiones/cierre")).status_code == 204

    async def test_cerrar_sesion_revoca_el_token(self, cliente):
        """Antes cerrar sesion solo borraba la cookie: el token seguia valiendo
        hasta expirar, y quien lo hubiera copiado seguia entrando."""
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "demo1234"})
        ).json()["token"]
        cabeceras = {"Authorization": f"Bearer {token}"}

        assert (await cliente.post("/v1/sesiones/cierre", headers=cabeceras)).status_code == 204

        respuesta = await cliente.get("/v1/sesiones/actual", headers=cabeceras)
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_revocada"
        # Volver a entrar da un token nuevo que si vale.
        nuevo = (
            await cliente.post("/v1/sesiones", json={"correo": "mama@ejemplo.com", "clave": "demo1234"})
        ).json()["token"]
        assert (
            await cliente.get("/v1/sesiones/actual", headers={"Authorization": f"Bearer {nuevo}"})
        ).status_code == 200

    async def test_cerrar_con_un_token_invalido_no_falla(self, cliente):
        """Cerrar es idempotente: un token vencido o inventado no es un error."""
        respuesta = await cliente.post("/v1/sesiones/cierre", headers={"Authorization": "Bearer inventado"})
        assert respuesta.status_code == 204
