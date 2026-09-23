"""La superficie de ESCRITURA del catalogo: la revision de listas por HTTP.

`descubrir.py` ya tenia toda la maquina de revision como CLI; esto la expone
sobre HTTP para que la consola de administracion la maneje. Las pruebas corren
contra la app con `ASGITransport` y un motor SQLite inyectado a mano, igual que
`test_api_catalogo`, porque el arranque normal abriria Postgres.

Lo que protegen, mas alla de que las rutas respondan: que una version YA
REVISADA no se pueda editar (la puerta que `descubrir` cuida en el CLI vale
igual por HTTP), que cerrar exija que no queden propuestas sin decidir, y que
`nueva-version` nazca sin revisar para poder corregir una lista publicada.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    PropuestaProducto,
    Tienda,
    VersionListaOficial,
)
from tukit_comun.bd import MotorServicio

COLEGIO = uuid.UUID("11111111-1111-5111-8111-111111111111")
TAREA = Base.metadata.tables["tarea_importacion"]
CURADOR = uuid.UUID("22222222-2222-5222-8222-222222222222")


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """Una lista sin revisar y otra ya revisada, para ejercer la puerta.

    La sin revisar tiene una propuesta pendiente, que es lo que `cerrar` mira
    para negarse; la revisada existe para probar que editarla se rechaza y que
    `nueva-version` la clona en una nueva sin revisar.
    """
    cuaderno = Concepto(codigo="C001", nombre_canonico="cuaderno", categoria="Cuadernos")
    colores = Concepto(codigo="C002", nombre_canonico="colores", categoria="Arte")
    sesion.add_all([cuaderno, colores])
    sesion.flush()

    tienda = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    sesion.add(tienda)
    sesion.flush()

    # Productos curados para el concepto cuaderno (C001): uno por nivel, con
    # precio vigente. Es lo que la ruta rapida devuelve como `candidatos`,
    # keyed por concepto y sin buscar por texto.
    for nivel, sku, precio in (
        ("economico", "TK-C001-ECO", 4500),
        ("confiable", "TK-C001-CON", 9900),
        ("premium", "TK-C001-PRE", 18900),
    ):
        producto = ProductoCanonico(
            concepto_id=cuaderno.id,
            sku_interno=sku,
            nombre=f"Cuaderno {nivel}",
            marca="Norma",
            nivel=nivel,
            imagen_url=f"https://ejemplo.com/{sku}.jpg",
            atributos={"rayado": "cuadriculado"},
            unidades_por_empaque=1,
            curado_por=CURADOR,
        )
        sesion.add(producto)
        sesion.flush()
        oferta = OfertaTienda(
            producto_canonico_id=producto.id,
            tienda_id=tienda.id,
            referencia_externa=f"{tienda.slug}-{sku}",
            url=f"https://{tienda.slug}.com/{sku}",
            metodo_vinculacion="manual",
            disponible=True,
        )
        sesion.add(oferta)
        sesion.flush()
        sesion.add(
            PrecioOferta(
                oferta_id=oferta.id,
                valor_centavos=precio * 100,
                fuente="scraper",
                vigente_desde=datetime(2026, 2, 1, tzinfo=UTC),
            )
        )
    sesion.flush()

    # Lista SIN revisar (v1 vigente) con dos renglones y una propuesta pendiente.
    lista = ListaOficial(colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026)
    sesion.add(lista)
    sesion.flush()
    abierta = VersionListaOficial(lista_id=lista.id, numero=1, vigente=True)
    sesion.add(abierta)
    sesion.flush()
    item = ItemListaOficial(
        version_id=abierta.id,
        orden=1,
        texto_original="2 cuadernos cuadriculados",
        cantidad=2,
        concepto_id=cuaderno.id,
    )
    sesion.add_all(
        [
            item,
            ItemListaOficial(
                version_id=abierta.id,
                orden=2,
                texto_original="chaquiras de colores",
                cantidad=1,
                concepto_id=None,
                requiere_revision=True,
            ),
        ]
    )
    sesion.flush()
    sesion.add(
        PropuestaProducto(
            concepto_id=cuaderno.id,
            texto_origen="chaquiras de colores",
            tienda_id=tienda.id,
            referencia_externa="EX-1",
            nombre="Chaquiras surtidas x 100",
            precio_centavos=350000,
            nivel_sugerido="economico",
            estado="pendiente",
            # Atada a la version sin revisar: es lo que la vista de revision
            # muestra como candidato y lo que `cerrar` cuenta para negarse.
            version_lista_id=abierta.id,
            item_lista_id=item.id,
        )
    )

    # Lista YA revisada (otro grado), v1 vigente y revisada.
    lista2 = ListaOficial(colegio_id=COLEGIO, grado="Quinto", anio_lectivo=2026)
    sesion.add(lista2)
    sesion.flush()
    cerrada = VersionListaOficial(
        lista_id=lista2.id, numero=1, vigente=True, revisada_en=datetime(2026, 3, 1, tzinfo=UTC)
    )
    sesion.add(cerrada)
    sesion.flush()
    sesion.add_all(
        [
            ItemListaOficial(
                version_id=cerrada.id,
                orden=1,
                texto_original="1 cuaderno cosido",
                cantidad=1,
                concepto_id=cuaderno.id,
            ),
            # Renglon de compra directa al colegio (no surtible): sin concepto,
            # linea informativa. La ruta rapida lo devuelve con candidatos [].
            ItemListaOficial(
                version_id=cerrada.id,
                orden=2,
                texto_original="Agenda escolar institucional",
                cantidad=1,
                concepto_id=None,
                modo_adquisicion="venta_directa_editorial",
                instruccion_colegio="Se paga en la tesoreria del colegio.",
                requiere_revision=True,
            ),
        ]
    )
    sesion.flush()
    return {
        "cuaderno": cuaderno.id,
        "colores": colores.id,
        "abierta": abierta.id,
        "cerrada": cerrada.id,
        "lista_cerrada": lista2.id,
    }


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, uuid.UUID] = {}
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


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


class TestLaVistaDeRevision:
    async def test_trae_los_renglones_con_su_concepto_y_las_propuestas(self, cliente):
        vid = cliente.ids["abierta"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert cuerpo["revisada"] is False
        assert [i["orden"] for i in cuerpo["items"]] == [1, 2]
        cuaderno = cuerpo["items"][0]
        assert cuaderno["concepto"]["codigo"] == "C001"
        # El renglon sin concepto se ve como no resuelto, no desaparece.
        assert cuerpo["items"][1]["concepto"] is None
        assert cuerpo["items"][1]["requiere_revision"] is True
        # Las propuestas pendientes son los candidatos de la region 3.
        assert len(cuerpo["propuestas"]) == 1
        assert cuerpo["propuestas"][0]["precio"] == 3500
        assert cuerpo["propuestas"][0]["nombre"].startswith("Chaquiras")

    async def test_una_version_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.get(f"/v1/admin/listas/{uuid.uuid4()}/revision")
        assert respuesta.status_code == 404


class TestEditarUnRenglon:
    async def test_editar_persiste_sobre_una_version_sin_revisar(self, cliente):
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][1]["item_id"]

        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}",
            json={"concepto_codigo": "C002", "cantidad": 3, "requiere_revision": False},
        )
        assert respuesta.status_code == 200

        despues = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        editado = despues["items"][1]
        assert editado["concepto"]["codigo"] == "C002"
        assert editado["cantidad"] == 3
        assert editado["requiere_revision"] is False

    async def test_editar_una_version_revisada_se_rechaza(self, cliente):
        vid = cliente.ids["cerrada"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][0]["item_id"]
        respuesta = await cliente.patch(f"/v1/admin/listas/{vid}/items/{item_id}", json={"cantidad": 9})
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_ya_revisada"

    async def test_quitar_un_concepto_sin_marcar_revision_se_rechaza(self, cliente):
        # El CHECK del modelo: un renglon sin concepto SIEMPRE requiere revision.
        # La API lo dice como error de dominio antes de que la base lo grite.
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][0]["item_id"]
        respuesta = await cliente.patch(
            f"/v1/admin/listas/{vid}/items/{item_id}",
            json={"concepto_codigo": None, "requiere_revision": False},
        )
        assert respuesta.status_code == 422


class TestAgregarYQuitarRenglon:
    async def test_agregar_toma_el_siguiente_orden(self, cliente):
        vid = cliente.ids["abierta"]
        respuesta = await cliente.post(
            f"/v1/admin/listas/{vid}/items",
            json={"texto_original": "1 borrador", "cantidad": 1, "concepto_codigo": "C001"},
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["orden"] == 3

    async def test_quitar_saca_el_renglon(self, cliente):
        vid = cliente.ids["abierta"]
        revision = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        item_id = revision["items"][0]["item_id"]
        assert (await cliente.delete(f"/v1/admin/listas/{vid}/items/{item_id}")).status_code == 204
        despues = (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()
        assert len(despues["items"]) == 1

    async def test_agregar_en_una_version_revisada_se_rechaza(self, cliente):
        vid = cliente.ids["cerrada"]
        respuesta = await cliente.post(
            f"/v1/admin/listas/{vid}/items",
            json={"texto_original": "1 regla", "concepto_codigo": "C001"},
        )
        assert respuesta.status_code == 409


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


PDF_FALSO = b"%PDF-1.4 lista de utiles de prueba"


def _cuerpo_importar(**extra) -> dict:
    """El cuerpo del contrato que inteligencia manda a `importar`."""
    cuerpo = {
        "colegio_id": str(COLEGIO),
        "grado": "Sexto",
        "anio_lectivo": 2026,
        "items": [
            {"texto_original": "2 cuadernos cuadriculados", "cantidad": 2, "confianza": 0.91},
            {"texto_original": "chaquiras de colores", "cantidad": 1, "confianza": 0.3},
        ],
        "evidencia": {
            "documento_base64": base64.b64encode(PDF_FALSO).decode("ascii"),
            "percepcion_cruda": [{"pagina": 1, "crudo": "cuadernos y chaquiras"}],
        },
    }
    cuerpo.update(extra)
    return cuerpo


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

    async def test_la_percepcion_devuelve_paginas_e_items(self, cliente):
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/percepcion")).json()
        assert cuerpo["version_id"] == vid
        assert cuerpo["paginas"] == [{"pagina": 1, "crudo": "cuadernos y chaquiras"}]
        assert {i["texto_original"] for i in cuerpo["items"]} == {
            "2 cuadernos cuadriculados",
            "chaquiras de colores",
        }

    async def test_el_documento_sin_evidencia_es_404(self, cliente):
        # La version sembrada (abierta) no tiene tarea de evidencia.
        vid = cliente.ids["abierta"]
        assert (await cliente.get(f"/v1/admin/listas/{vid}/documento")).status_code == 404
        assert (await cliente.get(f"/v1/admin/listas/{vid}/percepcion")).status_code == 404

    async def test_importar_de_nuevo_sube_numero_y_supersede_la_vigente(self, cliente):
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


CAMPOS_CANDIDATO = {
    "sku",
    "nombre",
    "nivel",
    "precio_cop",
    "producto_id",
    "marca",
    "personaje",
    "imagen_url",
    "unidad_base",
    "unidades_por_empaque",
    "atributos",
    "cumple",
}


class TestResueltosLaRutaRapida:
    async def test_una_version_revisada_trae_items_concepto_y_candidatos(self, cliente):
        vid = cliente.ids["cerrada"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/resueltos")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["revisada"] is True
        assert cuerpo["grado"] == "Quinto"
        assert cuerpo["anio_lectivo"] == 2026
        assert cuerpo["colegio_id"] == str(COLEGIO)

        # Orden por `orden`: primero el cuaderno resuelto, luego la agenda.
        assert [i["orden"] for i in cuerpo["items"]] == [1, 2]
        cuaderno = cuerpo["items"][0]
        assert cuaderno["concepto_codigo"] == "C001"
        assert cuaderno["concepto_nombre"] == "cuaderno"
        assert cuaderno["texto_original"] == "1 cuaderno cosido"
        assert cuaderno["cantidad"] == 1
        # Los candidatos curados: uno por nivel, con precio.
        candidatos = cuaderno["candidatos"]
        assert {c["nivel"] for c in candidatos} == {"economico", "confiable", "premium"}
        eco = next(c for c in candidatos if c["nivel"] == "economico")
        assert eco["precio_cop"] == 4500
        assert eco["sku"] == "TK-C001-ECO"
        assert eco["cumple"] is True

    async def test_el_renglon_de_compra_directa_no_trae_candidatos(self, cliente):
        vid = cliente.ids["cerrada"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()
        agenda = cuerpo["items"][1]
        assert agenda["concepto_codigo"] is None
        assert agenda["concepto_nombre"] is None
        assert agenda["candidatos"] == []
        assert agenda["instruccion_colegio"] == "Se paga en la tesoreria del colegio."

    async def test_los_candidatos_tienen_las_llaves_del_dataclass(self, cliente):
        vid = cliente.ids["cerrada"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()
        candidatos = cuerpo["items"][0]["candidatos"]
        assert candidatos
        for candidato in candidatos:
            assert set(candidato.keys()) == CAMPOS_CANDIDATO
            assert isinstance(candidato["unidades_por_empaque"], int)
            assert candidato["unidades_por_empaque"] >= 1
            assert candidato["precio_cop"] is None or isinstance(candidato["precio_cop"], int)
            assert isinstance(candidato["atributos"], dict)

    async def test_una_version_sin_revisar_es_409(self, cliente):
        vid = cliente.ids["abierta"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/resueltos")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_no_revisada"

    async def test_una_version_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.get(f"/v1/admin/listas/{uuid.uuid4()}/resueltos")
        assert respuesta.status_code == 404


def _cuerpo_sugerencia(**extra) -> dict:
    """El cuerpo que el web manda cuando un padre sugiere su lista.

    Trae solo (colegio, grado, ano), un contacto por identificador y el PDF en
    base64. NO trae correo ni telefono: esa PII no cruza hacia Catalogo.
    """
    cuerpo = {
        "colegio_id": str(COLEGIO),
        "grado": "Septimo",
        "anio_lectivo": 2026,
        "contacto_referencia": str(uuid.uuid4()),
        "evidencia": {"documento_base64": base64.b64encode(PDF_FALSO).decode("ascii")},
    }
    cuerpo.update(extra)
    return cuerpo


class TestSugerenciaDeUnPadre:
    async def test_crea_una_tarea_pendiente_sugerencia_padre(self, cliente):
        cuerpo = _cuerpo_sugerencia()
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 201
        env = respuesta.json()
        assert env["estado"] == "pendiente"
        assert env["tarea_id"]

        # La tarea quedo en el backlog con origen y destino declarados.
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert fila.origen == "sugerencia_padre"
        assert fila.estado == "pendiente"
        assert fila.colegio_id == COLEGIO
        assert fila.grado == "Septimo"
        assert fila.anio_lectivo == 2026
        assert str(fila.contacto_referencia) == cuerpo["contacto_referencia"]
        assert fila.documento == PDF_FALSO
        # No hay version: es una sugerencia por atender, no una lista escrita.
        assert fila.version_id is None

    async def test_no_guarda_pii_solo_el_contacto_por_id(self, cliente):
        # El web nunca manda correo/telefono, pero si un cliente los cuela, ni
        # se aceptan ni se echan de vuelta: la respuesta solo trae id y estado.
        referencia = str(uuid.uuid4())
        cuerpo = _cuerpo_sugerencia(
            contacto_referencia=referencia,
            correo="mama@ejemplo.com",
            telefono="+573001112233",
        )
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 201
        env = respuesta.json()
        assert "mama@ejemplo.com" not in str(env)
        assert "+573001112233" not in str(env)

        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(TAREA.select().where(TAREA.c.id == uuid.UUID(env["tarea_id"])))
            ).one()
        assert str(fila.contacto_referencia) == referencia
        # No hay ninguna columna donde el correo/telefono pudiera haber caido.
        assert "mama@ejemplo.com" not in str(dict(fila._mapping))

    async def test_sin_documento_ni_contacto_igual_se_encola(self, cliente):
        cuerpo = _cuerpo_sugerencia(contacto_referencia=None, evidencia={"documento_base64": None})
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 201
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            fila = (
                await conexion.execute(
                    TAREA.select().where(TAREA.c.id == uuid.UUID(respuesta.json()["tarea_id"]))
                )
            ).one()
        assert fila.contacto_referencia is None
        assert fila.documento is None

    async def test_base64_invalido_es_422_sin_repetir_lo_enviado(self, cliente):
        cuerpo = _cuerpo_sugerencia(evidencia={"documento_base64": "no-es-base64!!"})
        respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
        assert respuesta.status_code == 422
        env = respuesta.json()
        assert env["error"] == "documento_invalido"
        assert env["campo"] == "documento_base64"
        assert "no-es-base64!!" not in str(env)


class TestElBacklogDeSugerencias:
    """La lista de sugerencias de padres que el administrador atiende.

    Solo las tareas con origen='sugerencia_padre' —no las de onboarding— y solo
    los campos seguros: el `contacto_referencia` es un id, nunca un correo ni un
    telefono, que son PII que vive unicamente en Identidad. No se hace ningun
    join para resolverlos.
    """

    async def test_lista_solo_las_sugerencias_con_campos_seguros(self, cliente):
        referencia = str(uuid.uuid4())
        await cliente.post("/v1/admin/sugerencias", json=_cuerpo_sugerencia(contacto_referencia=referencia))

        cuerpo = (await cliente.get("/v1/admin/sugerencias")).json()
        assert len(cuerpo["sugerencias"]) == 1
        s = cuerpo["sugerencias"][0]
        assert set(s.keys()) == {
            "tarea_id",
            "estado",
            "colegio_id",
            "grado",
            "anio_lectivo",
            "contacto_referencia",
            "tiene_documento",
        }
        assert s["estado"] == "pendiente"
        assert s["grado"] == "Septimo"
        assert s["anio_lectivo"] == 2026
        assert s["colegio_id"] == str(COLEGIO)
        assert s["contacto_referencia"] == referencia
        assert s["tiene_documento"] is True

    async def test_una_sin_documento_marca_tiene_documento_false(self, cliente):
        await cliente.post(
            "/v1/admin/sugerencias",
            json=_cuerpo_sugerencia(contacto_referencia=None, evidencia={"documento_base64": None}),
        )
        cuerpo = (await cliente.get("/v1/admin/sugerencias")).json()
        s = cuerpo["sugerencias"][0]
        assert s["tiene_documento"] is False
        assert s["contacto_referencia"] is None

    async def test_no_incluye_las_tareas_de_onboarding(self, cliente):
        # Onboarding escribe una tarea con origen='onboarding': no es sugerencia
        # de padre y no debe salir en este backlog.
        await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())
        await cliente.post("/v1/admin/sugerencias", json=_cuerpo_sugerencia())
        cuerpo = (await cliente.get("/v1/admin/sugerencias")).json()
        assert len(cuerpo["sugerencias"]) == 1

    async def test_nunca_devuelve_correo_ni_telefono(self, cliente):
        # Aunque un cliente cuele PII en el POST, ni se guarda ni puede aflorar
        # aqui: la respuesta solo trae el id de contacto.
        correo = "papa-secreto@ejemplo.com"
        telefono = "+573009998877"
        await cliente.post(
            "/v1/admin/sugerencias",
            json=_cuerpo_sugerencia(correo=correo, telefono=telefono),
        )
        texto = (await cliente.get("/v1/admin/sugerencias")).text
        assert correo not in texto
        assert telefono not in texto


class TestNuevaVersionParaCorregir:
    async def test_clona_la_vigente_revisada_en_una_sin_revisar(self, cliente):
        # Editar despues de aprobar: se clona la vigente en numero+1 sin revisar.
        respuesta = await cliente.post(f"/v1/admin/listas/{COLEGIO}/Quinto/nueva-version?anio_lectivo=2026")
        assert respuesta.status_code == 201
        nueva = respuesta.json()
        assert nueva["numero"] == 2
        assert nueva["revisada"] is False

        # La nueva es vigente y trae los renglones de la anterior.
        vista = (await cliente.get(f"/v1/admin/listas/{nueva['version_id']}/revision")).json()
        assert vista["revisada"] is False
        assert len(vista["items"]) == 2

        # Solo una version vigente por lista: la vieja dejo de serlo.
        listas = (await cliente.get(f"/v1/admin/listas?colegio_id={COLEGIO}&grado=Quinto")).json()
        assert listas["total"] == 1
        assert listas["listas"][0]["numero"] == 2
