"""`/v1/cuenta/matriculas`: los hijos del portador, y solo los suyos.

Listar, agregar, quitar y cambiar de colegio. Todo exige el token y filtra
por `usuario_id`, asi que un padre solo alcanza a SUS hijos.
"""

from __future__ import annotations

import uuid

from tukit_comun.identificadores import derivar
from tukit_identidad.api import app
from tukit_identidad.modelos import Sede


class TestMisMatriculasExigenToken:
    async def test_solo_devuelve_lo_del_portador(self, cliente):
        """Otro acudiente no ve las matriculas ajenas ni con token valido."""
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "conkid@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "Quinto"}],
            },
        )
        await cliente.post(
            "/v1/registro",
            json={"correo": "sinkid@ejemplo.com", "acepta_terminos": True, "clave": "clave1234", "hijos": []},
        )
        token_ajeno = (
            await cliente.post("/v1/sesiones", json={"correo": "sinkid@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]

        cuenta = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token_ajeno}"})
        ).json()
        assert cuenta["total"] == 0


class TestGuardarMatriculasConSesion:
    """`POST /v1/cuenta/matriculas`: un acudiente autenticado agrega a sus hijos."""

    async def _token(self, cliente, correo: str) -> str:
        await cliente.post(
            "/v1/registro",
            json={"correo": correo, "acepta_terminos": True, "clave": "clave1234", "hijos": []},
        )
        return (await cliente.post("/v1/sesiones", json={"correo": correo, "clave": "clave1234"})).json()[
            "token"
        ]

    async def test_grado_invalido_es_422(self, cliente):
        token = await self._token(cliente, "malgrado-sesion@ejemplo.com")
        colegio_id = str(derivar("colegio", "2.4"))
        respuesta = await cliente.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": colegio_id, "grado": "5"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "grado"

    async def test_colegio_sin_sede_es_422(self, cliente):
        token = await self._token(cliente, "sinsede-sesion@ejemplo.com")
        # El colegio "9.9" existe pero no tiene sede activa (fixture `cliente`).
        colegio_id = str(derivar("colegio", "9.9"))
        respuesta = await cliente.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": colegio_id, "grado": "Quinto"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "colegio_id"

    async def test_solo_escribe_al_portador(self, cliente):
        """El hijo queda en la cuenta de quien porta el token, no en otra."""
        colegio_id = str(derivar("colegio", "2.4"))
        token_a = await self._token(cliente, "porta-a@ejemplo.com")
        token_b = await self._token(cliente, "porta-b@ejemplo.com")

        resultado = await cliente.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Pipe"}]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resultado.status_code == 201
        assert resultado.json()["total"] == 1

        cuenta_b = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token_b}"})
        ).json()
        assert cuenta_b["total"] == 0
        cuenta_a = (
            await cliente.get("/v1/cuenta/matriculas", headers={"Authorization": f"Bearer {token_a}"})
        ).json()
        assert cuenta_a["total"] == 1
        assert cuenta_a["matriculas"][0]["apodo"] == "Pipe"

    async def test_reenviar_agrega_otro_hijo(self, cliente):
        """El endpoint NO es idempotente por diseno: cada POST AGREGA. Reenviar el
        mismo cuerpo crea otra matricula (la proteccion de reenvios vive en la firma
        del formulario, no aqui), asi que no colapsa en una sola fila."""
        colegio_id = str(derivar("colegio", "2.4"))
        token = await self._token(cliente, "reenvio-sesion@ejemplo.com")
        cuerpo = {"hijos": [{"colegio_id": colegio_id, "grado": "Quinto"}]}
        cabecera = {"Authorization": f"Bearer {token}"}
        primero = await cliente.post("/v1/cuenta/matriculas", json=cuerpo, headers=cabecera)
        assert primero.json()["total"] == 1
        segundo = await cliente.post("/v1/cuenta/matriculas", json=cuerpo, headers=cabecera)
        assert segundo.json()["total"] == 1  # uno mas, realmente creado
        cuenta = (await cliente.get("/v1/cuenta/matriculas", headers=cabecera)).json()
        assert cuenta["total"] == 2

    async def test_reenviar_gemelos_agrega_mas(self, cliente):
        """Reenviar dos gemelos agrega dos mas (endpoint aditivo por diseno): 2 -> 4.
        La firma del formulario es lo que evita el reenvio accidental."""
        colegio_id = str(derivar("colegio", "2.4"))
        token = await self._token(cliente, "gemelos-sesion@ejemplo.com")
        cuerpo = {
            "hijos": [
                {"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Ana"},
                {"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Bea"},
            ]
        }
        cabecera = {"Authorization": f"Bearer {token}"}
        primero = await cliente.post("/v1/cuenta/matriculas", json=cuerpo, headers=cabecera)
        assert primero.json()["total"] == 2
        segundo = await cliente.post("/v1/cuenta/matriculas", json=cuerpo, headers=cabecera)
        assert segundo.json()["total"] == 2
        cuenta = (await cliente.get("/v1/cuenta/matriculas", headers=cabecera)).json()
        assert cuenta["total"] == 4

    async def test_agregar_otro_hijo_en_mismo_colegio_y_grado(self, cliente):
        """El portador YA tiene un hijo en (colegio, grado) por el registro;
        agregar OTRO en el mismo par con otro apodo debe crear una matricula NUEVA (no
        colapsar en la existente ni perder el apodo). Fija tambien la casacion de tipo
        de la clave del conteo: si fallara, colapsaria a 1 y esta prueba caeria."""
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "dos-hijos@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "hijos": [{"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Pipe"}],
            },
        )
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "dos-hijos@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]
        cabecera = {"Authorization": f"Bearer {token}"}
        respuesta = await cliente.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Sofi"}]},
            headers=cabecera,
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["total"] == 1  # uno realmente creado
        cuenta = (await cliente.get("/v1/cuenta/matriculas", headers=cabecera)).json()
        assert cuenta["total"] == 2
        assert {m["apodo"] for m in cuenta["matriculas"]} == {"Pipe", "Sofi"}

    async def test_un_tercero_tras_gemelos_del_registro_son_tres(self, cliente):
        """Registro con gemelos (2 en el mismo par) y luego un POST con un tercero en
        ese par: 3 matriculas distintas, no colapsar."""
        colegio_id = str(derivar("colegio", "2.4"))
        await cliente.post(
            "/v1/registro",
            json={
                "correo": "trillizos@ejemplo.com",
                "acepta_terminos": True,
                "clave": "clave1234",
                "hijos": [
                    {"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Ana"},
                    {"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Bea"},
                ],
            },
        )
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "trillizos@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]
        cabecera = {"Authorization": f"Bearer {token}"}
        respuesta = await cliente.post(
            "/v1/cuenta/matriculas",
            json={"hijos": [{"colegio_id": colegio_id, "grado": "Quinto", "apodo": "Cami"}]},
            headers=cabecera,
        )
        assert respuesta.json()["total"] == 1
        cuenta = (await cliente.get("/v1/cuenta/matriculas", headers=cabecera)).json()
        assert cuenta["total"] == 3
        assert {m["apodo"] for m in cuenta["matriculas"]} == {"Ana", "Bea", "Cami"}


