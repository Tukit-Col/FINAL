from __future__ import annotations

import uuid

import pytest


class TestElContactoSeVuelveUnIdentificador:
    async def test_devuelve_un_id_y_no_repite_el_correo(self, cliente):
        respuesta = await cliente.post("/v1/contactos", json={"correo": "papa@ejemplo.com"})

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["creado"] is True
        assert uuid.UUID(cuerpo["usuario_id"])
        assert "papa@ejemplo.com" not in respuesta.text

    async def test_resolver_un_id_devuelve_su_contacto_para_enviar(self, cliente):
        creado = (await cliente.post("/v1/contactos", json={"correo": "mama@ejemplo.com"})).json()

        respuesta = await cliente.get(f"/v1/contactos/{creado['usuario_id']}")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["usuario_id"] == creado["usuario_id"]
        assert cuerpo["correo"] == "mama@ejemplo.com"
        assert cuerpo["celular"] is None

    async def test_resolver_un_id_que_no_existe_da_404(self, cliente):
        respuesta = await cliente.get(f"/v1/contactos/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "usuario_no_existe"

    async def test_el_mismo_correo_no_crea_dos_cuentas(self, cliente):
        primero = (await cliente.post("/v1/contactos", json={"correo": "papa@ejemplo.com"})).json()
        segundo = (await cliente.post("/v1/contactos", json={"correo": "PAPA@Ejemplo.com "})).json()

        assert segundo["usuario_id"] == primero["usuario_id"]
        assert segundo["creado"] is False

    @pytest.mark.parametrize("correo", ["papa@ejemplo", "papa ejemplo.com", "@ejemplo.com"])
    async def test_lo_que_no_es_un_correo_no_crea_cuenta(self, cliente, correo):
        respuesta = await cliente.post("/v1/contactos", json={"correo": correo})
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "correo"

    async def test_una_cadena_demasiado_corta_la_para_la_validacion_de_forma(self, cliente):
        respuesta = await cliente.post("/v1/contactos", json={"correo": "a@b"})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "entrada_invalida"
