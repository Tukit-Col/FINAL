"""La lista que sugiere un padre y el backlog de sugerencias, sin PII."""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
# ruff: noqa: F811

from __future__ import annotations

import uuid

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    COLEGIO,
    PDF_FALSO,
    TAREA,
    _cuerpo_importar,
    _cuerpo_sugerencia,
    cliente,
)
from tukit_catalogo.api import app


class TestSugerenciaDeUnPadre:
    async def test_crea_una_tarea_pendiente_sugerencia_padre(self, cliente):
        cuerpo = _cuerpo_sugerencia()
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 201
        env = respuesta.json()
        assert env["estado"] == "pendiente"
        assert env["tarea_id"]

        # La tarea quedo en el backlog con origen y destino declarados.
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.origen == "sugerencia_padre"
        assert fila.estado == "pendiente"
        assert fila.colegio_id == COLEGIO
        assert fila.grado == "Septimo"
        assert fila.anio_lectivo == 2026
        assert str(fila.contacto_referencia) == cuerpo["contacto_referencia"]
        assert fila.documento == PDF_FALSO
        # No hay version: es una sugerencia por atender, no una lista escrita.
        assert fila.version_id is None

    async def test_no_guarda_pii_solo_el_contacto_por_id(self, cliente):
        # El web nunca manda correo/telefono, pero si un cliente los cuela, ni
        # se aceptan ni se echan de vuelta: la respuesta solo trae id y estado.
        referencia = str(uuid.uuid4())
        cuerpo = _cuerpo_sugerencia(
            contacto_referencia=referencia,
            correo="mama@ejemplo.com",
            telefono="+573001112233",
        )
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 201
        env = respuesta.json()
        assert "mama@ejemplo.com" not in str(env)
        assert "+573001112233" not in str(env)

        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert str(fila.contacto_referencia) == referencia
        # No hay ninguna columna donde el correo/telefono pudiera haber caido.
        assert "mama@ejemplo.com" not in str(dict(fila._mapping))

    async def test_sin_documento_ni_contacto_igual_se_encola(self, cliente):
        cuerpo = _cuerpo_sugerencia(contacto_referencia=None, evidencia={"documento_base64": None})
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 201
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(
                    TAREA.select().where(TAREA.c.id == uuid.UUID(respuesta.json()["tarea_id"]))
                )
            ).one()
        assert fila.contacto_referencia is None
        assert fila.documento is None

    async def test_base64_invalido_es_422_sin_repetir_lo_enviado(self, cliente):
        cuerpo = _cuerpo_sugerencia(evidencia={"documento_base64": "no-es-base64!!"})
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 422
        env = respuesta.json()
        assert env["error"] == "documento_invalido"
        assert env["campo"] == "documento_base64"
        assert "no-es-base64!!" not in str(env)


class TestElBacklogDeSugerencias:
    """La lista de sugerencias de padres que el administrador atiende.

    Solo las tareas con origen='sugerencia_padre' —no las de onboarding— y solo
    los campos seguros: el `contacto_referencia` es un id, nunca un correo ni un
    telefono, que son PII que vive unicamente en Identidad. No se hace ningun
    join para resolverlos.
    """

    async def test_lista_solo_las_sugerencias_con_campos_seguros(self, cliente):
        referencia = str(uuid.uuid4())
        await cliente.post("/v1/admin/sugerencias", json=_cuerpo_sugerencia(contacto_referencia=referencia))

        cuerpo = (await cliente.get("/v1/admin/sugerencias")).json()
        assert len(cuerpo["sugerencias"]) == 1
        s = cuerpo["sugerencias"][0]
        assert set(s.keys()) == {
            "tarea_id",
            "estado",
            "colegio_id",
            "grado",
            "anio_lectivo",
            "contacto_referencia",
            "tiene_documento",
        }
        assert s["estado"] == "pendiente"
        assert s["grado"] == "Septimo"
        assert s["anio_lectivo"] == 2026
        assert s["colegio_id"] == str(COLEGIO)
        assert s["contacto_referencia"] == referencia
        assert s["tiene_documento"] is True

    async def test_una_sin_documento_marca_tiene_documento_false(self, cliente):
        await cliente.post(
            "/v1/admin/sugerencias",
            json=_cuerpo_sugerencia(contacto_referencia=None, evidencia={"documento_base64": None}),
        )
        cuerpo = (await cliente.get("/v1/admin/sugerencias")).json()
        s = cuerpo["sugerencias"][0]
        assert s["tiene_documento"] is False
        assert s["contacto_referencia"] is None

    async def test_no_incluye_las_tareas_de_onboarding(self, cliente):
        # Onboarding escribe una tarea con origen='onboarding': no es sugerencia
        # de padre y no debe salir en este backlog.
        await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())
        await cliente.post("/v1/admin/sugerencias", json=_cuerpo_sugerencia())
        cuerpo = (await cliente.get("/v1/admin/sugerencias")).json()
        assert len(cuerpo["sugerencias"]) == 1

    async def test_nunca_devuelve_correo_ni_telefono(self, cliente):
        # Aunque un cliente cuele PII en el POST, ni se guarda ni puede aflorar
        # aqui: la respuesta solo trae el id de contacto.
        correo = "papa-secreto@ejemplo.com"
        telefono = "+573009998877"
        await cliente.post(
            "/v1/admin/sugerencias",
            json=_cuerpo_sugerencia(correo=correo, telefono=telefono),
        )
        texto = (await cliente.get("/v1/admin/sugerencias")).text
        assert correo not in texto
        assert telefono not in texto
