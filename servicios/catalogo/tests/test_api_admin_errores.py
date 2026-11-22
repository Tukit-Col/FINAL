"""NFR-MAN-01: las ramas de error y de validacion del router `/v1/admin` del catalogo.

`test_api_admin.py` y `test_curaduria_http.py` fijan el camino feliz de la
revision de listas. Aqui se caracterizan los rechazos: cada cuerpo mal formado
tiene que volver como un `ErrorDominio` con su codigo (`cuerpo_invalido`,
`item_invalido`, `cantidad_invalida`, `unidad_invalido`...) y su `campo`, y no
como un 500; y un rechazo no puede dejar escrituras a medias, porque la puerta
de la revision HITL valida TODO el cuerpo antes de tocar la base.

Corren contra la app con `ASGITransport` y un SQLite en memoria inyectado a
mano. El transporte NO relanza las excepciones de la app
(`raise_app_exceptions=False`): un fallo no controlado se ve como el 500 que
recibiria el cliente real, y asi se puede afirmar el codigo correcto (422) en
las pruebas que documentan defectos (xfail estricto).
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo import descubrir
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    PropuestaProducto,
    Tienda,
    VersionListaOficial,
)
from tukit_catalogo.routers.admin import _media_type_documento
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

COLEGIO = uuid.UUID("33333333-3333-5333-8333-333333333333")
TAREA = Base.metadata.tables["tarea_importacion"]
INEXISTENTE = uuid.UUID("99999999-9999-4999-8999-999999999999")

PDF_FALSO = b"%PDF-1.4 documento ficticio"
WEBP_FALSO = b"RIFF\x24\x00\x00\x00WEBPVP8 datos ficticios"


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """Cuatro listas para ejercer cada rechazo del router.

    - `abierta` (Cuarto): sin revisar, con un renglon resuelto, uno sin
      concepto y dos propuestas (una pendiente, otra ya rechazada).
    - `cerrada` (Quinto): revisada, con un renglon resuelto.
    - `solo_informativa` (Sexto): revisada y con renglones SIN concepto
      (compra directa): la ruta rapida no tiene conceptos que consultar.
    - `sin_vigente` (Septimo): una version que no es la vigente, para que
      `nueva-version` no encuentre de donde clonar.
    """
    cuaderno = Concepto(codigo="C001", nombre_canonico="cuaderno", categoria="Cuadernos")
    colores = Concepto(codigo="C002", nombre_canonico="colores", categoria="Arte")
    tienda = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    sesion.add_all([cuaderno, colores, tienda])
    sesion.flush()

    def _lista(grado: str, *, revisada: bool, vigente: bool = True) -> VersionListaOficial:
        lista = ListaOficial(colegio_id=COLEGIO, grado=grado, anio_lectivo=2026)
        sesion.add(lista)
        sesion.flush()
        version = VersionListaOficial(
            lista_id=lista.id,
            numero=1,
            vigente=vigente,
            revisada_en=datetime(2026, 3, 1, tzinfo=UTC) if revisada else None,
        )
        sesion.add(version)
        sesion.flush()
        return version

    abierta = _lista("Cuarto", revisada=False)
    resuelto = ItemListaOficial(
        version_id=abierta.id, orden=1, texto_original="2 cuadernos", cantidad=2, concepto_id=cuaderno.id
    )
    sin_concepto = ItemListaOficial(
        version_id=abierta.id,
        orden=2,
        texto_original="chaquiras de colores",
        cantidad=1,
        concepto_id=None,
        requiere_revision=True,
    )
    sesion.add_all([resuelto, sin_concepto])
    sesion.flush()
    pendiente = PropuestaProducto(
        concepto_id=cuaderno.id,
        texto_origen="chaquiras",
        tienda_id=tienda.id,
        referencia_externa="EX-1",
        nombre="Chaquiras surtidas",
        precio_centavos=350000,
        nivel_sugerido="economico",
        estado="pendiente",
        version_lista_id=abierta.id,
        item_lista_id=sin_concepto.id,
    )
    rechazada = PropuestaProducto(
        concepto_id=cuaderno.id,
        texto_origen="chaquiras",
        tienda_id=tienda.id,
        referencia_externa="EX-2",
        nombre="Chaquiras de otra marca",
        precio_centavos=400000,
        nivel_sugerido="confiable",
        estado="rechazada",
        version_lista_id=abierta.id,
        item_lista_id=sin_concepto.id,
    )
    sesion.add_all([pendiente, rechazada])

    cerrada = _lista("Quinto", revisada=True)
    sesion.add(
        ItemListaOficial(
            version_id=cerrada.id, orden=1, texto_original="1 cuaderno", cantidad=1, concepto_id=cuaderno.id
        )
    )

    informativa = _lista("Sexto", revisada=True)
    sesion.add_all(
        [
            ItemListaOficial(
                version_id=informativa.id,
                orden=orden,
                texto_original=texto,
                cantidad=1,
                concepto_id=None,
                modo_adquisicion="venta_directa_editorial",
                instruccion_colegio="Se paga en la tesoreria del colegio.",
                requiere_revision=True,
            )
            for orden, texto in enumerate(("Agenda institucional", "Carnet estudiantil"), start=1)
        ]
    )

    sin_vigente = _lista("Septimo", revisada=True, vigente=False)
    sesion.flush()
    return {
        "abierta": abierta.id,
        "resuelto": resuelto.id,
        "sin_concepto": sin_concepto.id,
        "pendiente": pendiente.id,
        "rechazada": rechazada.id,
        "cerrada": cerrada.id,
        "informativa": informativa.id,
        "sin_vigente": sin_vigente.id,
    }


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        http.fabrica = fabrica  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


def _cuerpo_importar(**cambios) -> dict:
    """El cuerpo del contrato que inteligencia manda a `importar`."""
    cuerpo = {
        "colegio_id": str(COLEGIO),
        "grado": "Octavo",
        "anio_lectivo": 2026,
        "items": [{"texto_original": "2 cuadernos cuadriculados", "cantidad": 2, "confianza": 0.9}],
        "evidencia": {
            "documento_base64": base64.b64encode(PDF_FALSO).decode("ascii"),
            "percepcion_cruda": [{"pagina": 1, "crudo": "cuadernos"}],
        },
    }
    cuerpo.update(cambios)
    return cuerpo


async def _total_listas(cliente) -> int:
    return (await cliente.get("/v1/admin/listas")).json()["total"]


async def _item(cliente, item_id: uuid.UUID) -> ItemListaOficial:
    async with cliente.fabrica() as sesion:
        return await sesion.get(ItemListaOficial, item_id)


async def _cuaderno_filtra_por(cliente, discriminantes: list[str]) -> None:
    """Desde `b12973e` lo curado en `atributos` tiene que ser discriminante del concepto
    (`_exigir_atributos_curables`, 422 `atributo_no_exigible`): C001 filtra por estos."""
    tabla = Base.metadata.tables["concepto"]
    async with cliente.fabrica() as sesion:
        await sesion.execute(
            tabla.update().where(tabla.c.codigo == "C001").values(atributos_discriminantes=discriminantes)
        )
        await sesion.commit()


# ---------------------------------------------------------------------------
# El tipo de contenido del documento de evidencia
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        (b"%PDF-1.7\n...", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n" + b"0" * 8, "image/png"),
        (b"\xff\xd8\xff\xe0" + b"0" * 8, "image/jpeg"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "application/octet-stream"),
        (b"texto cualquiera", "application/octet-stream"),
        (b"", "application/octet-stream"),
    ],
)
def test_el_tipo_del_documento_se_deduce_de_sus_primeros_bytes(datos, esperado):
    """La subida acepta PDF/JPG/PNG/WEBP y no guarda el tipo: se lee de la firma.

    Un RIFF que no es WEBP (un audio) o bytes sin firma no deben servirse como
    imagen ni PDF: caen en `application/octet-stream`.
    """
    assert _media_type_documento(datos) == esperado


async def test_el_documento_webp_se_sirve_con_su_tipo_y_sus_bytes_intactos(cliente):
    """Evidencia WEBP: el navegador la pinta como imagen y recibe los bytes tal cual."""
    cuerpo = _cuerpo_importar(
        evidencia={"documento_base64": base64.b64encode(WEBP_FALSO).decode("ascii"), "percepcion_cruda": []}
    )
    vid = (await cliente.post("/v1/admin/listas/importar", json=cuerpo)).json()["version_id"]
    respuesta = await cliente.get(f"/v1/admin/listas/{vid}/documento")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/webp"
    assert respuesta.content == WEBP_FALSO


async def test_la_percepcion_siempre_devuelve_el_crudo_como_texto(cliente):
    """Una pagina con `crudo` nulo o numerico, o una pagina suelta, igual sale como cadena.

    La region 2 de la consola renderiza `crudo` directo: un valor que no sea
    texto rompe React. El contrato `PercepcionCruda` es cadena siempre.
    """
    cuerpo = _cuerpo_importar(
        evidencia={
            "documento_base64": base64.b64encode(PDF_FALSO).decode("ascii"),
            "percepcion_cruda": [
                {"pagina": 2, "crudo": None},
                {"pagina": 3, "crudo": 42},
                "pagina suelta",
            ],
        }
    )
    vid = (await cliente.post("/v1/admin/listas/importar", json=cuerpo)).json()["version_id"]
    paginas = (await cliente.get(f"/v1/admin/listas/{vid}/percepcion")).json()["paginas"]
    assert paginas == [
        {"pagina": 2, "crudo": ""},
        {"pagina": 3, "crudo": "42"},
        {"pagina": 1, "crudo": "pagina suelta"},
    ]


# ---------------------------------------------------------------------------
# Importar: cada cuerpo invalido es 422 y no escribe nada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cambios", "quitar"),
    [
        ({}, "colegio_id"),
        ({"colegio_id": "no-es-un-uuid"}, None),
        ({}, "grado"),
        ({"anio_lectivo": "dos mil veintiseis"}, None),
        ({}, "anio_lectivo"),
        ({"items": 7}, None),
        ({}, "items"),
        ({}, "evidencia"),
        ({"evidencia": "texto"}, None),
    ],
)
async def test_importar_con_el_cuerpo_incompleto_es_cuerpo_invalido(cliente, cambios, quitar):
    """Falta un campo, o llega con el tipo equivocado: 422 `cuerpo_invalido` y la cola queda igual."""
    antes = await _total_listas(cliente)
    cuerpo = _cuerpo_importar(**cambios)
    if quitar:
        del cuerpo[quitar]
    respuesta = await cliente.post("/v1/admin/listas/importar", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "cuerpo_invalido"
    assert await _total_listas(cliente) == antes


@pytest.mark.parametrize("evidencia", [{}, {"documento_base64": "###no es base64###"}])
async def test_importar_sin_documento_valido_es_documento_invalido(cliente, evidencia):
    """La evidencia sin PDF o con base64 corrupto se rechaza nombrando el campo, sin eco del contenido."""
    respuesta = await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(evidencia=evidencia))
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "documento_invalido"
    assert cuerpo["campo"] == "documento_base64"
    assert "###" not in respuesta.text


@pytest.mark.parametrize("items", [[{"cantidad": 2}], ["texto suelto"]])
async def test_importar_un_renglon_sin_texto_es_item_invalido(cliente, items):
    """Un renglon sin `texto_original` (o que no es objeto) se rechaza por su posicion, no su contenido."""
    respuesta = await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(items=items))
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "item_invalido"
    assert cuerpo["campo"] == "texto_original"
    assert "posicion 0" in cuerpo["mensaje"]


@pytest.mark.parametrize("cantidad", [0, -3])
async def test_importar_una_cantidad_no_positiva_es_cantidad_invalida(cliente, cantidad):
    """Cero o negativa: 422 `cantidad_invalida`, y el renglon valido que iba antes tampoco se escribe.

    Se validan TODOS los renglones antes de escribir nada; si no, una lista a
    medias quedaria en la cola de revision.
    """
    antes = await _total_listas(cliente)
    items = [
        {"texto_original": "Estudiante Ficticio Uno cuaderno", "cantidad": 1},
        {"texto_original": "lapices", "cantidad": cantidad},
    ]
    respuesta = await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(items=items))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "cantidad_invalida"
    assert respuesta.json()["campo"] == "cantidad"
    assert "Estudiante Ficticio" not in respuesta.text
    assert await _total_listas(cliente) == antes


async def test_importar_sin_cantidad_vale_uno_y_un_numero_en_texto_se_convierte(cliente):
    """La cantidad ausente (o nula) es 1; "4" llega a 4. Lo guardado es lo que se pidio."""
    items = [
        {"texto_original": "borrador"},
        {"texto_original": "tajalapiz", "cantidad": None},
        {"texto_original": "resma", "cantidad": "4"},
    ]
    respuesta = await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(items=items))
    assert respuesta.status_code == 201
    vid = respuesta.json()["version_id"]
    cantidades = {
        i["texto_original"]: i["cantidad"]
        for i in (await cliente.get(f"/v1/admin/listas/{vid}/revision")).json()["items"]
    }
    assert cantidades == {"borrador": 1, "tajalapiz": 1, "resma": 4}


@pytest.mark.xfail(
    strict=True,
    reason="H-A-07: importar hace int(cantidad) sin proteger (routers/admin.py:473): "
    "una cantidad no numerica es 500 en vez de 422",
)
async def test_importar_una_cantidad_no_numerica_es_422(cliente):
    """Un `cantidad` como "muchos" es un error del cliente: debe ser 422, no un 500 sin sobre."""
    items = [{"texto_original": "cuadernos", "cantidad": "muchos"}]
    respuesta = await cliente.post("/v1/admin/listas/importar", json=_cuerpo_importar(items=items))
    assert respuesta.status_code == 422


# ---------------------------------------------------------------------------
# Sugerencias de un padre
# ---------------------------------------------------------------------------


def _cuerpo_sugerencia(**cambios) -> dict:
    cuerpo = {"colegio_id": str(COLEGIO), "grado": "Tercero", "anio_lectivo": 2026}
    cuerpo.update(cambios)
    return cuerpo


@pytest.mark.parametrize(
    ("cambios", "error", "campo"),
    [
        ({"anio_lectivo": "reciente"}, "cuerpo_invalido", None),
        ({"colegio_id": "no-uuid"}, "cuerpo_invalido", None),
        ({"contacto_referencia": "no-uuid"}, "contacto_invalido", "contacto_referencia"),
        ({"evidencia": {"documento_base64": "%%%"}}, "documento_invalido", "documento_base64"),
    ],
)
async def test_una_sugerencia_invalida_es_422_y_no_se_encola(cliente, cambios, error, campo):
    """Cada defecto del cuerpo tiene su codigo; el backlog del administrador no recibe nada."""
    respuesta = await cliente.post("/v1/admin/sugerencias", json=_cuerpo_sugerencia(**cambios))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == error
    assert respuesta.json().get("campo") == campo
    assert (await cliente.get("/v1/admin/sugerencias")).json() == {"sugerencias": []}


async def test_una_sugerencia_sin_la_clave_grado_es_cuerpo_invalido(cliente):
    """La clave `grado` ausente (no solo nula) tambien es 422 `cuerpo_invalido`."""
    cuerpo = _cuerpo_sugerencia()
    del cuerpo["grado"]
    respuesta = await cliente.post("/v1/admin/sugerencias", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "cuerpo_invalido"


# ---------------------------------------------------------------------------
# Editar, agregar y quitar renglones
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("unidad", "docena"), ("tipo_item", "regalo"), ("modo_adquisicion", "trueque")],
)
async def test_editar_con_un_valor_fuera_del_vocabulario_es_422_con_su_campo(cliente, campo, valor):
    """Un valor que los CHECK del modelo rechazarian se dice antes: 422 `<campo>_invalido`, no 500."""
    ids = cliente.ids
    respuesta = await cliente.patch(
        f"/v1/admin/listas/{ids['abierta']}/items/{ids['resuelto']}", json={campo: valor}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == f"{campo}_invalido"
    assert respuesta.json()["campo"] == campo
    assert getattr(await _item(cliente, ids["resuelto"]), campo) != valor


async def test_editar_persiste_cada_campo_permitido(cliente):
    """Unidad, tipo, modo, instruccion, url y atributos se guardan tal cual; lo demas no se toca."""
    ids = cliente.ids
    await _cuaderno_filtra_por(cliente, ["rayado"])
    respuesta = await cliente.patch(
        f"/v1/admin/listas/{ids['abierta']}/items/{ids['resuelto']}",
        json={
            "unidad": "hoja",
            "tipo_item": "texto",
            "modo_adquisicion": "venta_directa_editorial",
            "instruccion_colegio": "Se compra en la papeleria del colegio.",
            "url_externa": "https://colegio.example.test/papeleria",
            "atributos": {"rayado": "liso"},
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {"item_id": str(ids["resuelto"]), "actualizado": True}
    fila = await _item(cliente, ids["resuelto"])
    assert (fila.unidad, fila.tipo_item, fila.modo_adquisicion) == (
        "hoja",
        "texto",
        "venta_directa_editorial",
    )
    assert fila.instruccion_colegio == "Se compra en la papeleria del colegio."
    assert fila.url_externa == "https://colegio.example.test/papeleria"
    assert fila.atributos == {"rayado": "liso"}
    assert (fila.texto_original, fila.cantidad) == ("2 cuadernos", 2)


async def test_editar_atributos_nulos_los_deja_vacios(cliente):
    """`atributos: null` es "sin atributos" ({}), no un error ni un NULL que rompa la lectura."""
    ids = cliente.ids
    await _cuaderno_filtra_por(cliente, ["rayado"])
    ruta = f"/v1/admin/listas/{ids['abierta']}/items/{ids['resuelto']}"
    assert (await cliente.patch(ruta, json={"atributos": {"rayado": "liso"}})).status_code == 200
    assert (await cliente.patch(ruta, json={"atributos": None})).status_code == 200
    assert (await _item(cliente, ids["resuelto"])).atributos == {}


async def test_asignar_un_concepto_a_un_renglon_sin_concepto_lo_resuelve(cliente):
    """El revisor resuelve un renglon: `concepto_codigo` lo liga y `requiere_revision=false` lo libera."""
    ids = cliente.ids
    respuesta = await cliente.patch(
        f"/v1/admin/listas/{ids['abierta']}/items/{ids['sin_concepto']}",
        json={"concepto_codigo": "C002", "requiere_revision": False},
    )
    assert respuesta.status_code == 200
    revision = (await cliente.get(f"/v1/admin/listas/{ids['abierta']}/revision")).json()
    renglon = next(i for i in revision["items"] if i["item_id"] == str(ids["sin_concepto"]))
    assert renglon["concepto"] == {"codigo": "C002", "nombre": "colores"}
    assert renglon["requiere_revision"] is False


async def test_un_concepto_que_no_existe_es_422_y_no_cambia_el_renglon(cliente):
    """Un codigo de concepto inventado se rechaza nombrando `concepto_codigo`."""
    ids = cliente.ids
    respuesta = await cliente.patch(
        f"/v1/admin/listas/{ids['abierta']}/items/{ids['resuelto']}", json={"concepto_codigo": "C999"}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "concepto_no_existe"
    assert respuesta.json()["campo"] == "concepto_codigo"
    assert (await _item(cliente, ids["resuelto"])).concepto_id is not None


async def test_editar_una_cantidad_cero_es_cantidad_invalida(cliente):
    """La cantidad de un renglon editado tambien tiene que ser mayor que cero."""
    ids = cliente.ids
    respuesta = await cliente.patch(
        f"/v1/admin/listas/{ids['abierta']}/items/{ids['resuelto']}", json={"cantidad": 0}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "cantidad_invalida"
    assert (await _item(cliente, ids["resuelto"])).cantidad == 2


@pytest.mark.parametrize(
    "cuerpo",
    [
        pytest.param(
            {"cantidad": "muchos"},
            marks=pytest.mark.xfail(
                strict=True,
                reason="H-A-07: _valores_de_renglon hace int(cantidad) sin proteger "
                "(routers/admin.py:714): cantidad no numerica es 500 en vez de 422",
            ),
            id="cantidad-no-numerica",
        ),
        pytest.param(
            {"unidad": ["hoja"]},
            marks=pytest.mark.xfail(
                strict=True,
                reason="H-A-07: `valor not in permitidos` con un valor no hashable "
                "(routers/admin.py:730) lanza TypeError: 500 en vez de 422",
            ),
            id="unidad-no-hashable",
        ),
        # H-A-07 en `atributos` quedo corregido en `b12973e` (routers/admin.py:1152-1160,
        # 422 si no es un mapa de valores simples): salia XPASS(strict) en la corrida oe5.
        pytest.param({"atributos": [1, 2]}, id="atributos-no-objeto"),
    ],
)
async def test_editar_con_tipos_equivocados_es_422_y_no_500(cliente, cuerpo):
    """El cliente mando el tipo equivocado: el contrato del router es 422 con causa, nunca un 500."""
    ids = cliente.ids
    respuesta = await cliente.patch(f"/v1/admin/listas/{ids['abierta']}/items/{ids['resuelto']}", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]


async def test_editar_un_renglon_que_no_es_de_la_version_es_404(cliente):
    """El renglon se busca DENTRO de la version de la URL: uno ajeno o inexistente es `item_no_existe`."""
    ids = cliente.ids
    ajeno = (
        await cliente.patch(f"/v1/admin/listas/{ids['abierta']}/items/{INEXISTENTE}", json={"cantidad": 3})
    ).json()
    assert ajeno["error"] == "item_no_existe"
    quitar = await cliente.delete(f"/v1/admin/listas/{ids['abierta']}/items/{INEXISTENTE}")
    assert quitar.status_code == 404
    assert quitar.json()["error"] == "item_no_existe"


async def test_agregar_un_renglon_sin_texto_es_texto_requerido(cliente):
    """Un renglon nuevo sin `texto_original` no tiene que quedar a medias."""
    respuesta = await cliente.post(f"/v1/admin/listas/{cliente.ids['abierta']}/items", json={"cantidad": 2})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "texto_requerido"
    assert respuesta.json()["campo"] == "texto_original"


async def test_agregar_un_renglon_no_surtible_exige_instruccion(cliente):
    """Lo que Tukit no surte (venta directa del colegio) tiene que decir como conseguirlo."""
    await _cuaderno_filtra_por(cliente, ["formato"])
    ruta = f"/v1/admin/listas/{cliente.ids['abierta']}/items"
    sin = await cliente.post(
        ruta, json={"texto_original": "agenda", "concepto_codigo": "C001", "modo_adquisicion": "plataforma"}
    )
    assert sin.status_code == 422
    assert sin.json()["error"] == "no_surtible_sin_instruccion"

    con = await cliente.post(
        ruta,
        json={
            "texto_original": "agenda",
            "concepto_codigo": "C001",
            "modo_adquisicion": "plataforma",
            "instruccion_colegio": "Se paga en la plataforma del colegio.",
            "atributos": {"formato": "digital"},
        },
    )
    assert con.status_code == 201
    assert con.json()["orden"] == 3
    fila = await _item(cliente, uuid.UUID(con.json()["item_id"]))
    assert fila.modo_adquisicion == "plataforma"
    assert fila.atributos == {"formato": "digital"}
    assert fila.requiere_revision is False


# ---------------------------------------------------------------------------
# Datos del colegio, propuestas, cerrar y nueva version
# ---------------------------------------------------------------------------


async def test_completar_el_colegio_ignora_los_campos_fuera_de_la_lista_blanca(cliente):
    """`dane` define el `colegio_id` derivado: el revisor no puede reescribirlo, solo completar el perfil."""
    importada = await cliente.post(
        "/v1/admin/listas/importar",
        json=_cuerpo_importar(colegio_datos={"nombre": "Colegio San Ejemplo", "dane": "111001000001"}),
    )
    vid = importada.json()["version_id"]
    respuesta = await cliente.patch(
        f"/v1/admin/listas/{vid}/colegio",
        json={"direccion": "Calle Ficticia 1", "dane": "999", "colegio_id": str(INEXISTENTE)},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["colegio_datos"] == {
        "nombre": "Colegio San Ejemplo",
        "dane": "111001000001",
        "direccion": "Calle Ficticia 1",
    }


async def test_rechazar_una_propuesta_pendiente_guarda_estado_y_motivo(cliente):
    """El rechazo corriente deja la propuesta `rechazada` con el motivo que dio el revisor."""
    ids = cliente.ids
    respuesta = await cliente.post(
        f"/v1/admin/propuestas/{ids['pendiente']}/rechazar", json={"motivo": "no es"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": str(ids["pendiente"]), "estado": "rechazada"}
    async with cliente.fabrica() as sesion:
        fila = await sesion.get(PropuestaProducto, ids["pendiente"])
    assert fila.estado == "rechazada"
    # Con la unica pendiente rechazada, la version ya puede cerrarse.
    cierre = await cliente.post(f"/v1/admin/listas/{ids['abierta']}/cerrar")
    assert cierre.status_code == 200
    assert cierre.json() == {"version_id": str(ids["abierta"]), "revisada": True, "avisos_cerrados": 1}


async def test_rechazar_sin_cuerpo_tambien_funciona(cliente):
    """El motivo es opcional: un POST sin cuerpo rechaza igual."""
    respuesta = await cliente.post(f"/v1/admin/propuestas/{cliente.ids['pendiente']}/rechazar")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "rechazada"


async def test_rechazar_una_propuesta_que_no_existe_es_404(cliente):
    """Un identificador sin propuesta es `propuesta_no_existe`."""
    respuesta = await cliente.post(f"/v1/admin/propuestas/{INEXISTENTE}/rechazar")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "propuesta_no_existe"


async def test_rechazar_una_propuesta_ya_resuelta_es_409(cliente):
    """Una propuesta que ya no esta pendiente no se decide dos veces."""
    respuesta = await cliente.post(f"/v1/admin/propuestas/{cliente.ids['rechazada']}/rechazar")
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "propuesta_ya_resuelta"
    assert "rechazada" in respuesta.json()["mensaje"]


async def test_cerrar_una_version_que_no_existe_es_404(cliente):
    """Cerrar un identificador sin version es `version_no_existe` y no emite nada."""
    respuesta = await cliente.post(f"/v1/admin/listas/{INEXISTENTE}/cerrar")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "version_no_existe"


async def test_nueva_version_de_una_lista_inexistente_es_404(cliente):
    """Sin lista para ese (colegio, grado, ano) no hay de donde clonar: `lista_no_existe`."""
    respuesta = await cliente.post(
        f"/v1/admin/listas/{COLEGIO}/Undecimo/nueva-version", params={"anio_lectivo": 2026}
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "lista_no_existe"


async def test_nueva_version_sin_version_vigente_es_404(cliente):
    """Una lista cuya version no esta vigente no se clona: `version_no_existe`."""
    respuesta = await cliente.post(
        f"/v1/admin/listas/{COLEGIO}/Septimo/nueva-version", params={"anio_lectivo": 2026}
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "version_no_existe"


async def test_nueva_version_con_un_ano_fuera_de_rango_es_entrada_invalida(cliente):
    """El ano lectivo se acota en la firma (2020-2100): fuera de rango es 400 `entrada_invalida`."""
    respuesta = await cliente.post(
        f"/v1/admin/listas/{COLEGIO}/Quinto/nueva-version", params={"anio_lectivo": 1999}
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "entrada_invalida"


async def test_la_ruta_rapida_de_una_lista_solo_informativa_no_trae_candidatos(cliente):
    """Si ningun renglon tiene concepto no hay que consultar productos: los candidatos van vacios."""
    cuerpo = (await cliente.get(f"/v1/admin/listas/{cliente.ids['informativa']}/resueltos")).json()
    assert [i["texto_original"] for i in cuerpo["items"]] == ["Agenda institucional", "Carnet estudiantil"]
    assert all(i["candidatos"] == [] and i["concepto_codigo"] is None for i in cuerpo["items"])
    assert all(i["modo_adquisicion"] == "venta_directa_editorial" for i in cuerpo["items"])


# ---------------------------------------------------------------------------
# Curaduria: conceptos, util, libro y aprobacion
# ---------------------------------------------------------------------------


async def test_crear_un_concepto_con_un_tipo_de_item_desconocido_es_422(cliente):
    """El tipo del concepto sale del vocabulario cerrado `TipoItem`."""
    respuesta = await cliente.post(
        "/v1/admin/catalogo/conceptos",
        json={"nombre_canonico": "pegante", "categoria": "Arte", "tipo_item": "regalo"},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "tipo_item_invalido"
    assert respuesta.json()["campo"] == "tipo_item"


async def test_crear_un_concepto_limpia_los_sinonimos_que_llegan_como_lista(cliente):
    """Los sinonimos en lista se recortan y los vacios se descartan; el codigo es el siguiente libre."""
    respuesta = await cliente.post(
        "/v1/admin/catalogo/conceptos",
        json={"nombre": "Pegante", "categoria": "Arte", "sinonimos": [" colbon ", "", "goma"]},
    )
    assert respuesta.status_code == 201
    # Desde d37c235 el alta devuelve tambien los dos papeles de atributo
    # (routers/admin.py:1605-1611); sin pedirlos, las dos listas van vacias.
    assert respuesta.json() == {
        "codigo": "C003",
        "nombre_canonico": "Pegante",
        "categoria": "Arte",
        "tipo_item": "util",
        "atributos_discriminantes": [],
        "atributos_descriptivos": [],
    }
    sinonimos = Base.metadata.tables["concepto"].c.sinonimos
    codigo = Base.metadata.tables["concepto"].c.codigo
    async with cliente.fabrica() as sesion:
        guardados = (await sesion.execute(select(sinonimos).where(codigo == "C003"))).scalar_one()
    assert list(guardados) == ["colbon", "goma"]


def _oferta(tienda: str, sku: str):
    from tukit_catalogo import tiendas

    return tiendas.Oferta(
        tienda=tienda,
        nombre="Cuaderno ficticio",
        precio_cop=5000,
        disponible=True,
        imagen_url=None,
        url="",
        sku=sku,
        ean=None,
        marca=None,
        especificaciones={},
    )


async def test_encolar_un_util_que_ya_no_aparece_en_la_tienda_es_422(cliente, monkeypatch):
    """Si el candidato se agoto entre la busqueda y el alta, es `candidato_no_disponible`, no un 500."""
    from tukit_catalogo import tiendas

    # Desde 4dfdd99 el alta re-busca con `tiendas.buscar` (una tienda, sin el filtro
    # de palabras; routers/admin.py:1664), no con `admin.buscar_candidatos`: sin
    # este doble la prueba salia a la red de la tienda.
    monkeypatch.setattr(tiendas, "buscar", lambda slug, consulta, cuantos=24: [_oferta(slug, "OTRO")])
    respuesta = await cliente.post(
        "/v1/admin/catalogo/propuestas/util",
        json={"concepto": "C001", "slug": "exito", "sku": "S-AGOTADO", "consulta": "cuaderno"},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "candidato_no_disponible"
    assert respuesta.json()["campo"] == "sku"


async def test_encolar_un_util_de_una_tienda_que_no_esta_en_la_bd_es_422(cliente, monkeypatch):
    """La busqueda en vivo puede traer una tienda que la BD no registra: `tienda_desconocida`."""
    from tukit_catalogo import tiendas

    # El doble va en `tiendas.buscar`, que es lo que el alta consulta desde 4dfdd99
    # (routers/admin.py:1664); la tienda se busca en la BD despues (:1683-1688).
    monkeypatch.setattr(tiendas, "buscar", lambda slug, consulta, cuantos=24: [_oferta(slug, "S1")])
    respuesta = await cliente.post(
        "/v1/admin/catalogo/propuestas/util",
        json={"concepto": "C001", "slug": "mercadolibre", "sku": "S1", "consulta": "cuaderno"},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "tienda_desconocida"
    assert respuesta.json()["campo"] == "slug"


@pytest.mark.parametrize("ruta", ["util-manual", "libro"])
@pytest.mark.parametrize("precio", [[4200], "mucho", None, -5])
async def test_un_precio_que_no_es_un_entero_positivo_es_precio_invalido(cliente, ruta, precio):
    """El precio se lee en pesos enteros: una lista, un texto, nada o un negativo son `precio_invalido`."""
    cuerpo = {
        "concepto": "C001",
        "nombre": "Cuaderno artesanal",
        "isbn": "9781234567897",
        "titulo": "Libro Ficticio",
        "precio": precio,
        "slug": "exito",
    }
    respuesta = await cliente.post(f"/v1/admin/catalogo/propuestas/{ruta}", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_invalido"
    assert respuesta.json()["campo"] == "precio"


async def test_encolar_un_libro_sin_tienda_usa_panamericana_y_si_no_existe_es_422(cliente):
    """Sin `slug` el libro va a panamericana; en una BD que no la tiene, `tienda_desconocida`."""
    respuesta = await cliente.post(
        "/v1/admin/catalogo/propuestas/libro",
        json={"concepto": "C001", "isbn": "9781234567897", "titulo": "Libro Ficticio", "precio": 30000},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "tienda_desconocida"
    assert "panamericana" in respuesta.json()["mensaje"]


async def test_aprobar_reenvia_nombre_y_limpia_los_textos_vacios(cliente, monkeypatch):
    """Las correcciones a mano viajan a `resolver`: el nombre se reenvia, un texto vacio es "sin dato" (None).

    Un nombre en blanco NO se reenvia, para que `resolver` conserve el
    automatico de la propuesta.
    """
    recibido = {}

    async def _falso_resolver(id_corto, aprobar, nivel, motivo, no_surtir=False, overrides=None):
        recibido.update(id_corto=id_corto, nivel=nivel, overrides=overrides)
        return 0

    monkeypatch.setattr(descubrir, "resolver", _falso_resolver)
    prop = cliente.ids["pendiente"]
    cuerpo = {
        "nivel": "premium",
        "nombre": "Cuaderno corregido",
        "marca": "   ",
        "personaje": "Personaje Ficticio",
        "imagen_url": None,
        "atributos": {"rayado": "liso"},
    }
    respuesta = await cliente.post(f"/v1/admin/catalogo/propuestas/{prop}/aprobar", json=cuerpo)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": str(prop), "estado": "aprobada"}
    assert recibido["id_corto"] == str(prop)[:8]
    assert recibido["nivel"] == "premium"
    assert recibido["overrides"] == {
        "nombre": "Cuaderno corregido",
        "marca": None,
        "personaje": "Personaje Ficticio",
        "imagen_url": None,
        "atributos": {"rayado": "liso"},
    }

    await cliente.post(f"/v1/admin/catalogo/propuestas/{prop}/aprobar", json={"nombre": "   "})
    assert recibido["overrides"] is None
