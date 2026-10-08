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
BANDEJA = Base.metadata.tables["bandeja_salida"]
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

    async def test_una_lista_sin_tarea_no_declara_procedencia(self, cliente):
        # Las versiones sembradas a mano no nacen de una importacion, asi que la
        # cola no puede atribuirles una procedencia ni un padre esperando.
        cuerpo = (await cliente.get("/v1/admin/listas")).json()
        cuarto = next(v for v in cuerpo["listas"] if v["grado"] == "Cuarto")
        assert cuarto["procedencia"] is None
        assert cuarto["tiene_contacto"] is False

    async def test_una_version_importada_declara_su_procedencia(self, cliente):
        # Una version que nace de `importar` (onboarding) la trae etiquetada,
        # para que la cola distinga "el colegio la envio" de "un padre la subio".
        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        cuerpo = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        importada = next(v for v in cuerpo["listas"] if v["version_id"] == vid)
        assert importada["procedencia"] == "onboarding"
        assert importada["tiene_contacto"] is False

    async def test_una_subida_de_acudiente_declara_sugerencia_padre(self, cliente):
        # La subida del acudiente manda origen='sugerencia_padre' en el cuerpo:
        # la cola tiene que verlo asi para decir "un acudiente la subio". Sin
        # esto, `importar` fijaba siempre 'onboarding' y mentia en la insignia.
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
        # Y el nombre del colegio nuevo viaja para que la cola no muestre el id.
        assert subida["colegio_nombre"] == "Colegio San Ejemplo"

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


class TestEliminarUnaVersionDeLaCola:
    async def test_eliminar_una_version_sin_revisar_la_saca_de_la_cola(self, cliente):
        vid = cliente.ids["abierta"]
        assert (await cliente.delete(f"/v1/admin/listas/{vid}")).status_code == 204

        assert (await cliente.get(f"/v1/admin/listas/{vid}/revision")).status_code == 404
        pendientes = (await cliente.get("/v1/admin/listas?revisada=false")).json()
        assert all(v["version_id"] != str(vid) for v in pendientes["listas"])

    async def test_una_version_revisada_no_se_elimina(self, cliente):
        """La revisada es la que ve el acudiente y contra la que alguien pudo
        comprar: no sale por la puerta de la cola."""
        vid = cliente.ids["cerrada"]
        respuesta = await cliente.delete(f"/v1/admin/listas/{vid}")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_ya_revisada"

    async def test_eliminar_la_subida_nueva_le_devuelve_la_vigencia_a_la_aprobada(self, cliente):
        """Subir una lista nueva le quita la vigencia a la aprobada. Si esa
        subida se elimina, el acudiente no puede quedarse sin la aprobada."""
        cerrada = cliente.ids["cerrada"]
        nueva = (
            await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(grado="Quinto"))
        ).json()["version_id"]
        assert (await cliente.delete(f"/v1/admin/listas/{nueva}")).status_code == 204

        resueltos = await cliente.get(f"/v1/admin/listas/{cerrada}/resueltos")
        assert resueltos.status_code == 200
        listas = (await cliente.get(f"/v1/listas?colegio_id={COLEGIO}&grado=Quinto")).json()
        assert [v["version_id"] for v in listas["listas"]] == [str(cerrada)]

    async def test_una_version_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.delete(f"/v1/admin/listas/{uuid.uuid4()}")
        assert respuesta.status_code == 404


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

    async def test_las_listas_aprobadas_antes_reciben_su_evento_una_sola_vez(self, cliente):
        # Una lista aprobada antes de que existiera `lista_aprobada` no tiene
        # kits canonicos: `canonicos.emitir` le deja el evento que le falto, y
        # correrlo otra vez no lo repite.
        from sqlalchemy import delete
        from tukit_catalogo import canonicos

        vid = (await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar())).json()["version_id"]
        assert (await cliente.post(f"/v1/admin/listas/{vid}/cerrar")).status_code == 200
        motor = app.state.motor
        async with motor.sesion() as db:
            conexion = await db.connection()
            # Como si se hubiera aprobado antes del cambio: sin evento.
            await conexion.execute(delete(BANDEJA).where(BANDEJA.c.tipo == "lista_aprobada"))
            # La semilla trae otras listas aprobadas: tambien reciben el suyo.
            emitidos = await canonicos.emitir(conexion)
            assert emitidos >= 1
            assert await canonicos.emitir(conexion) == 0
            await db.commit()

        eventos = {str(e.agregado_id): e for e in await self._bandeja("lista_aprobada")}
        assert len(eventos) == emitidos
        assert eventos[vid].carga["grado"] == "Sexto"

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


