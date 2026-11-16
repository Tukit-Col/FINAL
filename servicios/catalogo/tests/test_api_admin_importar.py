"""Importar una lista desde el onboarding o la sugerencia de un padre (`/v1/admin/listas/importar`)."""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
# ruff: noqa: F811

from __future__ import annotations

import base64
import uuid

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    COLEGIO,
    PDF_FALSO,
    PNG_FALSO,
    TAREA,
    _bandeja_de,
    _cuerpo_importar,
    cliente,
)
from tukit_catalogo.api import app


class TestImportarListaDesdeOnboarding:
    async def test_crea_una_version_sin_revisar_con_items_resueltos(self, cliente):
        respuesta = await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())
        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["items"] == 2
        assert cuerpo["revisada"] is False
        assert cuerpo["version_id"]
        assert cuerpo["tarea_id"]

        vista = (await cliente.get(f"/v1/admin/listas/{cuerpo['version_id']}/revision")).json()
        assert vista["revisada"] is False
        # El cuaderno se resolvio a concepto; la chaquira no y va a revision.
        cuaderno = next(i for i in vista["items"] if i["texto_original"].startswith("2 cuadernos"))
        assert cuaderno["concepto"] is not None
        chaquira = next(i for i in vista["items"] if i["texto_original"].startswith("chaquiras"))
        assert chaquira["concepto"] is None
        assert chaquira["requiere_revision"] is True

    async def test_el_documento_devuelve_el_pdf_crudo(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/documento")
        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"] == "application/pdf"
        assert respuesta.content == PDF_FALSO

    async def test_el_documento_png_conserva_su_tipo(self, cliente):
        # Una lista subida como imagen se sirve como image/png, no como PDF.
        cuerpo = _cuerpo_importar(
            evidencia={
                "documento_base64": base64.b64encode(PNG_FALSO).decode("ascii"),
                "percepcion_cruda": [{"pagina": 1, "crudo": "imagen de prueba"}],
            }
        )
        vid = (await cliente.post("/v1/admin/listas/importar", json=cuerpo)).json()["version_id"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/documento")
        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"] == "image/png"
        assert respuesta.content == PNG_FALSO

    async def test_la_percepcion_devuelve_paginas_e_items(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/percepcion")).json()
        assert cuerpo["version_id"] == vid
        assert cuerpo["paginas"] == [{"pagina": 1, "crudo": "cuadernos y chaquiras"}]
        assert {i["texto_original"] for i in cuerpo["items"]} == {
            "2 cuadernos cuadriculados",
            "chaquiras de colores",
        }

    async def test_la_percepcion_coacciona_un_crudo_viejo_de_lista_a_texto(self, cliente):
        # Versiones importadas antes del arreglo guardaron `crudo` como una LISTA
        # de objetos {descripcion,cantidad,confianza} en vez de texto. La region 2
        # lo pinta directo y una lista revienta React ("Objects are not valid as a
        # React child"). El endpoint tiene que devolverlo SIEMPRE como cadena,
        # sin depender de una migracion, para no romper las filas ya escritas.
        cuerpo_viejo = _cuerpo_importar(
            evidencia={
                "documento_base64": base64.b64encode(PDF_FALSO).decode("ascii"),
                "percepcion_cruda": [
                    {
                        "pagina": 1,
                        "crudo": [
                            {"descripcion": "2 cuadernos cuadriculados", "cantidad": 2, "confianza": 0.9},
                            {"descripcion": "caja de colores", "cantidad": None, "confianza": 0.8},
                        ],
                    }
                ],
            }
        )
        vid = (await cliente.post("/v1/admin/listas/importar", json=cuerpo_viejo)).json()["version_id"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/percepcion")).json()
        crudo = cuerpo["paginas"][0]["crudo"]
        assert isinstance(crudo, str)
        assert "2 cuadernos cuadriculados" in crudo
        assert "caja de colores" in crudo

    async def test_el_documento_sin_evidencia_es_404(self, cliente):
        # La version sembrada (abierta) no tiene tarea de evidencia.
        vid = cliente.ids["abierta"]
        for recurso in ("documento", "percepcion"):
            respuesta = await cliente.get(f"/v1/admin/listas/{vid}/{recurso}")
            assert respuesta.status_code == 404
            assert respuesta.json()["error"] == "sin_evidencia"

    async def test_reimportar_sube_numero_y_supersede_la_vigente(self, cliente):
        primera = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()
        segunda = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()
        assert primera["version_id"] != segunda["version_id"]

        # Una sola vigente por lista, con el numero mas alto.
        listas = (await cliente.get(f"/v1/admin/listas?colegio_id={COLEGIO}&grado=Sexto")).json()
        assert listas["total"] == 1
        assert listas["listas"][0]["numero"] == 2
        assert listas["listas"][0]["version_id"] == segunda["version_id"]

    async def test_un_item_invalido_no_repite_su_texto_en_el_error(self, cliente):
        secreto = "cuaderno del nino Juan Perez"
        cuerpo = _cuerpo_importar(items=[{"texto_original": secreto, "cantidad": 0, "confianza": 0.9}])
        respuesta = await cliente.post("/v1/admin/listas/importar", json=cuerpo)
        assert respuesta.status_code == 422
        env = respuesta.json()
        assert secreto not in str(env)
        assert env["campo"] == "cantidad"

    async def test_sin_contacto_la_tarea_queda_sin_referencia(self, cliente):
        # El onboarding del colegio no trae un padre esperando: la tarea de
        # evidencia nace sin `contacto_referencia`.
        env = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.contacto_referencia is None

    async def test_con_contacto_la_tarea_referencia_al_padre_que_espera(self, cliente):
        # La subida de un acudiente importa la version PERO deja la traza al
        # padre por identificador (nunca su correo/telefono) para avisarle
        # cuando un administrador la apruebe.
        referencia = str(uuid.uuid4())
        env = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(contacto_referencia=referencia),
            )
        ).json()
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert str(fila.contacto_referencia) == referencia

    async def test_un_contacto_invalido_es_422_sin_repetir_el_documento(self, cliente):
        cuerpo = _cuerpo_importar(contacto_referencia="no-es-un-uuid")
        respuesta = await cliente.post("/v1/admin/listas/importar", json=cuerpo)
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "contacto_referencia"

    async def test_las_preferencias_del_padre_se_guardan_en_la_tarea(self, cliente):
        # Las preferencias que el padre declaro al subir se guardan tal cual para
        # que el kit de la aprobacion las use, en vez de los pesos por omision.
        preferencias = {
            "pesos": {"precio": 0.6, "marca_exigida": 0.15, "calidad": 0.2, "personaje": 0.05},
            "disposicion_sobreprecio": 0.0,
        }
        env = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(preferencias=preferencias),
            )
        ).json()
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.preferencias == preferencias

    async def test_sin_preferencias_la_tarea_las_deja_en_null(self, cliente):
        env = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.preferencias is None

    async def test_preferencias_que_no_son_objeto_es_422(self, cliente):
        cuerpo = _cuerpo_importar(preferencias=["no", "es", "objeto"])
        respuesta = await cliente.post("/v1/admin/listas/importar", json=cuerpo)
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "preferencias"

    async def test_los_datos_del_colegio_se_guardan_en_la_tarea(self, cliente):
        # Cuando la lista llega por un colegio que aun no existe en Tukit (el
        # acudiente lo eligio del directorio o lo escribio), sus datos se guardan
        # tal cual para que la cola los muestre y la aprobacion cree la identidad.
        colegio_datos = {"dane": "311001105731", "nombre": "ACADEMIA CENTRAL DE SISTEMAS"}
        env = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(colegio_datos=colegio_datos),
            )
        ).json()
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.colegio_datos == colegio_datos

    async def test_sin_datos_de_colegio_la_tarea_los_deja_en_null(self, cliente):
        # Un colegio aliado ya conocido no trae datos que crear.
        env = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.colegio_datos is None

    async def test_datos_de_colegio_que_no_son_objeto_es_422(self, cliente):
        cuerpo = _cuerpo_importar(colegio_datos=["no", "es", "objeto"])
        respuesta = await cliente.post("/v1/admin/listas/importar", json=cuerpo)
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "colegio_datos"


