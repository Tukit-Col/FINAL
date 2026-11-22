"""Cerrar la revision de una lista: lo que exige y los eventos que deja en la bandeja.

Cerrar exige que no queden propuestas sin decidir, y al cerrar se emiten
`lista_aprobada`, `lista_verificada` (si hay padre esperando) y
`colegio_verificado` (si el colegio es nuevo), una sola vez cada uno.
"""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
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
        # Se decide la propuesta (rechazar corriente) para dejar cerrar.
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
        # Un padre subio su lista (version importada con `contacto_referencia` y
        # sus preferencias). Al aprobarla, se escribe un evento en la bandeja de
        # salida para que Inteligencia arme su kit —Catalogo no la llama directo—.
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
        # El poller arma el kit con la referencia REAL del hijo que subio la
        # lista (`hijo-2`), no con un `hijo-1` fijo: es la clave con la que el
        # formulario guardo su personaje en `personaje_por_hijo`.
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
        # El onboarding del colegio no deja padre esperando: aprobarlo no dispara
        # el kit de ningun acudiente (`lista_verificada`).
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]

        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200

        # El kit del grado sale de `lista_aprobada` (ADR 0029), no de la cola.
        assert await self._bandeja("lista_verificada") == []

    async def test_cerrar_cualquier_version_emite_lista_aprobada(self, cliente):
        # Con o sin padre esperando, aprobar la lista le pide a Inteligencia que
        # arme sus kits canonicos: el proximo acudiente sin tope de gasto los
        # recibe sin volver a correr el optimizador.
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]

        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200

        eventos = await self._bandeja("lista_aprobada")
        assert len(eventos) == 1
        evento = eventos[0]
        assert str(evento.agregado_id) == vid
        # `correlacion_id` lo agrega la bandeja (ADR 0022) para seguir el evento.
        carga = {k: v for k, v in evento.carga.items() if k != "correlacion_id"}
        assert carga == {"colegio_id": str(COLEGIO), "grado": "Sexto", "anio_lectivo": 2026}
        # Cerrar dos veces no arma dos veces: la segunda es un no-op.
        await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert len(await self._bandeja("lista_aprobada")) == 1

    async def test_cerrar_una_version_de_colegio_nuevo_emite_colegio_verificado(self, cliente):
        # Un acudiente subio la lista de un colegio que aun no existe en Tukit
        # (lo eligio del directorio o lo escribio): la version trae `colegio_datos`.
        # Al aprobarla, ademas de armar el kit, se emite `colegio_verificado` para
        # que Identidad cree el colegio como aliado —Catalogo no la llama directo—.
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
        # El colegio_id es el que el catalogo ya derivo; Identidad lo usa como PK.
        assert evento.carga["colegio_id"] == str(COLEGIO)
        assert evento.carga["grado"] == "Sexto"
        assert evento.carga["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"
        # El DANE viaja como `nit` (la columna del colegio en Identidad).
        assert evento.carga["nit"] == "311001105731"
        assert evento.carga["direccion"] == "Calle 1 # 2-3"
        # Onboarding sin padre esperando: la clave viaja pero en None (el guard de
        # este bloque es `colegio_datos`, no `contacto_referencia`).
        assert evento.carga["contacto_referencia"] is None

    async def test_colegio_verificado_lleva_contacto_referencia_cuando_hay_padre(self, cliente):
        # Un padre subio la lista de un colegio nuevo (trae `contacto_referencia` Y
        # `colegio_datos`): al aprobarla, `colegio_verificado` debe llevar tambien
        # su identificador opaco, para que el poller de Identidad matricule al hijo.
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
        # El padre, por identificador opaco; nunca su correo/telefono.
        assert evento.carga["contacto_referencia"] == referencia
        assert evento.carga["colegio_id"] == str(COLEGIO)
        assert evento.carga["grado"] == "Sexto"

    async def test_cerrar_un_colegio_aliado_conocido_no_emite_colegio_verificado(self, cliente):
        # Un colegio ya aliado (sin `colegio_datos`) no tiene identidad que crear:
        # aprobar su lista no emite el evento de colegio.
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        respuesta = await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        assert respuesta.status_code == 200
        assert await self._bandeja("colegio_verificado") == []

    async def test_cerrar_dos_veces_no_re_emite_el_evento(self, cliente):
        # `cerrar` sobre una version ya revisada devuelve `ya_estaba` sin tocar
        # nada: el evento se emite una sola vez, no en cada reintento.
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
