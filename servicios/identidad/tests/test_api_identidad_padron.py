from __future__ import annotations

from tukit_comun.identificadores import derivar

from tests._ayudas_identidad import sembrar_usuario_con_rol


class TestElPadronDeAcudientes:
    async def _registrar(self, cliente, correo, apodo=None):
        hijo = {"colegio_id": str(derivar("colegio", "2.4")), "grado": "Quinto"}
        if apodo is not None:
            hijo["apodo"] = apodo
        respuesta = await cliente.post(
            "/v1/registro",
            json={
                "correo": correo,
                "acepta_terminos": True,
                "clave": "clave1234",
                "celular": "3001112233",
                "hijos": [hijo],
            },
        )
        assert respuesta.status_code == 201
        return respuesta.json()["usuario_id"]

    async def test_un_acudiente_no_ve_el_padron_ni_el_apodo(self, cliente):
        await self._registrar(cliente, "papa@ejemplo.com", apodo="Pipe")
        token = (
            await cliente.post("/v1/sesiones", json={"correo": "papa@ejemplo.com", "clave": "clave1234"})
        ).json()["token"]
        r = await cliente.get("/v1/admin/acudientes", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["error"] == "acceso_denegado"
        assert "Pipe" not in r.text

    async def test_admin_ve_al_acudiente_con_apodo_descifrado(self, cliente):
        await self._registrar(cliente, "familia@ejemplo.com", apodo="Pipe")
        _uid, token = await sembrar_usuario_con_rol("admin@tukit.co", "admin")
        r = await cliente.get("/v1/admin/acudientes", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        fila = next(a for a in r.json()["acudientes"] if a["correo"] == "familia@ejemplo.com")
        assert fila["celular"] == "3001112233"
        assert fila["creado_en"]
        assert fila["hijos"][0] == {
            "apodo": "Pipe",
            "colegio_id": str(derivar("colegio", "2.4")),
            "colegio_nombre": "Colegio San Pedro",
            "grado": "Quinto",
        }

    async def test_operador_tambien_puede(self, cliente):
        _uid, token = await sembrar_usuario_con_rol("operador@tukit.co", "operador")
        await self._registrar(cliente, "familia-op@ejemplo.com", apodo="Lu")
        r = await cliente.get("/v1/admin/acudientes", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        fila = next(a for a in r.json()["acudientes"] if a["correo"] == "familia-op@ejemplo.com")
        assert fila["hijos"][0]["apodo"] == "Lu"

    async def test_hijo_sin_apodo_sale_como_null(self, cliente):
        await self._registrar(cliente, "sinapodo@ejemplo.com", apodo=None)
        _uid, token = await sembrar_usuario_con_rol("admin@tukit.co", "admin")
        cuerpo = (
            await cliente.get("/v1/admin/acudientes", headers={"Authorization": f"Bearer {token}"})
        ).json()
        fila = next(a for a in cuerpo["acudientes"] if a["correo"] == "sinapodo@ejemplo.com")
        assert fila["hijos"][0]["apodo"] is None

    async def test_ids_acota_a_los_solicitados(self, cliente):
        a = await self._registrar(cliente, "a@ejemplo.com")
        await self._registrar(cliente, "b@ejemplo.com")
        _uid, token = await sembrar_usuario_con_rol("admin@tukit.co", "admin")
        cuerpo = (
            await cliente.get(f"/v1/admin/acudientes?ids={a}", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert {x["correo"] for x in cuerpo["acudientes"]} == {"a@ejemplo.com"}

    async def test_los_internos_no_aparecen_ni_pidiendolos_por_id(self, cliente):
        interno, _ = await sembrar_usuario_con_rol("rectoria@colegio.edu.co", "colegio_admin")
        _uid, token = await sembrar_usuario_con_rol("admin@tukit.co", "admin")
        general = (
            await cliente.get("/v1/admin/acudientes", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert str(interno) not in {x["usuario_id"] for x in general["acudientes"]}
        forzado = (
            await cliente.get(
                f"/v1/admin/acudientes?ids={interno}", headers={"Authorization": f"Bearer {token}"}
            )
        ).json()
        assert forzado["acudientes"] == []

    async def test_no_expone_campos_prohibidos(self, cliente):
        await self._registrar(cliente, "familia@ejemplo.com", apodo="Pipe")
        _uid, token = await sembrar_usuario_con_rol("admin@tukit.co", "admin")
        r = await cliente.get("/v1/admin/acudientes", headers={"Authorization": f"Bearer {token}"})
        for prohibido in ("clave_hash", "documento", "fecha_nacimiento", "estudiante_id"):
            assert prohibido not in r.text
        fila = next(a for a in r.json()["acudientes"] if a["correo"] == "familia@ejemplo.com")
        assert set(fila) == {"usuario_id", "correo", "celular", "creado_en", "hijos"}
        assert set(fila["hijos"][0]) == {"apodo", "colegio_id", "colegio_nombre", "grado"}
