# ruff: noqa: F811

from __future__ import annotations

import uuid

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    BANDEJA,
    COLEGIO,
    _cuerpo_importar,
    cliente,
)
from tukit_catalogo.api import app


class TestCerrarLaRevision:
    async def test_cerrar_con_propuestas_pendientes_se_niega(self, cliente):
        vid = cliente.ids["abierta"]
        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "propuestas_pendientes"

    async def test_cerrar_sin_pendientes_marca_revisada(self, cliente):
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        prop_id = revision["propuestas"][0]["id"]
        await cliente.post(f"/v1/admin/propuestas/{prop_id}/rechazar", json={"motivo": "no es"})

        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200
        despues = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert despues["revisada"] is True

    async def _bandeja(self, tipo: str | None = None) -> list:
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            filas = list(await conexion.execute(BANDEJA.select()))
        return [f for f in filas if tipo is None or f.tipo == tipo]

    async def test_cerrar_una_version_con_padre_esperando_emite_lista_verificada(self, cliente):
        referencia = str(uuid.uuid4())
        preferencias = {
            "pesos": {"precio": 0.6, "marca_exigida": 0.15, "calidad": 0.2, "personaje": 0.05},
            "disposicion_sobreprecio": 0.05,
        }
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(contacto_referencia=referencia, preferencias=preferencias),
            )
        ).json()["version_id"]

        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200

        eventos = await self._bandeja("lista_verificada")
        assert len(eventos) == 1
        evento = eventos[0]
        assert evento.agregado_tipo == "version_lista_oficial"
        assert str(evento.agregado_id) == vid
        assert evento.publicado_en is None
        assert evento.carga["contacto_referencia"] == referencia
        assert evento.carga["colegio_id"] == str(COLEGIO)
        assert evento.carga["grado"] == "Sexto"
        assert evento.carga["anio_lectivo"] == 2026
        assert evento.carga["preferencias"] == preferencias

    async def test_lista_verificada_lleva_las_referencias_de_los_hijos(self, cliente):
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(contacto_referencia=str(uuid.uuid4()), referencias=["hijo-2"]),
            )
        ).json()["version_id"]
        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200
        [evento] = await self._bandeja("lista_verificada")
        assert evento.carga["referencias"] == ["hijo-2"]

    async def test_referencias_que_no_son_lista_de_texto_se_rechazan(self, cliente):
        respuesta = await cliente.post(
            "/v1/admin/listas/importar", json=_cuerpo_importar(referencias="hijo-2")
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "referencias_invalidas"
        assert respuesta.json()["campo"] == "referencias"

    async def test_cerrar_un_onboarding_sin_padre_no_arma_kit_de_padre(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]

        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200

        assert await self._bandeja("lista_verificada") == []

    async def test_cerrar_cualquier_version_emite_lista_aprobada(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]

        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200

        eventos = await self._bandeja("lista_aprobada")
        assert len(eventos) == 1
        evento = eventos[0]
        assert str(evento.agregado_id) == vid
        carga = {k: v for k, v in evento.carga.items() if k != "correlacion_id"}
        assert carga == {"colegio_id": str(COLEGIO), "grado": "Sexto", "anio_lectivo": 2026}
        await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert len(await self._bandeja("lista_aprobada")) == 1

    async def test_cerrar_una_version_de_colegio_nuevo_emite_colegio_verificado(self, cliente):
        colegio_datos = {
            "dane": "311001105731",
            "nombre": "ACADEMIA CENTRAL DE SISTEMAS",
            "direccion": "Calle 1 # 2-3",
        }
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(colegio_datos=colegio_datos),
            )
        ).json()["version_id"]

        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200

        eventos = await self._bandeja("colegio_verificado")
        assert len(eventos) == 1
        evento = eventos[0]
        assert evento.agregado_tipo == "colegio"
        assert str(evento.agregado_id) == str(COLEGIO)
        assert evento.publicado_en is None
        assert evento.carga["colegio_id"] == str(COLEGIO)
        assert evento.carga["grado"] == "Sexto"
        assert evento.carga["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"
        assert evento.carga["nit"] == "311001105731"
        assert evento.carga["direccion"] == "Calle 1 # 2-3"
        assert evento.carga["contacto_referencia"] is None

    async def test_colegio_verificado_lleva_contacto_referencia_cuando_hay_padre(self, cliente):
        referencia = str(uuid.uuid4())
        colegio_datos = {
            "dane": "311001105731",
            "nombre": "ACADEMIA CENTRAL DE SISTEMAS",
            "direccion": "Calle 1 # 2-3",
        }
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(contacto_referencia=referencia, colegio_datos=colegio_datos),
            )
        ).json()["version_id"]

        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200

        eventos = await self._bandeja("colegio_verificado")
        assert len(eventos) == 1
        evento = eventos[0]
        assert evento.carga["contacto_referencia"] == referencia
        assert evento.carga["colegio_id"] == str(COLEGIO)
        assert evento.carga["grado"] == "Sexto"

    async def test_cerrar_un_colegio_aliado_conocido_no_emite_colegio_verificado(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200
        assert await self._bandeja("colegio_verificado") == []

    async def test_cerrar_dos_veces_no_re_emite_el_evento(self, cliente):
        referencia = str(uuid.uuid4())
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(contacto_referencia=referencia),
            )
        ).json()["version_id"]

        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200
        segunda = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert segunda.status_code == 200
        assert segunda.json().get("ya_estaba") is True
        assert len(await self._bandeja("lista_verificada")) == 1
