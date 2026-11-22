# ruff: noqa: F811

from __future__ import annotations

import uuid

import pytest
from _ayudas_api_admin import (  # noqa: F401  (el fixture `cliente` se reusa tal cual)
    COLEGIO,
    _cuerpo_importar,
    cliente,
)


class TestListarVersionesParaRevisar:
    async def test_las_lista_todas_con_su_estado(self, cliente):
        cuerpo = (await cliente.get("/v1/admin/listas")).json()
        assert cuerpo["total"] == 2
        por_grado = {v["grado"]: v for v in cuerpo["listas"]}
        assert por_grado["Cuarto"]["revisada"] is False
        assert por_grado["Cuarto"]["items"] == 2
        assert por_grado["Quinto"]["revisada"] is True

    async def test_filtra_por_revisada(self, cliente):
        pendientes = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        assert [v["grado"] for v in pendientes["listas"]] == ["Cuarto"]

    async def test_filtra_por_colegio_y_grado(self, cliente):
        cuerpo = (await cliente.get(f"/v1/admin/listas?colegio_id={COLEGIO}&grado=Quinto")).json()
        assert cuerpo["total"] == 1
        assert cuerpo["listas"][0]["grado"] == "Quinto"

    async def test_una_lista_sin_tarea_no_declara_procedencia(self, cliente):
        cuerpo = (await cliente.get("/v1/admin/listas")).json()
        cuarto = next(v for v in cuerpo["listas"] if v["grado"] == "Cuarto")
        assert cuarto["procedencia"] is None
        assert cuarto["tiene_contacto"] is False

    async def test_una_version_importada_declara_su_procedencia(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        cuerpo = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        importada = next(v for v in cuerpo["listas"] if v["version_id"] == vid)
        assert importada["procedencia"] == "onboarding"
        assert importada["tiene_contacto"] is False

    async def test_una_subida_de_acudiente_declara_sugerencia_padre(self, cliente):
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(
                    origen="sugerencia_padre", colegio_datos={"nombre": "Colegio San Ejemplo"}
                ),
            )
        ).json()["version_id"]
        cuerpo = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        subida = next(v for v in cuerpo["listas"] if v["version_id"] == vid)
        assert subida["procedencia"] == "sugerencia_padre"
        assert subida["colegio_nombre"] == "Colegio San Ejemplo"

    async def test_el_onboarding_de_un_colegio_nuevo_entra_con_su_nombre_y_sin_contacto(self, cliente):
        colegio_datos = {"dane": "311001105731", "nombre": "ACADEMIA CENTRAL DE SISTEMAS"}
        vid = (
            await cliente.post(
                "/v1/admin/listas/importar",
                json=_cuerpo_importar(origen="onboarding", colegio_datos=colegio_datos),
            )
        ).json()["version_id"]
        cuerpo = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        subida = next(v for v in cuerpo["listas"] if v["version_id"] == vid)
        assert subida["procedencia"] == "onboarding"
        assert subida["tiene_contacto"] is False
        assert subida["colegio_nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert revision["colegio_datos"] == colegio_datos

    async def _subida_de(self, cliente, contacto: uuid.UUID) -> str:
        cuerpo = _cuerpo_importar(origen="sugerencia_padre", contacto_referencia=str(contacto))
        return (await cliente.post("/v1/admin/listas/importar", json=cuerpo)).json()["version_id"]

    async def test_la_lista_que_el_acudiente_cancela_sale_de_la_cola(self, cliente):
        padre = uuid.uuid4()
        vid = await self._subida_de(cliente, padre)
        retiro = await cliente.post(f"/interno/listas-por-contacto/{padre}/retirar", json={"version_id": vid})
        assert retiro.json()["retiradas"] == 1

        cola = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        assert vid not in [v["version_id"] for v in cola["listas"]]
        todas = (await cliente.get("/v1/admin/listas")).json()
        retirada = next(v for v in todas["listas"] if v["version_id"] == vid)
        assert retirada["retirada_por_acudiente"] is True
        assert retirada["tiene_contacto"] is False

    async def test_una_lista_sin_acudiente_que_nadie_retiro_queda_en_la_cola(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]

        cola = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        sigue = next(v for v in cola["listas"] if v["version_id"] == vid)
        assert sigue["retirada_por_acudiente"] is False
        assert sigue["tiene_contacto"] is False

    async def test_un_origen_desconocido_se_rechaza(self, cliente):
        respuesta = await cliente.post(
            "/v1/admin/listas/importar", json=_cuerpo_importar(origen="cualquier_cosa")
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "origen_invalido"


class TestLaVistaDeRevision:
    async def test_trae_los_renglones_con_su_concepto_y_las_propuestas(self, cliente):
        vid = cliente.ids["abierta"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert cuerpo["revisada"] is False
        assert [i["orden"] for i in cuerpo["items"]] == [1, 2]
        cuaderno = cuerpo["items"][0]
        assert cuaderno["concepto"]["codigo"] == "C001"
        assert cuerpo["items"][1]["concepto"] is None
        assert cuerpo["items"][1]["requiere_revision"] is True
        assert len(cuerpo["propuestas"]) == 1
        assert cuerpo["propuestas"][0]["precio"] == 3500
        assert cuerpo["propuestas"][0]["nombre"].startswith("Chaquiras")


class TestEliminarUnaVersionDeLaCola:
    async def test_eliminar_una_version_sin_revisar_la_saca_de_la_cola(self, cliente):
        vid = cliente.ids["abierta"]
        assert (await cliente.delete(f"/v1/admin/listas/{vid}")).status_code == 204

        assert (await cliente.get(f"/v1/admin/listas/{vid}/revision")).status_code == 404
        pendientes = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        assert all(v["version_id"] != str(vid) for v in pendientes["listas"])

    async def test_una_version_revisada_no_se_elimina(self, cliente):
        vid = cliente.ids["cerrada"]
        respuesta = await cliente.delete(f"/v1/admin/listas/{vid}")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_ya_revisada"

    async def test_eliminar_la_subida_nueva_le_devuelve_la_vigencia_a_la_aprobada(self, cliente):
        cerrada = cliente.ids["cerrada"]
        nueva = (
            await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(grado="Quinto"))
        ).json()["version_id"]
        assert (await cliente.delete(f"/v1/admin/listas/{nueva}")).status_code == 204

        resueltos = await cliente.get(f"/v1/admin/listas/{cerrada}/resueltos")
        assert resueltos.status_code == 200
        listas = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Quinto")).json()
        assert [v["version_id"] for v in listas["listas"]] == [str(cerrada)]


class TestUnaVersionQueNoExiste:
    @pytest.mark.parametrize(
        ("metodo", "sufijo"),
        [("GET", "/revision"), ("DELETE", ""), ("GET", "/resueltos")],
        ids=["revision", "eliminar", "resueltos"],
    )
    async def test_es_404_version_no_existe(self, cliente, metodo, sufijo):
        respuesta = await cliente.request(metodo, f"/v1/admin/listas/{uuid.uuid4()}{sufijo}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "version_no_existe"