class TestQuitarYCambiarHijos:
    """El acudiente quita a un hijo o lo cambia de colegio desde su panel.

    Quitar no borra: cierra el vinculo (`vigente_hasta`) y retira la matricula,
    que es lo que la retencion de datos de menores exige conservar. Cambiar de
    colegio retira la matricula vieja y crea la nueva con el mismo apodo.
    """

    async def _cuenta_con_hijo(self, cliente, correo: str, apodo: str = "Pipe") -> tuple[dict, str]:
        await cliente.post(
            "/v1/registro",
            json={"correo": correo, "acepta_terminos": True, "clave": "clave1234", "hijos": []},
        )
        token = (await cliente.post("/v1/sesiones", json={"correo": correo, "clave": "clave1234"})).json()[
            "token"
        ]
        cabecera = {"Authorization": f"Bearer {token}"}
        await cliente.post(
            "/v1/cuenta/matriculas",
            json={
                "hijos": [{"colegio_id": str(derivar("colegio", "2.4")), "grado": "Quinto", "apodo": apodo}]
            },
            headers=cabecera,
        )
        return cabecera, (await cliente.get("/v1/cuenta/matriculas", headers=cabecera)).json()["matriculas"][
            0
        ]["matricula_id"]

    async def _hijos(self, cliente, cabecera) -> list[dict]:
        return (await cliente.get("/v1/cuenta/matriculas", headers=cabecera)).json()["matriculas"]

    async def test_la_lista_trae_el_id_de_la_matricula(self, cliente):
        cabecera, matricula_id = await self._cuenta_con_hijo(cliente, "id-hijo@ejemplo.com")
        assert uuid.UUID(matricula_id)

    async def test_quitar_un_hijo(self, cliente):
        cabecera, matricula_id = await self._cuenta_con_hijo(cliente, "quitar@ejemplo.com")
        respuesta = await cliente.delete(f"/v1/cuenta/matriculas/{matricula_id}", headers=cabecera)
        assert respuesta.status_code == 204
        assert await self._hijos(cliente, cabecera) == []

    async def test_no_se_quita_el_hijo_de_otra_cuenta(self, cliente):
        _, matricula_id = await self._cuenta_con_hijo(cliente, "duena@ejemplo.com")
        otra, _ = await self._cuenta_con_hijo(cliente, "ajena@ejemplo.com", apodo="Otro")
        respuesta = await cliente.delete(f"/v1/cuenta/matriculas/{matricula_id}", headers=otra)
        assert respuesta.status_code == 404
        assert (await cliente.delete(f"/v1/cuenta/matriculas/{matricula_id}")).status_code == 401

    async def test_un_hijo_quitado_se_puede_volver_a_agregar(self, cliente):
        """La derivacion cae en la misma matricula retirada: se reactiva."""
        cabecera, matricula_id = await self._cuenta_con_hijo(cliente, "volver@ejemplo.com")
        await cliente.delete(f"/v1/cuenta/matriculas/{matricula_id}", headers=cabecera)
        respuesta = await cliente.post(
            "/v1/cuenta/matriculas",
            json={
                "hijos": [
                    {"colegio_id": str(derivar("colegio", "2.4")), "grado": "Quinto", "apodo": "Pipe 2"}
                ]
            },
            headers=cabecera,
        )
        assert respuesta.json()["total"] == 1
        hijos = await self._hijos(cliente, cabecera)
        assert [h["apodo"] for h in hijos] == ["Pipe 2"]

    async def test_cambiar_de_colegio_conserva_el_apodo(self, cliente):
        # El colegio "9.9" del fixture no tiene sede: se le da una para recibirlo.
        async with app.state.motor.sesion() as sesion:
            sesion.add(
                Sede(
                    id=derivar("sede", "9.9", "Sede unica"),
                    colegio_id=derivar("colegio", "9.9"),
                    nombre="Sede unica",
                )
            )
            await sesion.commit()
        cabecera, matricula_id = await self._cuenta_con_hijo(cliente, "cambiar@ejemplo.com")

        respuesta = await cliente.put(
            f"/v1/cuenta/matriculas/{matricula_id}",
            json={"colegio_id": str(derivar("colegio", "9.9")), "grado": "Sexto"},
            headers=cabecera,
        )
        assert respuesta.status_code == 200
        hijos = await self._hijos(cliente, cabecera)
        assert len(hijos) == 1
        assert hijos[0]["colegio_id"] == str(derivar("colegio", "9.9"))
        assert hijos[0]["grado"] == "Sexto"
        assert hijos[0]["apodo"] == "Pipe"

    async def test_cambiar_a_un_grado_invalido_no_toca_nada(self, cliente):
        cabecera, matricula_id = await self._cuenta_con_hijo(cliente, "malcambio@ejemplo.com")
        respuesta = await cliente.put(
            f"/v1/cuenta/matriculas/{matricula_id}",
            json={"colegio_id": str(derivar("colegio", "2.4")), "grado": "5"},
            headers=cabecera,
        )
        assert respuesta.status_code == 422
        hijos = await self._hijos(cliente, cabecera)
        assert [(h["grado"], h["apodo"]) for h in hijos] == [("Quinto", "Pipe")]
