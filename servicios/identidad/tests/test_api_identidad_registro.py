"""`POST /v1/registro`: el alta del acudiente con credencial, consentimiento e hijos."""

from __future__ import annotations

import uuid

from tukit_comun.identificadores import derivar
from tukit_identidad.api import app


class TestElRegistroDelAcudiente:
    """El alta con credencial y los hijos del acudiente nuevo (camino B)."""

    async def test_crea_una_cuenta_con_credencial_usable(self, cliente):
        respuesta = await cliente.post(
            "/v1/registro",
            json={
                "correo": "nueva@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "celular": "3001112233",
                "hijos": [],
            },
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["creado"] is True

        # Y la credencial sirve: la cuenta puede iniciar sesion.
        sesion = await cliente.post(
            "/v1/sesiones", json={"correo": "nueva@ejemplo.com", "clave": "clave1234"}
        )
        assert sesion.status_code == 200
        assert sesion.json()["sesion"]["correo"] == "nueva@ejemplo.com"

    async def test_asciende_un_contacto_sin_credencial_sin_perder_su_id(self, cliente):
        """Orden-independiente con /v1/contactos: quien primero pidio un kit
        (creando el contacto) y luego se registra conserva el MISMO id, para
        que el trabajo del pipeline que ya lo referencia siga apuntando bien."""
        contacto = (await cliente.post("/v1/contactos", json={"correo": "mixta@ejemplo.com"})).json()
        assert contacto["creado"] is True

        registro = (
            await cliente.post(
                "/v1/registro",
                json={
                    "correo": "mixta@ejemplo.com",
                    "acepta_terminos": True,
                    "clave": "clave1234",
                    "hijos": [],
                },
            )
        ).json()
        assert registro["creado"] is True
        assert registro["usuario_id"] == contacto["usuario_id"]

        # Como contacto no podia entrar (centinela); registrado, entra con su id.
        sesion = await cliente.post(
            "/v1/sesiones", json={"correo": "mixta@ejemplo.com", "clave": "clave1234"}
        )
        assert sesion.status_code == 200
        assert sesion.json()["sesion"]["usuario_id"] == contacto["usuario_id"]

    async def test_no_pisa_una_cuenta_ya_registrada(self, cliente):
        """La ruta es publica: no debe dejar que un tercero cambie la clave de
        una cuenta que ya tiene credencial."""
        await cliente.post(
            "/v1/registro",
            json={"correo": "duena@ejemplo.com", "acepta_terminos": True, "clave": "originaal", "hijos": []},
        )
        repetido = await cliente.post(
            "/v1/registro",
            json={"correo": "duena@ejemplo.com", "acepta_terminos": True, "clave": "otraaaaa", "hijos": []},
        )
        assert repetido.status_code == 201
        assert repetido.json()["creado"] is False

        # La clave es la original, no la del segundo intento.
        original = await cliente.post(
            "/v1/sesiones", json={"correo": "duena@ejemplo.com", "clave": "originaal"}
        )
        assert original.status_code == 200
        assert original.json()["sesion"]["usuario_id"] == repetido.json()["usuario_id"]
        assert (
            await cliente.post("/v1/sesiones", json={"correo": "duena@ejemplo.com", "clave": "otraaaaa"})
        ).status_code == 401

    async def test_persiste_los_hijos_y_los_expone_por_cuenta_matriculas(self, cliente):
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "conhijos@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Pipe"}],
            },
        )
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "conhijos@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]

        respuesta = await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["total"] == 1
        assert cuerpo["matriculas"][0]["colegio_id"] == colegio_id
        assert cuerpo["matriculas"][0]["grado"] == "Quinto"
        # El PADRE SI ve el apodo de SUS hijos: es el portador del token y el mismo
        # lo escribio, y lo necesita para precargar `/empezar`. Baja descifrado en
        # servidor; sigue sin salir nombre legal, documento ni estudiante_id.
        assert cuerpo["matriculas"][0]["apodo"] == "Pipe"

    async def test_aceptar_los_terminos_deja_el_consentimiento_del_titular(self, cliente):
        from sqlalchemy import select
        from tukit_identidad.modelos import Consentimiento

        cuerpo = {"correo": "acepta@ejemplo.com", "clave": "clave1234", "acepta_terminos": True}
        alta = await cliente.post("/v1/registro", json=cuerpo)
        assert alta.status_code == 201
        # Sin la casilla el alta se rechaza y no deja ni la cuenta ni el consentimiento.
        sin = {"correo": "sinmarca@ejemplo.com", "clave": "clave1234"}
        assert (await cliente.post("/v1/registro", json=sin)).status_code == 422

        async with app.state.motor.sesion() as db:
            filas = (await db.execute(select(Consentimiento))).scalars().all()
        titulares = [f for f in filas if f.regimen == "registro_titular"]
        assert len(titulares) == 1
        assert str(titulares[0].usuario_id) == alta.json()["usuario_id"]
        assert titulares[0].matricula_id is None
        assert titulares[0].version

    async def test_sin_aceptar_los_terminos_es_422_y_no_crea_la_cuenta(self, cliente):
        from sqlalchemy import select
        from tukit_identidad.modelos import Usuario

        for cuerpo in (
            {"correo": "sinmarca@ejemplo.com", "clave": "clave1234"},
            {"correo": "sinmarca@ejemplo.com", "clave": "clave1234", "acepta_terminos": False},
        ):
            r = await cliente.post("/v1/registro", json=cuerpo)
            assert r.status_code == 422
            assert r.json()["error"] == "consentimiento_requerido"
            assert r.json()["campo"] == "acepta_terminos"

        async with app.state.motor.sesion() as db:
            correos = (await db.execute(select(Usuario.correo))).scalars().all()
        assert "sinmarca@ejemplo.com" not in correos

    async def test_el_contacto_del_pago_no_pide_consentimiento(self, cliente):
        """`POST /v1/contactos` es el alta interna del pipeline: no tiene casilla,
        crea la cuenta sin ella y no deja consentimiento del titular."""
        from sqlalchemy import select
        from tukit_identidad.modelos import Consentimiento

        r = await cliente.post("/v1/contactos", json={"correo": "contacto@ejemplo.com"})
        assert r.status_code == 201
        assert r.json()["creado"] is True
        async with app.state.motor.sesion() as db:
            assert (await db.execute(select(Consentimiento))).scalars().all() == []

    async def test_credencial_distingue_contacto_de_cuenta_con_clave(self, cliente):
        contacto = (await cliente.post("/v1/contactos", json={"correo": "solo@ejemplo.com"})).json()
        cuenta = (
            await cliente.post(
                "/v1/registro",
                json={"correo": "conclave@ejemplo.com", "clave": "clave1234", "acepta_terminos": True},
            )
        ).json()

        sin = await cliente.get(f"/v1/contactos/{contacto['usuario_id']}/credencial")
        con = await cliente.get(f"/v1/contactos/{cuenta['usuario_id']}/credencial")
        desconocido = await cliente.get(f"/v1/contactos/{uuid.uuid4()}/credencial")
        assert sin.json() == {"tiene_credencial": False}
        assert con.json() == {"tiene_credencial": True}
        assert desconocido.json() == {"tiene_credencial": False}

    async def test_reenviar_el_mismo_formulario_no_duplica_matriculas(self, cliente):
        colegio_id = str(derivar("colegio", "2.4"))
        cuerpo = {
            "correo": "repite@ejemplo.com",
            "acepta_terminos": True,
            "clave": "clave1234",
            "hijos": [{"colegio_id": colegio_id, "grado": "Quinto"}],
        }
        # Nace como contacto y luego se registra dos veces (idempotente).
        await cliente.post("/v1/registro", json=cuerpo)
        # El segundo POST no asciende (ya tiene credencial) pero tampoco debe
        # duplicar; comprobamos por matriculas tras un solo alta valida.
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "repite@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]
        cuenta = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert cuenta["total"] == 1

    async def test_un_grado_que_no_existe_es_422(self, cliente):
        colegio_id = str(derivar("colegio", "2.4"))
        respuesta = await cliente.post(
            "/v1/registro",
            json={
                "correo": "malgrado@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "5"}],
            },
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "grado"

    async def test_gemelos_mismo_colegio_grado_generan_dos_matriculas(self, cliente):
        """Dos hijos en el mismo colegio y grado —gemelos— son DOS matriculas, no
        una: no colapsan en el mismo estudiante derivado."""
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "gemelos@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "hijos": [
                    {"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Ana"},
                    {"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Bea"},
                ],
            },
        )
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "gemelos@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]
        cuenta = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert cuenta["total"] == 2
        assert {m["apodo"] for m in cuenta["matriculas"]} == {"Ana", "Bea"}
