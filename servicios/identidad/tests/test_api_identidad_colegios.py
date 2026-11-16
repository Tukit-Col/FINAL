"""El catalogo institucional: colegios, su perfil, el directorio DUEB y los grados.

`/v1/colegios`, `/v1/colegios/{colegio_id}`, `/v1/directorio/{dane}` y
`/v1/grados`. Son datos institucionales, no de menor.
"""

from __future__ import annotations

import uuid

import pytest
from tukit_comun.identificadores import derivar
from tukit_identidad.routers.identidad import GRADOS


class TestElDirectorioNoFiltraDeMas:
    """`GET /v1/directorio/{dane}` sirve dos formas en la MISMA ruta. Por defecto
    solo los 7 campos del alta: es lo que la subida de listas vuelca sin filtrar
    en `colegio_datos`, asi que un campo de mas se filtraria a cada colegio nuevo.
    La ficha completa (sector, localidad, rector, telefonos, correos) solo sale
    con `?completo=true`, para el detalle del colegio en el admin. Se usa un DANE
    real del directorio (no uno inventado) para no acoplar la prueba a un codigo."""

    async def test_por_defecto_solo_devuelve_los_campos_del_alta(self, cliente):
        from tukit_identidad.dominio.directorio import (
            _indice_por_dane,
            datos_colegio_nuevo_por_dane,
        )

        dane = next(iter(_indice_por_dane()))
        cuerpo = (await cliente.get(f"/v1/directorio/{dane}")).json()
        # Igualdad exacta: ni una clave de mas. Esto protege el flujo de subida
        # (MapaRuiz) de que se filtren datos del directorio a `colegio_datos`.
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
        # Ordenados por nombre: "San Pedro" antes que "Sin Perfil".
        assert cuerpo["colegios"][0]["nombre"] == "Colegio San Pedro"
        assert cuerpo["colegios"][0]["sedes"] == 1

    async def test_el_identificador_es_el_derivado_que_usa_catalogo(self, cliente):
        """Es lo que hace que `lista_oficial.colegio_id` resuelva de verdad:
        los dos cargadores derivan el mismo UUID del mismo codigo."""
        cuerpo = (await cliente.get("/v1/colegios")).json()
        assert cuerpo["colegios"][0]["colegio_id"] == str(derivar("colegio", "2.4"))

    async def test_un_colegio_que_no_existe_es_404_con_codigo(self, cliente):
        respuesta = await cliente.get(f"/v1/colegios/{uuid.uuid4()}")
        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "colegio_no_existe"


class TestElPerfilDelColegio:
    """El logo y los contactos que el padre reconoce en la tarjeta de partner.

    Son datos institucionales, no de menor: no les aplica el cifrado del
    Anexo M que sí protege al estudiante en el mismo modelo. Por eso viajan en
    claro por la superficie pública, a diferencia de todo lo de `menor`.
    """

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
        # El logo va en el listado porque el desplegable del padre lo pinta
        # sin abrir el detalle; los contactos no, que son de la pantalla admin.
        cuerpo = (await cliente.get("/v1/colegios")).json()
        san_pedro = next(c for c in cuerpo["colegios"] if c["nombre"] == "Colegio San Pedro")
        assert san_pedro["logo_url"] == "https://cdn.tukit.co/colegios/san-pedro.png"

    async def test_el_listado_trae_el_dane_para_casar_el_buscador(self, cliente):
        # El buscador de `/empezar` compara el DANE del aliado contra el
        # directorio de Bogota para reconducir por `colegio_id`; sin el DANE en el
        # listado no podria, y volveria a darlo de alta como colegio del
        # directorio (el bug del duplicado). El que no tiene DANE serializa null.
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
    """El administrador completa el perfil institucional que el padre reconoce.

    Solo los campos institucionales —logo, sitio, contactos— son editables. El
    nombre y el NIT son la identidad de la institucion y no se tocan por esta
    puerta: cambiarlos rompe la referencia que Catalogo guarda por colegio_id.
    Estos datos NO son de menor, asi que no les toca el cifrado del Anexo M.
    """

    async def test_editar_persiste_y_hace_round_trip_por_el_get(self, cliente):
        cid = str(derivar("colegio", "9.9"))  # el que nace sin perfil
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
        # El nombre no se toca: es institucional y no vino en el cuerpo.
        assert cuerpo["nombre"] == "Colegio Sin Perfil"

        # Y persiste: el GET del detalle lo devuelve igual.
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
        """A diferencia del NIT, el DANE si se edita: aqui el id ya esta fijado y
        no se re-deriva del DANE, asi que completarlo cuando falta es seguro y es
        lo que habilita leer la ficha del directorio."""
        cid = str(derivar("colegio", "2.4"))
        cuerpo = (await cliente.patch(f"/v1/colegios/{cid}", json={"dane": "311001105731"})).json()
        assert cuerpo["dane"] == "311001105731"
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["dane"] == "311001105731"

    @pytest.mark.parametrize("dane", ["311001093", "311001105731a", "abcdefghijkl", "3110 0110573"])
    async def test_un_dane_que_no_son_12_digitos_es_400(self, cliente, dane):
        """El DANE es la llave del directorio DUEB: si no son 12 digitos exactos se
        rechaza antes de escribir, con el mismo formato de error 400 del endpoint."""
        cid = str(derivar("colegio", "2.4"))
        respuesta = await cliente.patch(f"/v1/colegios/{cid}", json={"dane": dane})
        assert respuesta.status_code == 400
        assert respuesta.json()["error"] == "dane_invalido"
        assert respuesta.json()["campo"] == "dane"

    async def test_el_dane_se_puede_vaciar_con_null(self, cliente):
        """`null` vacia el DANE (p. ej. si se cargo uno equivocado): es valido y
        deja el colegio sin ficha de directorio, sin romper."""
        cid = str(derivar("colegio", "2.4"))
        await cliente.patch(f"/v1/colegios/{cid}", json={"dane": "311001105731"})
        cuerpo = (await cliente.patch(f"/v1/colegios/{cid}", json={"dane": None})).json()
        assert cuerpo["dane"] is None
        despues = (await cliente.get(f"/v1/colegios/{cid}")).json()
        assert despues["dane"] is None
