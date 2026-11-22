from __future__ import annotations

import uuid

import pytest
from tukit_comun.identificadores import derivar
from tukit_identidad.routers.identidad import GRADOS


class TestElDirectorioNoFiltraDeMas:

    async def test_por_defecto_solo_devuelve_los_campos_del_alta(self, cliente):
        from tukit_identidad.dominio.directorio import (
            _indice_por_dane,
            datos_colegio_nuevo_por_dane,
        )

        dane = next(iter(_indice_por_dane()))
        cuerpo = (await cliente.get(f"/v1/directorio/{dane}")).json()
        assert set(cuerpo) == set(datos_colegio_nuevo_por_dane(dane))

    async def test_completo_agrega_el_superconjunto_del_admin(self, cliente):
        from tukit_identidad.dominio.directorio import _indice_por_dane

        dane = next(iter(_indice_por_dane()))
        cuerpo = (await cliente.get(f"/v1/directorio/{dane}?completo=true")).json()
        assert {"sector", "localidad", "rector", "telefonos", "correos"} <= set(cuerpo)


class TestElAcudienteEscogeColegioYGrado:
    async def test_los_colegios_traen_su_numero_de_sedes(self, cliente):
        cuerpo = (await cliente.get("/v1/colegios")).json()

        assert cuerpo["total"] == 2
        assert cuerpo["colegios"][0]["nombre"] == "Colegio San Pedro"
        assert cuerpo["colegios"][0]["sedes"] == 1

    async def test_el_identificador_es_el_derivado_que_usa_catalogo(self, cliente):
        cuerpo = (await cliente.get("/v1/colegios")).json()
        assert cuerpo["colegios"][0]["colegio_id"] == str(derivar("colegio", "2.4"))

    async def test_un_colegio_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get(f"/v1/colegios/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "colegio_no_existe"


class TestElPerfilDelColegio:

    async def test_el_detalle_trae_logo_sitio_y_contactos(self, cliente):
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert cuerpo["logo_url"] == "https://cdn.tukit.co/colegios/san-pedro.png"
        assert cuerpo["sitio_web"] == "https://sanpedro.edu.co"
        assert cuerpo["contacto_nombre"] == "Secretaria academica"
        assert cuerpo["contacto_email"] == "secretaria@sanpedro.edu.co"
        assert cuerpo["contacto_telefono"] == "+57 1 2345678"
        assert cuerpo["direccion"] == "Calle 1 # 2-3, Bogota"

    async def test_el_listado_trae_el_logo_para_la_tarjeta(self, cliente):
        cuerpo = (await cliente.get("/v1/colegios")).json()
        san_pedro = next(c for c in cuerpo["colegios"] if c["nombre"] == "Colegio San Pedro")
        assert san_pedro["logo_url"] == "https://cdn.tukit.co/colegios/san-pedro.png"

    async def test_el_listado_trae_el_dane_para_casar_el_buscador(self, cliente):
        cuerpo = (await cliente.get("/v1/colegios")).json()
        san_pedro = next(c for c in cuerpo["colegios"] if c["nombre"] == "Colegio San Pedro")
        assert san_pedro["dane"] == "311001093652"
        sin_perfil = next(c for c in cuerpo["colegios"] if c["nombre"] == "Colegio Sin Perfil")
        assert sin_perfil["dane"] is None

    async def test_un_colegio_sin_perfil_serializa_los_campos_como_null(self, cliente):
        cid = str(derivar("colegio", "9.9"))
        cuerpo = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert cuerpo["logo_url"] is None
        assert cuerpo["sitio_web"] is None
        assert cuerpo["contacto_nombre"] is None
        assert cuerpo["contacto_email"] is None
        assert cuerpo["contacto_telefono"] is None
        assert cuerpo["direccion"] is None

    async def test_los_grados_van_en_orden_escolar_y_no_alfabetico(self, cliente):
        cuerpo = (await cliente.get("/v1/grados")).json()
        assert cuerpo["grados"] == list(GRADOS)
        assert cuerpo["grados"][0] == "Parvulos"
        assert cuerpo["grados"][-1] == "Once"


class TestEditarElPerfilDelColegio:

    async def test_editar_persiste_y_hace_round_trip_por_el_get(self, cliente):
        cid = str(derivar("colegio", "9.9"))
        respuesta = await cliente.patch(
            f"/v1/colegios/{cid}",
            json={
                "logo_url": "https://cdn.tukit.co/colegios/sin-perfil.png",
                "contacto_email": "rectoria@sinperfil.edu.co",
            },
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["logo_url"] == "https://cdn.tukit.co/colegios/sin-perfil.png"
        assert cuerpo["contacto_email"] == "rectoria@sinperfil.edu.co"
        assert cuerpo["nombre"] == "Colegio Sin Perfil"

        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["logo_url"] == "https://cdn.tukit.co/colegios/sin-perfil.png"
        assert despues["contacto_email"] == "rectoria@sinperfil.edu.co"

    async def test_devuelve_la_misma_forma_que_el_detalle(self, cliente):
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (
            await cliente.patch(f"/v1/colegios/{cid}", json={"sitio_web": "https://nuevo.edu.co"})
        ).json()
        assert set(cuerpo.keys()) == {
            "colegio_id",
            "nombre",
            "dane",
            "logo_url",
            "sitio_web",
            "contacto_nombre",
            "contacto_email",
            "contacto_telefono",
            "direccion",
            "sedes",
        }
        assert cuerpo["sitio_web"] == "https://nuevo.edu.co"

    async def test_un_colegio_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.patch(f"/v1/colegios/{uuid.uuid4()}", json={"sitio_web": "x"})
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "colegio_no_existe"

    @pytest.mark.parametrize("campo", ["nombre", "nit"])
    async def test_los_campos_institucionales_no_se_editan(self, cliente, campo):
        cid = str(derivar("colegio", "2.4"))
        respuesta = await cliente.patch(f"/v1/colegios/{cid}", json={campo: "Otro"})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "campo_no_editable"
        assert respuesta.json()["campo"] == campo

    async def test_el_dane_si_se_puede_completar(self, cliente):
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (await cliente.patch(f"/v1/colegios/{cid}", json={"dane": "311001105731"})).json()
        assert cuerpo["dane"] == "311001105731"
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["dane"] == "311001105731"

    @pytest.mark.parametrize("dane", ["311001093", "311001105731a", "abcdefghijkl", "3110 0110573"])
    async def test_un_dane_que_no_son_12_digitos_es_400(self, cliente, dane):
        cid = str(derivar("colegio", "2.4"))
        respuesta = await cliente.patch(f"/v1/colegios/{cid}", json={"dane": dane})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "dane_invalido"
        assert respuesta.json()["campo"] == "dane"

    async def test_el_dane_se_puede_vaciar_con_null(self, cliente):
        cid = str(derivar("colegio", "2.4"))
        await cliente.patch(f"/v1/colegios/{cid}", json={"dane": "311001105731"})
        cuerpo = (await cliente.patch(f"/v1/colegios/{cid}", json={"dane": None})).json()
        assert cuerpo["dane"] is None
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["dane"] is None