class TestImportarConClaveDeIdempotencia:
    """Inteligencia reintenta la importacion de una subida que encontro el
    catalogo caido (ADR 0040). Si la primera entro y lo que se perdio fue la
    respuesta, el reintento trae la misma `clave_idempotencia` y tiene que
    recibir la version que ya existe, no crear otra."""

    async def _versiones(self, cliente) -> list[dict]:
        listas = (await cliente.get(f"/v1/admin/listas?colegio_id={COLEGIO}&grado=Sexto")).json()
        return listas["listas"]

    async def test_la_misma_clave_dos_veces_da_una_sola_version(self, cliente):
        clave = str(uuid.uuid4())
        primera = await cliente.post(
            "/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia=clave)
        )
        segunda = await cliente.post(
            "/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia=clave)
        )

        assert primera.status_code == segunda.status_code == 201
        assert segunda.json() == primera.json()
        [version] = await self._versiones(cliente)
        assert version["numero"] == 1
        async with app.state.motor.sesion() as db:
            conexion = await db.connection()
            tareas = list(
                await conexion.execute(TAREA.select().where(TAREA.c.clave_idempotencia == uuid.UUID(clave)))
            )
        assert len(tareas) == 1

    async def test_claves_distintas_son_versiones_distintas(self, cliente):
        primera = (
            await cliente.post(
                "/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia=str(uuid.uuid4()))
            )
        ).json()
        segunda = (
            await cliente.post(
                "/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia=str(uuid.uuid4()))
            )
        ).json()

        assert primera["version_id"] != segunda["version_id"]
        [vigente] = await self._versiones(cliente)
        assert vigente["numero"] == 2

    async def test_una_clave_invalida_es_422(self, cliente):
        respuesta = await cliente.post(
            "/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia="no-es-un-uuid")
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "clave_idempotencia"

    async def test_si_dos_entran_a_la_vez_la_segunda_recibe_la_primera(self, cliente, monkeypatch):
        # La carrera: las dos peticiones miran antes de escribir y ninguna ve a
        # la otra. El indice unico frena la segunda y su transaccion entera
        # (version y renglones incluidos) se deshace; responde con la primera.
        from tukit_catalogo.repositorios.admin import RepoAdmin

        clave = str(uuid.uuid4())
        primera = (
            await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia=clave))
        ).json()

        original = RepoAdmin.importacion_por_clave
        vistas = {"n": 0}

        async def _ciega_la_primera_vez(self, clave_):
            vistas["n"] += 1
            if vistas["n"] == 1:
                return None
            return await original(self, clave_)

        monkeypatch.setattr(RepoAdmin, "importacion_por_clave", _ciega_la_primera_vez)
        segunda = await cliente.post(
            "/v1/admin/listas/importar", json=_cuerpo_importar(clave_idempotencia=clave)
        )

        assert segunda.status_code == 201
        assert segunda.json() == primera
        [version] = await self._versiones(cliente)
        assert version["numero"] == 1


