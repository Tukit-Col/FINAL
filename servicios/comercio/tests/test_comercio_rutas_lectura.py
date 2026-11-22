"""NFR-MAN-01: las rutas de lectura de Comercio: tablero, historial del acudiente, detalle y cruce interno.

Son la cara que ven el back-office de logistica y el panel del acudiente (CONTRATO_API §9). Lo que
se defiende es lo que, si falla, miente en pantalla o filtra de mas:

- El tablero consolida por estado, suma ingresos SOLO de lo ya pagado y cuenta las entregas pendientes
  (lo cancelado y lo pendiente de pago no son ingreso), con el pedido mas reciente primero.
- Cada pedido trae lineas, el ULTIMO intento de pago y el envio; un pedido sin pago o sin envio los
  muestra en `null`, no revienta.
- `mis-pedidos` separa a un acudiente de otro por la SESION (e82d03c: el `usuario_id` del
  navegador se ignora) y devuelve vacio, no error, si no hay.
- `pedidos-pagados` entrega solo identificadores (sin PII) y solo de pedidos confirmados con trabajo.
- Una entrada mal formada es `400 entrada_invalida` y el sobre nunca repite lo que se envio.

Desde e82d03c el tablero y el detalle son solo staff y `mis-pedidos` pide sesion: las lecturas van
con el bearer del operador o del acudiente (`IdentidadFalsa` de `conftest.py`); lo que pasa SIN
credencial lo fija `test_comercio_control_acceso.py`.

Sin red: SQLite en memoria, `PasarelaFalsa` y un Catalogo en memoria. Las fechas se fijan a mano para
que el orden "mas reciente primero" no dependa del reloj.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from conftest import TOKEN_ACUDIENTE, TOKEN_OPERADOR, TOKEN_OTRO, IdentidadFalsa, bearer
from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPedido, Pago
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PEDIDO = Base.metadata.tables["pedido"]
PAGO = Pago.__table__
ENVIO = Base.metadata.tables["envio"]
ACUDIENTE = "22222222-2222-5222-8222-222222222222"
OTRO_ACUDIENTE = "33333333-3333-5333-8333-333333333333"
BASE_TIEMPO = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
STAFF = bearer(TOKEN_OPERADOR)


class CatalogoFalso:
    """Catalogo en memoria: todo sku existe y cuesta lo que diga el mapa (4.500 por omision)."""

    def __init__(self, precios: dict[str, int] | None = None) -> None:
        self.precios = precios or {}

    async def resolver(self, sku: str):
        return uuid.uuid5(uuid.NAMESPACE_OID, sku), self.precios.get(sku, 4500)


@pytest_asyncio.fixture
async def entorno() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    app.state.motor = motor
    app.state.pasarela = PasarelaFalsa()
    app.state.catalogo = CatalogoFalso()
    app.state.identidad = IdentidadFalsa()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor
    await engine.dispose()


def _orden(
    *, usuario: str = ACUDIENTE, cantidad: int = 2, trabajo_id: str | None = None, sku: str = "TK-C001-ECO"
) -> dict:
    cuerpo = {
        "usuario_id": usuario,
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": sku, "nombre": "Cuaderno cuadriculado", "cantidad": cantidad, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }
    if trabajo_id:
        cuerpo["trabajo_id"] = trabajo_id
    return cuerpo


async def _crear(
    http: httpx.AsyncClient, motor: MotorServicio, *, minutos: int, estado: str = "pendiente_pago", **kw
) -> str:
    """Crea una orden por HTTP y fija su fecha (`BASE_TIEMPO + minutos`) y estado en la base."""
    pedido_id = (await http.post("/v1/ordenes", json=_orden(**kw))).json()["pedido_id"]
    async with motor.sesion() as db:
        await db.execute(
            update(PEDIDO)
            .where(PEDIDO.c.id == uuid.UUID(pedido_id))
            .values(creado_en=BASE_TIEMPO + timedelta(minutes=minutos), estado=estado)
        )
    return pedido_id


# --- tablero ------------------------------------------------------------------------------------


async def test_tablero_vacio_trae_el_resumen_en_ceros_con_todos_los_estados(entorno):
    """Sin pedidos el tablero no es un error: ceros en cada uno de los ocho estados y lista vacia."""
    http, _ = entorno

    respuesta = await http.get("/v1/comercio/pedidos", headers=STAFF)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "resumen": {
            "pedidos_totales": 0,
            "por_estado": {estado.value: 0 for estado in EstadoPedido},
            "ingresos_confirmados": 0,
            "entregas_pendientes": 0,
            "alertas": {"incidencia_abierta": 0, "pagado_sin_avanzar": 0, "pago_atascado": 0},
        },
        "pedidos": [],
    }


async def test_tablero_cuenta_ingresos_solo_de_lo_confirmado_y_entregas_pendientes_del_camino(entorno):
    """Seis pedidos de $9.000 (2 x $4.500), uno por estado.

    Ingreso confirmado = pagado + en_reparto + entregado = $27.000. El pendiente de pago, el cancelado
    y la incidencia NO son ingreso. Entrega pendiente = pagado + en_reparto (el entregado ya llego)."""
    http, motor = entorno
    for minutos, estado in enumerate(
        ["pendiente_pago", "pagado", "en_reparto", "entregado", "cancelado", "incidencia"]
    ):
        await _crear(http, motor, minutos=minutos, estado=estado)

    cuerpo = (await http.get("/v1/comercio/pedidos", headers=STAFF)).json()

    assert cuerpo["resumen"] == {
        "pedidos_totales": 6,
        "por_estado": {
            "pendiente_pago": 1,
            "pagado": 1,
            "en_preparacion": 0,
            "despachado": 0,
            "en_reparto": 1,
            "entregado": 1,
            "incidencia": 1,
            "cancelado": 1,
        },
        "ingresos_confirmados": 27_000,
        "entregas_pendientes": 2,
        "alertas": {"incidencia_abierta": 1, "pagado_sin_avanzar": 1, "pago_atascado": 0},
    }
    assert len(cuerpo["pedidos"]) == 6


async def test_tablero_lista_primero_el_pedido_mas_reciente_con_lineas_y_envio_anidados(entorno):
    http, motor = entorno
    viejo = await _crear(http, motor, minutos=0)
    medio = await _crear(http, motor, minutos=10, cantidad=3)
    nuevo = await _crear(http, motor, minutos=20)

    pedidos = (await http.get("/v1/comercio/pedidos", headers=STAFF)).json()["pedidos"]

    assert [p["pedido_id"] for p in pedidos] == [nuevo, medio, viejo]
    del_medio = pedidos[1]
    assert del_medio["total"] == 13_500  # 3 x 4.500
    assert del_medio["lineas"] == [
        {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 3, "precio_unitario": 4500}
    ]
    assert del_medio["envio"]["destinatario"] == "Acudiente Ficticio"
    assert del_medio["envio"]["ciudad"] == "Bogota"
    assert del_medio["envio"]["guia"] is None
    assert del_medio["pago"] is None  # todavia no se inicio el cobro: `null`, no un error
    assert del_medio["creado_en"].startswith("2026-03-01T12:10:00")


async def test_tablero_muestra_el_ultimo_intento_de_pago_de_cada_pedido(entorno):
    """Con dos intentos (el primero rechazado) el tablero y el detalle muestran el mas reciente; el
    del tablero se arma en lote (sin N+1) y debe coincidir con el del detalle de un solo pedido."""
    http, motor = entorno
    pedido_id = await _crear(http, motor, minutos=0)
    for referencia, estado, minuto in (("ref-vieja", "rechazado", 1), ("ref-nueva", "iniciado", 2)):
        async with motor.sesion() as db:
            await db.execute(
                insert(PAGO).values(
                    id=uuid.uuid4(),
                    pedido_id=uuid.UUID(pedido_id),
                    referencia_wompi=referencia,
                    transaccion_wompi=None,
                    metodo="pse",
                    estado=estado,
                    monto=9000,
                    creado_en=BASE_TIEMPO + timedelta(minutes=minuto),
                )
            )

    en_tablero = (await http.get("/v1/comercio/pedidos", headers=STAFF)).json()["pedidos"][0]["pago"]
    en_detalle = (await http.get(f"/v1/comercio/pedidos/{pedido_id}", headers=STAFF)).json()["pago"]

    esperado = {"referencia_wompi": "ref-nueva", "metodo": "pse", "estado": "iniciado", "monto": 9000}
    assert en_tablero == esperado
    # 669e914: el detalle agrega lo que solo ve el staff del ultimo intento (`datos_de_pago_staff`).
    assert {k: en_detalle[k] for k in esperado} == esperado
    assert en_detalle["transaccion_wompi"] is None  # sigue `iniciado`


# --- detalle de un pedido -----------------------------------------------------------------------


async def test_detalle_de_un_pedido_trae_la_forma_completa_del_contrato(entorno):
    http, motor = entorno
    trabajo = str(uuid.uuid4())
    pedido_id = await _crear(http, motor, minutos=0, trabajo_id=trabajo)

    respuesta = await http.get(f"/v1/comercio/pedidos/{pedido_id}", headers=STAFF)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # e82d03c agrega el dueno (`usuario_id`), el `historial` de avances y, en el envio, el
    # repartidor; el celular del repartidor sale solo en este detalle del staff. Desde oe5 (cef2c25)
    # trae tambien las `devoluciones` (los retractos con su plazo de la Ley 1480).
    assert set(cuerpo) == {
        "pedido_id",
        "usuario_id",
        "trabajo_id",
        "estado",
        "creado_en",
        "total",
        "hijos",
        "colegios",
        "lineas",
        "pago",
        "envio",
        "historial",
        "devoluciones",
    }
    assert (cuerpo["historial"], cuerpo["devoluciones"]) == ([], [])
    assert cuerpo["trabajo_id"] == trabajo
    assert cuerpo["estado"] == "pendiente_pago"
    assert (cuerpo["total"], cuerpo["hijos"], cuerpo["colegios"]) == (9000, 1, ["Colegio Ficticio"])
    # La localidad y el lugar de Google llegan con ADR 0044 (77bb105, ya en `main`); la latitud y la
    # longitud del pin de OpenStreetMap, con ADR 0049 (oe5, 64d17c6). Sin pin van nulas (N-149).
    assert set(cuerpo["envio"]) == {
        "destinatario",
        "direccion",
        "ciudad",
        "telefono",
        "departamento",
        "documento_destinatario",
        "indicaciones",
        "localidad",
        "latitud",
        "longitud",
        "transportadora",
        "guia",
        "repartidor_nombre",
        "repartidor_celular",
        "entrega_estimada",
        "entregado_en",
    }
    assert (cuerpo["envio"]["latitud"], cuerpo["envio"]["longitud"]) == (None, None)


async def test_el_seguimiento_del_acudiente_y_el_detalle_de_logistica_son_la_misma_vista(entorno):
    """`GET /v1/ordenes/{id}` reusa el serializador del detalle: dos formas distintas serian dos
    verdades. Desde e82d03c el detalle del staff agrega SOLO el `historial` y el celular del
    repartidor (dato de un tercero que el acudiente no necesita), y desde oe5 (cef2c25) las
    `devoluciones` (el motivo del retracto es texto libre, solo del staff); todo lo demas coincide."""
    http, motor = entorno
    pedido_id = await _crear(http, motor, minutos=0)

    del_acudiente = (await http.get(f"/v1/ordenes/{pedido_id}")).json()
    de_logistica = (await http.get(f"/v1/comercio/pedidos/{pedido_id}", headers=STAFF)).json()

    historial = de_logistica.pop("historial")
    devoluciones = de_logistica.pop("devoluciones")
    celular = de_logistica["envio"].pop("repartidor_celular")
    assert (historial, devoluciones, celular) == ([], [], None)
    assert del_acudiente == de_logistica


@pytest.mark.parametrize("ruta", ["/v1/comercio/pedidos/{}", "/v1/ordenes/{}"])
async def test_un_pedido_que_no_existe_es_404_con_el_sobre_del_contrato(entorno, ruta):
    http, _ = entorno

    respuesta = await http.get(ruta.format(uuid.uuid4()), headers=STAFF)

    assert respuesta.status_code == 404
    assert respuesta.json() == {
        "error": "pedido_no_existe",
        "mensaje": "No hay ningun pedido con ese identificador.",
    }


async def test_un_identificador_mal_formado_es_400_y_no_se_repite_en_la_respuesta(entorno):
    """El sobre dice DONDE fallo (`pedido_id`), nunca QUE se envio: nada de eco de la entrada."""
    http, _ = entorno

    respuesta = await http.get("/v1/comercio/pedidos/no-es-un-uuid-ficticio")

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "entrada_invalida"
    assert cuerpo["campo"] == "pedido_id"
    assert "no-es-un-uuid-ficticio" not in respuesta.text


async def test_un_pedido_sin_envio_se_muestra_con_envio_nulo_en_detalle_y_tablero(entorno):
    """Un pedido cuya fila de envio no existe (dato legado o purgado) no revienta ni al detalle ni al
    tablero: `envio` es `null` y el resto del pedido se sigue mostrando."""
    http, motor = entorno
    pedido_id = await _crear(http, motor, minutos=0)
    async with motor.sesion() as db:
        await db.execute(delete(ENVIO).where(ENVIO.c.pedido_id == uuid.UUID(pedido_id)))

    detalle = await http.get(f"/v1/comercio/pedidos/{pedido_id}", headers=STAFF)
    tablero = (await http.get("/v1/comercio/pedidos", headers=STAFF)).json()["pedidos"]

    assert detalle.status_code == 200
    assert detalle.json()["envio"] is None
    assert detalle.json()["total"] == 9000
    assert [(p["pedido_id"], p["envio"]) for p in tablero] == [(pedido_id, None)]


# --- historial del acudiente --------------------------------------------------------------------


async def test_mis_pedidos_separa_acudientes_y_ordena_del_mas_reciente_al_mas_viejo(entorno):
    """El acudiente sale de la sesion (e82d03c); un `?usuario_id=` ajeno se ignora."""
    http, motor = entorno
    primero = await _crear(http, motor, minutos=0)
    ajeno = await _crear(http, motor, minutos=5, usuario=OTRO_ACUDIENTE)
    segundo = await _crear(http, motor, minutos=10)

    mios = (
        await http.get(
            "/v1/comercio/mis-pedidos",
            params={"usuario_id": OTRO_ACUDIENTE},
            headers=bearer(TOKEN_ACUDIENTE),
        )
    ).json()
    suyos = (await http.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_OTRO))).json()

    assert mios["total"] == 2
    assert [p["pedido_id"] for p in mios["pedidos"]] == [segundo, primero]
    assert [p["pedido_id"] for p in suyos["pedidos"]] == [ajeno]
    assert suyos["total"] == 1


async def test_mis_pedidos_de_quien_no_ha_comprado_es_lista_vacia_y_no_error(entorno):
    http, motor = entorno
    await _crear(http, motor, minutos=0, usuario=OTRO_ACUDIENTE)

    respuesta = await http.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_ACUDIENTE))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 0, "pedidos": []}


@pytest.mark.parametrize(
    "params", [{}, {"usuario_id": "acudiente-ficticio"}], ids=["sin_usuario", "mal_formado"]
)
async def test_mis_pedidos_sin_sesion_es_401_y_el_usuario_del_navegador_no_cuenta(entorno, params):
    """Antes de e82d03c el `usuario_id` venia en la query y faltar o venir mal era `400`. Ahora sale
    de la sesion: sin bearer es `401 sesion_invalida` (sin eco de la entrada) y, con bearer, un
    `usuario_id` mal formado en la query se ignora."""
    http, _ = entorno

    sin_sesion = await http.get("/v1/comercio/mis-pedidos", params=params)
    con_sesion = await http.get("/v1/comercio/mis-pedidos", params=params, headers=bearer(TOKEN_ACUDIENTE))

    assert sin_sesion.status_code == 401
    assert sin_sesion.json() == {"error": "sesion_invalida", "mensaje": "El token no es valido o expiro."}
    assert "acudiente-ficticio" not in sin_sesion.text
    assert (con_sesion.status_code, con_sesion.json()) == (200, {"total": 0, "pedidos": []})


# --- cruce interno: pedidos pagados -------------------------------------------------------------


async def test_pedidos_pagados_devuelve_solo_identificadores_de_pedidos_confirmados_con_trabajo(entorno):
    """Es el cruce server-to-server de Inteligencia: nada de PII (ni direccion, ni totales), y solo
    pedidos en estado confirmado que traen `trabajo_id`."""
    http, motor = entorno
    trabajo_pagado, trabajo_entregado, trabajo_pendiente = (str(uuid.uuid4()) for _ in range(3))
    await _crear(http, motor, minutos=0, estado="pagado", trabajo_id=trabajo_pagado)
    await _crear(
        http, motor, minutos=1, estado="entregado", usuario=OTRO_ACUDIENTE, trabajo_id=trabajo_entregado
    )
    await _crear(http, motor, minutos=2, estado="pendiente_pago", trabajo_id=trabajo_pendiente)
    await _crear(http, motor, minutos=3, estado="cancelado", trabajo_id=str(uuid.uuid4()))
    await _crear(http, motor, minutos=4, estado="pagado")  # confirmado pero sin trabajo

    respuesta = await http.get("/v1/comercio/pedidos-pagados")

    assert respuesta.status_code == 200
    pedidos = respuesta.json()["pedidos"]
    assert sorted(pedidos, key=lambda p: p["trabajo_id"]) == sorted(
        [
            {"trabajo_id": trabajo_pagado, "usuario_id": ACUDIENTE, "estado": "pagado"},
            {"trabajo_id": trabajo_entregado, "usuario_id": OTRO_ACUDIENTE, "estado": "entregado"},
        ],
        key=lambda p: p["trabajo_id"],
    )
    assert all(set(p) == {"trabajo_id", "usuario_id", "estado"} for p in pedidos)
    assert "Calle" not in respuesta.text
    assert "Acudiente Ficticio" not in respuesta.text


async def test_pedidos_pagados_sin_ninguno_es_lista_vacia(entorno):
    http, _ = entorno

    assert (await http.get("/v1/comercio/pedidos-pagados")).json() == {"pedidos": []}
