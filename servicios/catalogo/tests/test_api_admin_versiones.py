"""`nueva-version`: corregir una lista publicada en un borrador sin revisar."""

# El fixture `cliente` llega de `_ayudas_api_admin` y los tests lo reciben por nombre.
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
        # Editar despues de aprobar: se clona la vigente en numero+1 sin revisar,
        # PERO la vigente publicada no cambia hasta re-aprobar. El acudiente sigue
        # viendo la lista aprobada mientras se corrige.
        respuesta = await cliente.post(f"/v1/admin/listas/{COLEGIO}/Quinto/nueva-version?anio_lectivo=2026")
        assert respuesta.status_code == 201
        nueva = respuesta.json()
        assert nueva["numero"] == 2
        assert nueva["revisada"] is False

        # El borrador trae los renglones de la anterior y esta sin revisar.
        vista = (await cliente.get(f"/v1/admin/listas/{nueva['version_id']}/revision")).json()
        assert vista["revisada"] is False
        assert len(vista["items"]) == 2

        # La cola de administracion muestra el borrador (la de numero mayor).
        listas = (await cliente.get(f"/v1/admin/listas?colegio_id={COLEGIO}&grado=Quinto")).json()
        assert listas["total"] == 1
        assert listas["listas"][0]["numero"] == 2
        assert listas["listas"][0]["revisada"] is False

        # Pero el acudiente sigue viendo la vigente aprobada (numero 1): la
        # lectura publica sigue atada a `vigente`, y el borrador no la toco.
        publica = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Quinto&revisada=true")).json()
        assert publica["total"] == 1
        assert publica["listas"][0]["version"] == 1

    async def test_editar_una_no_revisada_es_409(self, cliente):
        # No se edita-clona algo que nunca se publico: la lista de Cuarto esta
        # sin revisar (v1 vigente sin revisada_en), asi que crear otra version se
        # rechaza —corrigela y aprobala en la cola en vez de bifurcarla.
        respuesta = await cliente.post(f"/v1/admin/listas/{COLEGIO}/Cuarto/nueva-version?anio_lectivo=2026")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_no_revisada"

    async def test_copia_la_evidencia_para_que_el_borrador_no_404(self, cliente):
        # El bug del 404: al clonar solo VERSION+ITEM el borrador quedaba sin
        # `tarea_importacion`, y el revisor de 4 paneles reventaba porque
        # /documento y /percepcion cuelgan de esa tarea. Importar (deja evidencia)
        # -> cerrar (la vuelve vigente+revisada) -> nueva-version debe copiar el
        # PDF y la percepcion al borrador.
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200

        clon = (
            await cliente.post(f"/v1/admin/listas/{COLEGIO}/Sexto/nueva-version?anio_lectivo=2026")
        ).json()
        assert clon["numero"] == 2

        # El PDF crudo viaja al borrador: /documento ya no es 404.
        doc = await cliente.get(f"/v1/admin/listas/{clon['version_id']}/documento")
        assert doc.status_code == 200
        assert doc.content == PDF_FALSO
        # Y la percepcion cruda tambien: /percepcion trae las paginas.
        perc = (await cliente.get(f"/v1/admin/listas/{clon['version_id']}/percepcion")).json()
        assert perc["paginas"] == [{"pagina": 1, "crudo": "cuadernos y chaquiras"}]

    async def test_la_copia_anula_contacto_y_preferencias(self, cliente):
        # Invariante del conteo de demanda: al "Editar (nueva versión)" la copia
        # CONSERVA `origen='sugerencia_padre'` pero ANULA `contacto_referencia` y
        # `preferencias`. Por eso la demanda se cuenta por contacto no nulo y una
        # copia de edición no suma. Se importa una sugerencia de padre (con
        # contacto y preferencias), se cierra y se clona; la copia debe nacer sin
        # contacto ni preferencias.
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
        assert fila.origen == "sugerencia_padre"  # el origen se conserva
        assert fila.contacto_referencia is None  # pero el contacto NO: no es demanda
        assert fila.preferencias is None

    async def test_al_cerrar_el_borrador_pasa_a_vigente_y_publica(self, cliente):
        # Aprobar la correccion es lo que le pasa la vigencia: hasta cerrar, el
        # publico ve v1; despues ve v2 y v1 deja de ser vigente.
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        await cliente.post(f"/v1/admin/listas/{vid}/cerrar")
        clon = (
            await cliente.post(f"/v1/admin/listas/{COLEGIO}/Sexto/nueva-version?anio_lectivo=2026")
        ).json()

        # Antes de cerrar el borrador, el publico sigue en v1.
        antes = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Sexto&revisada=true")).json()
        assert antes["listas"][0]["version"] == 1

        assert (await cliente.post(f"/v1/admin/listas/{clon['version_id']}/cerrar")).status_code == 200

        # Ahora el publico ve v2, y solo hay una vigente (la cola tambien la v2).
        despues = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Sexto&revisada=true")).json()
        assert despues["total"] == 1
        assert despues["listas"][0]["version"] == 2