class TestEditarDatosDelColegioEnLaRevision:
    """El revisor completa los datos del colegio nuevo ANTES de aprobar, para que
    se vaya completo (logo, direccion, contacto...) y no solo con nombre y grado.
    Se guardan sobre `colegio_datos` de la tarea; al aprobar viajan en el evento
    `colegio_verificado` y Identidad crea el colegio con ellos."""

    async def test_la_revision_expone_los_datos_del_colegio_nuevo(self, cliente):
        colegio_datos = {"dane": "311001105731", "nombre": "ACADEMIA CENTRAL DE SISTEMAS"}
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(colegio_datos=colegio_datos),
            )
        ).json()["version_id"]

        vista = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert vista["colegio_datos"]["dane"] == "311001105731"
        assert vista["colegio_datos"]["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"

    async def test_la_revision_de_un_aliado_no_trae_datos_de_colegio(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        vista = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert vista["colegio_datos"] is None

    async def test_completar_atributos_los_persiste_y_aprobar_los_lleva_al_evento(self, cliente):
        colegio_datos = {"dane": "311001105731", "nombre": "ACADEMIA CENTRAL DE SISTEMAS"}
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(colegio_datos=colegio_datos),
            )
        ).json()["version_id"]

        # El revisor completa logo, direccion y contacto.
        parche = {
            "logo_url": "https://cdn.tukit.co/logos/aca.png",
            "direccion": "Calle 1 # 2-3",
            "contacto_email": "rector@aca.edu.co",
        }
        respuesta = await cliente.patch(f"/v1/admin/listas/{vid}/colegio", json=parche)
        assert respuesta.status_code == 200

        # Persistio sobre colegio_datos (merge, sin perder nombre/dane).
        vista = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert vista["colegio_datos"]["logo_url"] == "https://cdn.tukit.co/logos/aca.png"
        assert vista["colegio_datos"]["direccion"] == "Calle 1 # 2-3"
        assert vista["colegio_datos"]["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"

        # Al aprobar, esos datos viajan en el evento colegio_verificado.
        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200
        eventos = [f for f in await _bandeja_de(cliente) if f.tipo == "colegio_verificado"]
        assert len(eventos) == 1
        assert eventos[0].carga["logo_url"] == "https://cdn.tukit.co/logos/aca.png"
        assert eventos[0].carga["contacto_email"] == "rector@aca.edu.co"

    async def test_completar_un_aliado_sin_datos_de_colegio_es_409(self, cliente):
        # Una version de colegio ya aliado no tiene datos que completar.
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        respuesta = await cliente.patch(f"/v1/admin/listas/{vid}/colegio", json={"logo_url": "x"})
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "sin_colegio_por_crear"

    async def test_completar_una_version_ya_revisada_es_409(self, cliente):
        colegio_datos = {"dane": "311001105731", "nombre": "ACADEMIA CENTRAL DE SISTEMAS"}
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(colegio_datos=colegio_datos),
            )
        ).json()["version_id"]
        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200
        respuesta = await cliente.patch(f"/v1/admin/listas/{vid}/colegio", json={"logo_url": "x"})
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_ya_revisada"
        vista = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert "logo_url" not in (vista["colegio_datos"] or {})