PDF_FALSO = b"%PDF-1.4 lista de utiles de prueba"
PNG_FALSO = b"\x89PNG\r\n\x1a\n" + b"lista de utiles de prueba"


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


async def _bandeja_de(cliente) -> list:
    motor = app.state.motor
    async with motor.sesion() as db:
        conexion = await db.connection()
        return list(await conexion.execute(BANDEJA.select()))


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

    async def test_un_concepto_sin_atributos_que_filtren_ofrece_todos_sus_productos_lisos(self, cliente):
        # Antes salia uno por nivel (tres a lo sumo) aunque el concepto tuviera
        # cuarenta: el kit nunca veia el resto del catalogo.
        await _con_cuadernos_extra(cliente)
        vid = cliente.ids["cerrada"]
        cuerpo = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()
        skus = {c["sku"] for c in cuerpo["items"][0]["candidatos"]}
        assert {"TK-C001-ECO", "TK-C001-CON", "TK-C001-PRE", "TK-REV-RAYADO"} <= skus
        # El de personaje no entra mientras haya lisos.
        assert "TK-REV-CARS" not in skus

    async def test_un_renglon_que_exige_un_atributo_solo_ofrece_los_que_lo_cumplen(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno rayado de 100 hojas")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert [c["sku"] for c in item["candidatos"]] == ["TK-REV-RAYADO"]
        assert item["atributos_impuestos"] == {"rayado": "rayado"}
        assert all(c["cumple"] for c in item["candidatos"])

    async def test_si_ningun_producto_cumple_no_hay_candidatos(self, cliente):
        # Un hueco, no un sustituto: el kit recomendaba un oleo para un acrilico.
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno ferrocarril")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert item["candidatos"] == []
        assert item["atributos_impuestos"] == {"rayado": "ferrocarril"}

    async def test_el_personaje_entra_solo_si_es_el_unico_que_cumple(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno doble linea")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert [c["sku"] for c in item["candidatos"]] == ["TK-REV-CARS"]

    async def test_lo_que_el_revisor_corrigio_en_la_curaduria_manda_sobre_lo_leido(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno ferrocarril", atributos={"rayado": "rayado"})
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert [c["sku"] for c in item["candidatos"]] == ["TK-REV-RAYADO"]

    async def test_un_renglon_con_varios_valores_se_marca_para_revisar(self, cliente):
        await _con_cuadernos_extra(cliente, discriminantes=["rayado"])
        vid = await _version_revisada_con(cliente, "cuaderno rayado o cuadriculado")
        item = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"][0]
        assert item["atributos_impuestos"] == {}
        assert item["atributos_por_revisar"] == ["rayado"]

    async def test_dice_si_el_concepto_es_uno_por_estudiante(self, cliente):
        await _marcar_uno_por_estudiante(cliente, "colores")
        vid = await _version_revisada_con_renglones(
            cliente, [("Caja de colores", "colores"), ("colores", "colores")]
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["uno_por_estudiante"] for i in items] == [True, True]
        # Lo que se junta solo no se marca como repetido: no hay nada que revisar.
        assert [i["posible_repetido_de"] for i in items] == [None, None]

    async def test_un_consumible_casi_igual_a_otro_se_marca_como_posible_repetido(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente, [("Pegante en barra", "colores"), ("cinta", "colores"), ("pegante en barra", "colores")]
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["posible_repetido_de"] for i in items] == [None, None, 1]

    async def test_dos_colores_de_la_misma_pintura_no_son_repetidos(self, cliente):
        async with app.state.motor.sesion() as db:
            conexion = await db.connection()
            tabla = Base.metadata.tables["concepto"]
            await conexion.execute(
                tabla.update()
                .where(tabla.c.id == cliente.ids["colores"])
                .values(atributos_discriminantes=["color"])
            )
            await db.commit()
        vid = await _version_revisada_con_renglones(
            cliente,
            [
                ("Pinturas acrilicas tubo de 45 cc: cian", "colores"),
                ("Pinturas acrilicas tubo de 45 cc: magenta", "colores"),
            ],
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["posible_repetido_de"] for i in items] == [None, None]

    async def test_un_cuaderno_por_materia_no_es_un_repetido(self, cliente):
        vid = await _version_revisada_con_renglones(
            cliente,
            [
                ("cuaderno cuadriculado 100 hojas", "cuaderno"),
                ("cuaderno cuadriculado 100 hojas", "cuaderno"),
            ],
        )
        items = (await cliente.get(f"/v1/admin/listas/{vid}/resueltos")).json()["items"]
        assert [i["posible_repetido_de"] for i in items] == [None, None]

    async def test_una_version_sin_revisar_es_409(self, cliente):
        vid = cliente.ids["abierta"]
        respuesta = await cliente.get(f"/v1/admin/listas/{vid}/resueltos")
        assert respuesta.status_code == 409
        assert respuesta.json()["error"] == "lista_no_revisada"

    async def test_una_version_que_no_existe_es_404(self, cliente):
        respuesta = await cliente.get(f"/v1/admin/listas/{uuid.uuid4()}/resueltos")
        assert respuesta.status_code == 404


async def _con_cuadernos_extra(cliente, discriminantes: list[str] | None = None) -> None:
    """Dos cuadernos mas en C001: uno rayado aprobado en la cola y uno de
    personaje doble linea. Con `discriminantes`, C001 filtra por ellos."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        concepto = Base.metadata.tables["concepto"]
        producto = Base.metadata.tables["producto_canonico"]
        if discriminantes:
            await conexion.execute(
                concepto.update()
                .where(concepto.c.id == cliente.ids["cuaderno"])
                .values(atributos_discriminantes=discriminantes)
            )
        for sku, atributos, personaje in (
            ("TK-REV-RAYADO", {"rayado": "rayado"}, None),
            ("TK-REV-CARS", {"rayado": "doble linea"}, "Cars"),
        ):
            await conexion.execute(
                producto.insert().values(
                    id=uuid.uuid4(),
                    concepto_id=cliente.ids["cuaderno"],
                    sku_interno=sku,
                    nombre=f"Cuaderno {sku}",
                    nivel="confiable",
                    personaje=personaje,
                    atributos=atributos,
                    unidad_base="unidad",
                    unidades_por_empaque=1,
                    es_propio=False,
                    es_representante_canonico=False,
                    quality_score=0.85,
                    activo=True,
                    curado_por=CURADOR,
                )
            )
        await db.commit()


async def _version_revisada_con(cliente, texto: str, atributos: dict | None = None) -> uuid.UUID:
    """Una lista revisada de un solo renglon de cuaderno con ese texto."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tablas = Base.metadata.tables
        lista_id, version_id = uuid.uuid4(), uuid.uuid4()
        await conexion.execute(
            tablas["lista_oficial"]
            .insert()
            .values(id=lista_id, colegio_id=COLEGIO, grado=f"G-{lista_id}", anio_lectivo=2026, activa=True)
        )
        await conexion.execute(
            tablas["version_lista_oficial"]
            .insert()
            .values(
                id=version_id,
                lista_id=lista_id,
                numero=1,
                vigente=True,
                revisada_en=datetime(2026, 3, 1, tzinfo=UTC),
            )
        )
        await conexion.execute(
            tablas["item_lista_oficial"]
            .insert()
            .values(
                id=uuid.uuid4(),
                version_id=version_id,
                orden=1,
                texto_original=texto,
                cantidad=1,
                concepto_id=cliente.ids["cuaderno"],
                modo_adquisicion="mercado_abierto",
                atributos=atributos or {},
                requiere_revision=False,
            )
        )
        await db.commit()
    return version_id


async def _marcar_uno_por_estudiante(cliente, concepto: str) -> None:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tabla = Base.metadata.tables["concepto"]
        await conexion.execute(
            tabla.update().where(tabla.c.id == cliente.ids[concepto]).values(uno_por_estudiante=True)
        )
        await db.commit()


async def _version_revisada_con_renglones(cliente, renglones: list[tuple[str, str]]) -> uuid.UUID:
    """Una lista revisada con esos (texto, concepto) en orden 1, 2, ..."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tablas = Base.metadata.tables
        lista_id, version_id = uuid.uuid4(), uuid.uuid4()
        await conexion.execute(
            tablas["lista_oficial"]
            .insert()
            .values(id=lista_id, colegio_id=COLEGIO, grado=f"G-{lista_id}", anio_lectivo=2026, activa=True)
        )
        await conexion.execute(
            tablas["version_lista_oficial"]
            .insert()
            .values(
                id=version_id,
                lista_id=lista_id,
                numero=1,
                vigente=True,
                revisada_en=datetime(2026, 3, 1, tzinfo=UTC),
            )
        )
        for orden, (texto, concepto) in enumerate(renglones, start=1):
            await conexion.execute(
                tablas["item_lista_oficial"]
                .insert()
                .values(
                    id=uuid.uuid4(),
                    version_id=version_id,
                    orden=orden,
                    texto_original=texto,
                    cantidad=1,
                    concepto_id=cliente.ids[concepto],
                    modo_adquisicion="mercado_abierto",
                    atributos={},
                    requiere_revision=False,
                )
            )
        await db.commit()
    return version_id


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


class TestCrearConcepto:
    async def test_autogenera_el_siguiente_codigo_y_parte_sinonimos(self, cliente):
        # La semilla tiene C001 y C002: el nuevo nace C003. Los sinonimos llegan
        # separados por "|" y se guardan como lista para que el matcher los use.
        respuesta = await cliente.post(
            "/v1/admin/catalogo/conceptos",
            json={
                "nombre_canonico": "plan lector digital",
                "categoria": "Diccionario / Biblia / Libros / Constitución",
                "sinonimos": "raz plus | plan lector virtual",
                "tipo_item": "licencia_digital",
            },
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["codigo"] == "C003"

        # El concepto quedo activo y con sus sinonimos: aparece en el vocabulario.
        from sqlalchemy import select
        from tukit_catalogo.admin_http import CONCEPTO, _motor

        async with _motor().engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(CONCEPTO.c.sinonimos, CONCEPTO.c.tipo_item).where(CONCEPTO.c.codigo == "C003")
                )
            ).one()
        assert list(fila.sinonimos) == ["raz plus", "plan lector virtual"]
        assert fila.tipo_item == "licencia_digital"

    async def test_guarda_los_atributos_que_filtran_y_los_que_informan(self, cliente):
        # El alta trae los dos papeles del atributo: el discriminante descarta
        # productos (un cuaderno cuadriculado no pasa por uno rayado) y el
        # descriptivo solo cuenta que se compra. Se normalizan a la forma del
        # corpus y un nombre repetido entre listas se queda solo como filtro,
        # porque la base prohibe que este en las dos.
        respuesta = await cliente.post(
            "/v1/admin/catalogo/conceptos",
            json={
                "nombre_canonico": "Bata de laboratorio",
                "categoria": "Uniformes",
                "atributos_discriminantes": ["Color", "manga larga"],
                "atributos_descriptivos": "talla | color",
            },
        )
        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["atributos_discriminantes"] == ["color", "manga_larga"]
        assert cuerpo["atributos_descriptivos"] == ["talla"]

        from sqlalchemy import select
        from tukit_catalogo.admin_http import CONCEPTO, _motor

        async with _motor().engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(CONCEPTO.c.atributos_discriminantes, CONCEPTO.c.atributos_descriptivos).where(
                        CONCEPTO.c.codigo == cuerpo["codigo"]
                    )
                )
            ).one()
        assert list(fila.atributos_discriminantes) == ["color", "manga_larga"]
        assert list(fila.atributos_descriptivos) == ["talla"]

    async def test_nombre_repetido_es_409(self, cliente):
        # "cuaderno" ya existe (C001): duplicarlo partiria el vocabulario, asi que
        # se rechaza y se invita a agregarle productos en vez de crear otro.
        respuesta = await cliente.post(
            "/v1/admin/catalogo/conceptos",
            json={"nombre_canonico": "Cuaderno", "categoria": "Cuadernos"},
        )
        assert respuesta.status_code == 409

    async def test_sin_nombre_o_categoria_es_422(self, cliente):
        assert (
            await cliente.post("/v1/admin/catalogo/conceptos", json={"categoria": "Arte"})
        ).status_code == 422
        assert (
            await cliente.post("/v1/admin/catalogo/conceptos", json={"nombre_canonico": "algo"})
        ).status_code == 422
