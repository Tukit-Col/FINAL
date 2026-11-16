"""Lo que comparten las pruebas de la superficie de escritura de listas (`/v1/admin/listas/*`).

Las pruebas corren contra la app con `ASGITransport` y un motor SQLite inyectado
a mano, igual que `test_api_catalogo`, porque el arranque normal abriria
Postgres. La siembra deja una lista sin revisar (con una propuesta pendiente) y
otra ya revisada, para ejercer la puerta de revision.
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


async def _bandeja_de(cliente) -> list:
    motor = app.state.motor
    async with motor.sesion() as db:
        conexion = await db.connection()
        return list(await conexion.execute(BANDEJA.select()))


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
