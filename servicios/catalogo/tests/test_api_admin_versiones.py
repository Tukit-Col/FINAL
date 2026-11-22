# ruff: noqa: F811

from __future__ import annotations

import uuid

from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    COLEGIO,
    PDF_FALSO,
    TAREA,
    _cuerpo_importar,
    cliente,
)


class TestNuevaVersionParaCorregir:
    async def test_clona_la_vigente_revisada_sin_tocar_la_publicada(self, cliente):
        respuesta = await cliente.post(f"/v1/admin/listas/{COLEGIO}/Quinto/nueva-version?anio_lectivo=2026")
        assert respuesta.status_code == 201
        nueva = respuesta.json()
        assert nueva["numero"] == 2
        assert nueva["revisada"] is False

        vista = (await cliente.get(f"/v1/admin/listas/{nueva['version_id']}/revision")).json()
        assert vista["revisada"] is False
        assert len(vista["items"]) == 2

        listas = (await cliente.get(f"/v1/admin/listas?colegio_id={COLEGIO}&grado=Quinto")).json()
        assert listas["total"] == 1
        assert listas["listas"][0]["numero"] == 2
        assert listas["listas"][0]["revisada"] is False

        publica = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Quinto&revisada=true")).json()
        assert publica["total"] == 1
        assert publica["listas"][0]["version"] == 1

    async def test_editar_una_no_revisada_es_409(self, cliente):
        respuesta = await cliente.post(f"/v1/admin/listas/{COLEGIO}/Cuarto/nueva-version?anio_lectivo=2026")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_no_revisada"

    async def test_copia_la_evidencia_para_que_el_borrador_no_404(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200

        clon = (
            await cliente.post(f"/v1/admin/listas/{COLEGIO}/Sexto/nueva-version?anio_lectivo=2026")
        ).json()
        assert clon["numero"] == 2

        doc = await cliente.get(f"/v1/admin/listas/{clon['version_id']}/documento")
        assert doc.status_code == 200
        assert doc.content == PDF_FALSO
        perc = (await cliente.get(f"/v1/admin/listas/{clon['version_id']}/percepcion")).json()
        assert perc["paginas"] == [{"pagina": 1, "crudo": "cuadernos y chaquiras"}]

    async def test_la_copia_anula_contacto_y_preferencias(self, cliente):
        referencia = str(uuid.uuid4())
        preferencias = {"nivel": "economico"}
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(
                    origen="sugerencia_padre",
                    contacto_referencia=referencia,
                    preferencias=preferencias,
                ),
            )
        ).json()["version_id"]
        await cliente.post(f"/v1/admin/listas/{vid}/cerrar")

        clon = (
            await cliente.post(f"/v1/admin/listas/{COLEGIO}/Sexto/nueva-version?anio_lectivo=2026")
        ).json()

        from tukit_catalogo.admin_http import _motor

        async with _motor().engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    TAREA.select().where(TAREA.c.version_id == uuid.UUID(clon["version_id"]))
                )
            ).one()
        assert fila.origen == "sugerencia_padre"
        assert fila.contacto_referencia is None
        assert fila.preferencias is None

    async def test_al_cerrar_el_borrador_pasa_a_vigente_y_publica(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        clon = (
            await cliente.post(f"/v1/admin/listas/{COLEGIO}/Sexto/nueva-version?anio_lectivo=2026")
        ).json()

        antes = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Sexto&revisada=true")).json()
        assert antes["listas"][0]["version"] == 1

        assert (await cliente.post(f"/v1/admin/listas/{clon['version_id']}/cerrar")).status_code == 200

        despues = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Sexto&revisada=true")).json()
        assert despues["total"] == 1
        assert despues["listas"][0]["version"] == 2
