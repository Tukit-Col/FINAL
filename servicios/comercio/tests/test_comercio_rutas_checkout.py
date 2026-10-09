"""NFR-MAN-01: el checkout de Comercio por HTTP: ramas de rechazo, webhook y avance de entrega.

`test_checkout.py` recorre el camino feliz. Aqui se fijan los caminos que protegen el dinero y el
inventario cuando algo sale distinto (CONTRATO_API §9). Si se rompen, o se cobra de mas o se deja un
pedido a medias:

- `POST /v1/ordenes`: ids mal formados son 422 ANTES de consultar a Catalogo; Catalogo caido es 503
  y un sku desconocido o con precio cambiado es 422, y en ambos casos NO queda pedido ni reserva; un
  solo renglon desactualizado tumba la orden entera; el id canonico lo manda Catalogo, no el cliente.
- `POST /v1/ordenes/{id}/pago`: el monto viaja a la pasarela en centavos y se guarda en pesos; un
  pedido que ya no esta pendiente (pagado, cancelado, entregado) no se vuelve a cobrar; si la
  pasarela cae no queda un pago huerfano y el reintento reutiliza la referencia.
- `POST /v1/webhooks/wompi`: eventos incompletos o de una referencia desconocida no mueven nada pero
  quedan registrados; un segundo aprobado con otro id no duplica el aviso `pedido_pagado`; un aprobado
  sobre un pedido cancelado no lo resucita; la correlacion de la peticion viaja en el aviso.
- `POST /v1/ordenes/{id}/avanzar`: la cadena de entrega solo avanza por transiciones legales, un
  despacho exige transportadora Y guia, y lo sellado en el envio no se pierde al avanzar.

Sin red: SQLite en memoria, `PasarelaFalsa` (que firma como Wompi) y Catalogo en memoria. Los contadores
de metricas se espian para comprobar que se cuentan solo cuando corresponde.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import (
    BandejaSalida,
    Base,
    EstadoPago,
    EstadoPedido,
    EventoPasarelaProcesado,
    LineaPedido,
    Pago,
    Pedido,
    ReservaInventario,
)
from tukit_comercio.pasarela import PasarelaFalsa, TransaccionCreada
from tukit_comercio.remoto import CatalogoCaido
from tukit_comercio.routers import comercio as router_comercio
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PEDIDO = Pedido.__table__
ACUDIENTE = "22222222-2222-5222-8222-222222222222"
CORREO = "acudiente@example.test"


class CatalogoFalso:
    """Catalogo en memoria. Un sku ausente del mapa no existe (`None`); un precio `None` es "sin precio"."""

    def __init__(self, precios: dict[str, int | None] | None = None) -> None:
        self.precios = precios if precios is not None else {"TK-C001-ECO": 4500, "TK-L002-LAP": 1200}
        self.consultas: list[str] = []

    async def resolver(self, sku: str):
        self.consultas.append(sku)
        if sku not in self.precios:
            return None
        return uuid.uuid5(uuid.NAMESPACE_OID, sku), self.precios[sku]


class CatalogoCaidoDoble:
    consultas = 0

    async def resolver(self, sku: str):
        type(self).consultas += 1
        raise CatalogoCaido("catalogo sin respuesta")


class PasarelaEspia(PasarelaFalsa):
    """La falsa, anotando exactamente con que argumentos se le pidio cobrar."""

    def __init__(self) -> None:
        super().__init__()
        self.llamadas: list[dict[str, Any]] = []

    async def crear_transaccion(self, **kwargs: Any) -> TransaccionCreada:
        self.llamadas.append(kwargs)
        return await super().crear_transaccion(**kwargs)


class PasarelaIntermitente(PasarelaEspia):
    """Wompi caido las primeras `fallos` veces y sano despues."""

    def __init__(self, fallos: int) -> None:
        super().__init__()
        self.fallos = fallos

    async def crear_transaccion(self, **kwargs: Any) -> TransaccionCreada:
        if self.fallos > 0:
            self.fallos -= 1
            self.llamadas.append(kwargs)
            raise httpx.ConnectError("wompi no responde")
        return await super().crear_transaccion(**kwargs)


@pytest_asyncio.fixture
async def entorno() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio, PasarelaEspia]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    app.state.motor = motor
    app.state.pasarela = PasarelaEspia()
    app.state.catalogo = CatalogoFalso()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor, app.state.pasarela
    await engine.dispose()


@pytest.fixture
def metricas(monkeypatch) -> dict[str, int]:
    cuenta = {"ordenes": 0, "pagos": 0}
    monkeypatch.setattr(
        router_comercio, "contar_orden_creada", lambda: cuenta.update(ordenes=cuenta["ordenes"] + 1)
    )
    monkeypatch.setattr(
        router_comercio, "contar_pago_aprobado", lambda: cuenta.update(pagos=cuenta["pagos"] + 1)
    )
    return cuenta


def _orden(**extra: Any) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "usuario_id": ACUDIENTE,
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 2, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }
    cuerpo.update(extra)
    return cuerpo


def _linea(sku: str, precio: int, cantidad: int = 1, **extra: Any) -> dict[str, Any]:
    return {"sku": sku, "nombre": f"Util {sku}", "cantidad": cantidad, "precio_unitario": precio, **extra}


async def _contar(motor: MotorServicio, modelo: type) -> int:
    async with motor.sesion() as db:
        return int(await db.scalar(select(func.count()).select_from(modelo)))


async def _sin_rastro(motor: MotorServicio) -> None:
    """Una orden rechazada no deja pedido, lineas, reservas, pagos ni avisos."""
    for modelo in (Pedido, LineaPedido, ReservaInventario, Pago, BandejaSalida):
        assert await _contar(motor, modelo) == 0, modelo.__name__


async def _poner_estado(motor: MotorServicio, pedido_id: str, estado: str) -> None:
    async with motor.sesion() as db:
        await db.execute(update(PEDIDO).where(PEDIDO.c.id == uuid.UUID(pedido_id)).values(estado=estado))


async def _fechar_pago(motor: MotorServicio, referencia: str, *, minutos: int) -> None:
    """Fija la fecha del pago: `now()` de SQLite tiene resolucion de segundos y dos intentos seguidos
    empatarian en "el mas reciente" (en Postgres el reloj de transaccion es de microsegundos)."""
    async with motor.sesion() as db:
        await db.execute(
            update(Pago.__table__)
            .where(Pago.__table__.c.referencia_wompi == referencia)
            .values(creado_en=datetime(2026, 3, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=minutos))
        )


async def _crear_orden(http: httpx.AsyncClient, **extra: Any) -> str:
    respuesta = await http.post("/v1/ordenes", json=_orden(**extra))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["pedido_id"]


async def _iniciar_pago(http: httpx.AsyncClient, pedido_id: str, **extra: Any) -> dict[str, Any]:
    cuerpo = {"correo_cliente": CORREO, "metodo": "pse", **extra}
    respuesta = await http.post(f"/v1/ordenes/{pedido_id}/pago", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _evento(pago: dict[str, Any], estado_wompi: str, **extra: Any) -> dict[str, Any]:
    evento = app.state.pasarela.emitir_evento(
        referencia=pago["referencia_wompi"],
        transaccion_id=pago["transaccion_wompi"],
        estado_wompi=estado_wompi,
    )
    return {**evento, **extra}


async def _pedido_pagado(http: httpx.AsyncClient) -> tuple[str, dict[str, Any]]:
    pedido_id = await _crear_orden(http)
    pago = await _iniciar_pago(http, pedido_id)
    respuesta = await http.post("/v1/webhooks/wompi", json=_evento(pago, "APPROVED"))
    assert respuesta.json()["estado"] == "aplicado"
    return pedido_id, pago


# --- crear orden: rechazos ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"usuario_id": "acudiente-ficticio"}, "usuario_id"),
        ({"trabajo_id": "trabajo-ficticio"}, "trabajo_id"),
        ({"lineas": [_linea("TK-C001-ECO", 4500, matricula_id="matricula-ficticia")]}, "matricula_id"),
    ],
)
async def test_un_identificador_mal_formado_es_422_antes_de_cobrar_o_reservar(entorno, extra, campo):
    """`identificador_invalido` nombra el campo; no queda rastro alguno en la base y, para el
    usuario y el trabajo, ni siquiera se molesta a Catalogo."""
    http, motor, _ = entorno

    respuesta = await http.post("/v1/ordenes", json=_orden(**extra))

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "error": "identificador_invalido",
        "mensaje": f"El campo {campo} no tiene forma de identificador.",
        "campo": campo,
    }
    if campo != "matricula_id":
        assert app.state.catalogo.consultas == []
    await _sin_rastro(motor)


async def test_catalogo_caido_es_503_y_no_deja_pedido_ni_reserva(entorno, metricas):
    http, motor, pasarela = entorno
    app.state.catalogo = CatalogoCaidoDoble()
    CatalogoCaidoDoble.consultas = 0

    respuesta = await http.post("/v1/ordenes", json=_orden())

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "error": "catalogo_no_disponible",
        "mensaje": "No se pudo re-verificar el precio con Catalogo; la orden no se cerro.",
    }
    assert CatalogoCaidoDoble.consultas == 1
    assert metricas == {"ordenes": 0, "pagos": 0}
    assert pasarela.llamadas == []
    await _sin_rastro(motor)


@pytest.mark.parametrize(
    "precios",
    [{}, {"TK-C001-ECO": None}, {"TK-C001-ECO": 5200}],
    ids=["sku_inexistente", "sin_precio_vigente", "precio_distinto"],
)
async def test_sku_desconocido_sin_precio_o_con_precio_distinto_es_422_sin_rastro(entorno, metricas, precios):
    http, motor, _ = entorno
    app.state.catalogo = CatalogoFalso(precios)

    respuesta = await http.post("/v1/ordenes", json=_orden())

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "error": "precio_cambiado",
        "mensaje": "El precio de una o mas lineas cambio; revisa el nuevo precio antes de pagar.",
        "campo": "lineas",
    }
    assert metricas["ordenes"] == 0
    await _sin_rastro(motor)


async def test_un_solo_renglon_desactualizado_tumba_la_orden_entera(entorno):
    """Dos renglones: el primero coincide con Catalogo y el segundo no. No se cierra la mitad."""
    http, motor, _ = entorno
    lineas = [_linea("TK-C001-ECO", 4500), _linea("TK-L002-LAP", 999)]  # Catalogo dice 1.200

    respuesta = await http.post("/v1/ordenes", json=_orden(lineas=lineas))

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"
    await _sin_rastro(motor)


# --- crear orden: lo que queda persistido -------------------------------------------------------


async def test_orden_de_dos_renglones_suma_el_total_congela_precios_y_reserva_cada_uno(entorno, metricas):
    http, motor, _ = entorno
    trabajo, matricula = str(uuid.uuid4()), str(uuid.uuid4())
    lineas = [_linea("TK-C001-ECO", 4500, 2, matricula_id=matricula), _linea("TK-L002-LAP", 1200, 3)]

    respuesta = await http.post("/v1/ordenes", json=_orden(lineas=lineas, trabajo_id=trabajo, hijos=2))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 4500 * 2 + 1200 * 3 == 12_600
    assert (cuerpo["trabajo_id"], cuerpo["hijos"], cuerpo["estado"]) == (trabajo, 2, "pendiente_pago")
    assert [(item["sku"], item["cantidad"], item["precio_unitario"]) for item in cuerpo["lineas"]] == [
        ("TK-C001-ECO", 2, 4500),
        ("TK-L002-LAP", 3, 1200),
    ]
    assert metricas["ordenes"] == 1
    async with motor.sesion() as db:
        reservas = {r.cantidad: r.estado for r in await db.scalars(select(ReservaInventario))}
        guardadas = {lin.sku: lin for lin in await db.scalars(select(LineaPedido))}
    assert reservas == {2: "activa", 3: "activa"}
    assert guardadas["TK-C001-ECO"].matricula_id == uuid.UUID(matricula)
    assert guardadas["TK-L002-LAP"].matricula_id is None


async def test_el_id_canonico_lo_manda_catalogo_y_no_el_cliente(entorno):
    """El cliente puede mandar un `producto_canonico_id` (o basura): se ignora, manda el sku
    re-verificado. Si no, alguien podria reservar stock de otro producto pagando el precio de este."""
    http, motor, _ = entorno
    impostor = str(uuid.uuid4())
    lineas = [_linea("TK-C001-ECO", 4500, producto_canonico_id=impostor)]

    respuesta = await http.post("/v1/ordenes", json=_orden(lineas=lineas))

    assert respuesta.status_code == 201
    async with motor.sesion() as db:
        linea = (await db.scalars(select(LineaPedido))).one()
        reserva = (await db.scalars(select(ReservaInventario))).one()
    canonico = uuid.uuid5(uuid.NAMESPACE_OID, "TK-C001-ECO")
    assert linea.producto_canonico_id == canonico != uuid.UUID(impostor)
    assert reserva.producto_canonico_id == canonico


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"lineas": []}, "lineas"),
        ({"lineas": [_linea("TK-C001-ECO", 4500, cantidad=0)]}, "lineas.0.cantidad"),
        ({"lineas": [_linea("TK-C001-ECO", -1)]}, "lineas.0.precio_unitario"),
        ({"lineas": [_linea("S" * 65, 4500)]}, "lineas.0.sku"),
        ({"hijos": -1}, "hijos"),
        (
            {"entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1", "ciudad": ""}},
            "entrega.ciudad",
        ),
        ({"entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1"}}, "entrega.ciudad"),
        ({"usuario_id": None}, "usuario_id"),
    ],
)
async def test_una_orden_con_forma_invalida_es_400_con_el_campo_y_sin_eco(entorno, cambio, campo):
    http, motor, _ = entorno

    respuesta = await http.post("/v1/ordenes", json=_orden(**cambio))

    assert respuesta.status_code == 400
    assert respuesta.json() == {
        "error": "entrada_invalida",
        "mensaje": "La peticion no tiene la forma que el contrato espera.",
        "campo": campo,
    }
    assert "SSSSSSSS" not in respuesta.text  # el valor enviado jamas vuelve en la respuesta
    await _sin_rastro(motor)


# --- iniciar pago -------------------------------------------------------------------------------


@pytest.mark.parametrize("metodo", ["pse", "nequi", "tarjeta"])
async def test_el_pago_manda_centavos_a_la_pasarela_guarda_pesos_y_solo_ids_y_estado(entorno, metodo):
    """Total $9.000: a la pasarela 900.000 centavos con el correo y la redireccion; en la base 9.000 y
    el metodo elegido. La respuesta no repite el correo ni inventa campos (SG-03)."""
    http, motor, pasarela = entorno
    pedido_id = await _crear_orden(http)

    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json={
            "correo_cliente": CORREO,
            "metodo": metodo,
            "url_redireccion": "https://tienda.example.test/kit",
        },
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"pago_id", "referencia_wompi", "transaccion_wompi", "estado", "url_redireccion"}
    assert cuerpo["estado"] == EstadoPago.INICIADO.value
    assert cuerpo["referencia_wompi"] == f"tukit-{pedido_id}-1"
    assert CORREO not in respuesta.text
    assert pasarela.llamadas == [
        {
            "referencia": f"tukit-{pedido_id}-1",
            "monto_centavos": 900_000,
            "correo_cliente": CORREO,
            "metodo": metodo,
            "url_redireccion": "https://tienda.example.test/kit",
        }
    ]
    async with motor.sesion() as db:
        pago = (await db.scalars(select(Pago))).one()
    assert (pago.monto, pago.metodo, pago.estado) == (9000, metodo, "iniciado")
    assert str(pago.id) == cuerpo["pago_id"]
    assert pago.transaccion_wompi == cuerpo["transaccion_wompi"]


async def test_un_metodo_de_pago_no_aceptado_es_422_y_no_llega_a_la_pasarela(entorno):
    http, motor, pasarela = entorno
    pedido_id = await _crear_orden(http)

    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": CORREO, "metodo": "bitcoin"}
    )

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "error": "metodo_invalido",
        "mensaje": "El medio de pago no es uno de los aceptados.",
        "campo": "metodo",
    }
    assert pasarela.llamadas == []
    assert await _contar(motor, Pago) == 0


async def test_pagar_un_pedido_que_no_existe_es_404_y_no_llega_a_la_pasarela(entorno):
    http, _, pasarela = entorno

    respuesta = await http.post(f"/v1/ordenes/{uuid.uuid4()}/pago", json={"correo_cliente": CORREO})

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "pedido_no_existe"
    assert pasarela.llamadas == []


@pytest.mark.parametrize(
    "estado",
    [e.value for e in EstadoPedido if e is not EstadoPedido.PENDIENTE_PAGO],
)
async def test_un_pedido_que_ya_no_esta_pendiente_no_se_vuelve_a_cobrar(entorno, estado):
    """Cobrar dos veces un pedido pagado, o cobrar uno cancelado, es el peor fallo de un checkout."""
    http, motor, pasarela = entorno
    pedido_id = await _crear_orden(http)
    await _poner_estado(motor, pedido_id, estado)

    respuesta = await http.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": CORREO})

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "error": "pedido_no_pagable",
        "mensaje": "El pedido ya no esta pendiente de pago.",
    }
    assert pasarela.llamadas == []
    assert await _contar(motor, Pago) == 0


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({}, "correo_cliente"),
        ({"correo_cliente": "a@b"}, "correo_cliente"),
        ({"correo_cliente": CORREO, "metodo": "x" * 17}, "metodo"),
    ],
)
async def test_un_pago_con_forma_invalida_es_400_y_no_llega_a_la_pasarela(entorno, cuerpo, campo):
    http, _, pasarela = entorno
    pedido_id = await _crear_orden(http)

    respuesta = await http.post(f"/v1/ordenes/{pedido_id}/pago", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "entrada_invalida"
    assert respuesta.json()["campo"] == campo
    assert pasarela.llamadas == []


async def test_si_la_pasarela_cae_no_queda_pago_huerfano_y_el_reintento_reusa_la_referencia(entorno):
    """La caida no guarda nada: el reintento posterior sale con la referencia `-1`, no `-2`."""
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    app.state.pasarela = PasarelaIntermitente(fallos=1)

    caida = await http.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": CORREO})
    assert caida.status_code == 502
    assert caida.json() == {
        "error": "pasarela_no_disponible",
        "mensaje": "No se pudo contactar la pasarela de pago; intenta de nuevo en un momento.",
    }
    assert await _contar(motor, Pago) == 0

    reintento = await _iniciar_pago(http, pedido_id)

    assert reintento["referencia_wompi"] == f"tukit-{pedido_id}-1"
    assert await _contar(motor, Pago) == 1


# --- webhook ------------------------------------------------------------------------------------


@pytest.mark.parametrize("campo_ausente", ["id", "referencia"])
async def test_un_evento_firmado_pero_incompleto_se_ignora_sin_mover_nada(entorno, campo_ausente):
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    pago = await _iniciar_pago(http, pedido_id)
    evento = _evento(pago, "APPROVED")
    if campo_ausente == "id":
        del evento["id"]
    else:
        del evento["data"]["transaction"]["reference"]  # no esta entre las propiedades firmadas

    respuesta = await http.post("/v1/webhooks/wompi", json=evento)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ignorado", "motivo": "evento_incompleto"}
    assert await _contar(motor, EventoPasarelaProcesado) == 0
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pendiente_pago"


async def test_un_evento_de_una_referencia_desconocida_queda_registrado_y_no_mueve_pedidos(entorno, metricas):
    """Evento valido de un pago que no conocemos: `sin_pago`, anotado como procesado (el reenvio es
    `repetido`) y ningun pedido ni contador se toca."""
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    evento = app.state.pasarela.emitir_evento(
        referencia="tukit-de-otro-comercio-1", transaccion_id="falsa-999", estado_wompi="APPROVED"
    )

    primera = await http.post("/v1/webhooks/wompi", json=evento)
    segunda = await http.post("/v1/webhooks/wompi", json=evento)

    assert primera.json() == {"estado": "sin_pago", "referencia": "tukit-de-otro-comercio-1"}
    assert segunda.json() == {"estado": "repetido", "evento_id": "evt-falsa-999"}
    assert await _contar(motor, EventoPasarelaProcesado) == 1
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pendiente_pago"
    assert metricas["pagos"] == 0


@pytest.mark.parametrize("cuerpo", [[], "evento", 7])
async def test_un_webhook_cuyo_cuerpo_no_es_un_objeto_es_400(entorno, cuerpo):
    http, _, _ = entorno

    respuesta = await http.post("/v1/webhooks/wompi", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "entrada_invalida"


async def test_un_webhook_vacio_no_trae_firma_y_se_ignora(entorno):
    http, _, _ = entorno

    respuesta = await http.post("/v1/webhooks/wompi", json={})

    assert respuesta.json() == {"estado": "ignorado", "motivo": "firma_invalida"}


async def test_un_pago_pendiente_actualiza_el_pago_pero_no_el_pedido_ni_la_bandeja(entorno, metricas):
    """`PENDING` es "aun no": el pago sigue `iniciado`, el pedido en `pendiente_pago`, sin aviso."""
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    pago = await _iniciar_pago(http, pedido_id)

    respuesta = await http.post("/v1/webhooks/wompi", json=_evento(pago, "PENDING"))

    assert respuesta.json() == {
        "estado": "aplicado",
        "evento_id": "evt-falsa-1",
        "pago_estado": "iniciado",
        "pedido_transicionado": False,
    }
    pedido = (await http.get(f"/v1/ordenes/{pedido_id}")).json()
    assert (pedido["estado"], pedido["pago"]["estado"]) == ("pendiente_pago", "iniciado")
    assert await _contar(motor, BandejaSalida) == 0
    assert metricas["pagos"] == 0


async def test_rechazado_y_luego_aprobado_en_un_reintento_termina_pagado_con_un_solo_aviso(entorno, metricas):
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    primero = await _iniciar_pago(http, pedido_id)
    await _fechar_pago(motor, primero["referencia_wompi"], minutos=0)
    rechazo = await http.post("/v1/webhooks/wompi", json=_evento(primero, "DECLINED"))
    assert rechazo.json()["pedido_transicionado"] is False
    assert metricas["pagos"] == 0

    segundo = await _iniciar_pago(http, pedido_id)
    await _fechar_pago(motor, segundo["referencia_wompi"], minutos=5)
    aprobado = await http.post("/v1/webhooks/wompi", json=_evento(segundo, "APPROVED"))

    assert aprobado.json()["pedido_transicionado"] is True
    pedido = (await http.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == "pagado"
    assert pedido["pago"]["referencia_wompi"] == f"tukit-{pedido_id}-2"  # el ultimo intento
    async with motor.sesion() as db:
        estados = {p.referencia_wompi: p.estado for p in await db.scalars(select(Pago))}
    assert estados == {f"tukit-{pedido_id}-1": "rechazado", f"tukit-{pedido_id}-2": "aprobado"}
    assert await _contar(motor, BandejaSalida) == 1
    assert metricas["pagos"] == 1


async def test_un_segundo_aprobado_con_otro_id_no_duplica_el_aviso_ni_la_metrica(entorno, metricas):
    """El candado por id de evento no basta si Wompi manda otro id: la maquina de estados
    (`pagado -> pagado` no es transicion) impide re-pagar el pedido y re-avisar al acudiente."""
    http, motor, _ = entorno
    pedido_id, pago = await _pedido_pagado(http)

    otra = await http.post("/v1/webhooks/wompi", json=_evento(pago, "APPROVED", id="evt-otro-id-ficticio"))

    assert otra.json() == {
        "estado": "aplicado",
        "evento_id": "evt-otro-id-ficticio",
        "pago_estado": "aprobado",
        "pedido_transicionado": False,
    }
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pagado"
    assert await _contar(motor, BandejaSalida) == 1
    assert metricas["pagos"] == 1


async def test_un_aprobado_sobre_un_pedido_cancelado_no_lo_resucita_ni_avisa(entorno, metricas):
    """El barredor o un retracto cancelaron el pedido y luego llega el pago: `cancelado` es terminal,
    no se pasa a `pagado`, no se encola `pedido_pagado` y no se cuenta como pago aprobado."""
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    pago = await _iniciar_pago(http, pedido_id)
    await _poner_estado(motor, pedido_id, "cancelado")

    respuesta = await http.post("/v1/webhooks/wompi", json=_evento(pago, "APPROVED"))

    assert respuesta.status_code == 200
    assert respuesta.json()["pedido_transicionado"] is False
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "cancelado"
    assert await _contar(motor, BandejaSalida) == 0
    assert metricas["pagos"] == 0


async def test_el_aviso_pedido_pagado_lleva_el_pedido_el_total_y_la_correlacion_de_la_peticion(entorno):
    """Outbox: el aviso nace en la misma transaccion del pago y hereda el `x-correlation-id` del
    webhook, para poder seguir el hilo de un pago hasta el despacho."""
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    pago = await _iniciar_pago(http, pedido_id)

    respuesta = await http.post(
        "/v1/webhooks/wompi",
        json=_evento(pago, "APPROVED"),
        headers={"x-correlation-id": "cid-ficticio-0009"},
    )

    assert respuesta.headers["x-correlation-id"] == "cid-ficticio-0009"
    async with motor.sesion() as db:
        aviso = (await db.scalars(select(BandejaSalida))).one()
    assert (aviso.tipo, aviso.agregado_tipo, aviso.agregado_id) == (
        "pedido_pagado",
        "pedido",
        uuid.UUID(pedido_id),
    )
    assert aviso.publicado_en is None
    assert aviso.carga == {
        "pedido_id": pedido_id,
        "usuario_id": ACUDIENTE,
        "total": 9000,
        "correlacion_id": "cid-ficticio-0009",
    }


# --- avanzar la cadena de entrega ---------------------------------------------------------------


async def _avanzar(http: httpx.AsyncClient, pedido_id: str, **cuerpo: Any) -> httpx.Response:
    return await http.post(f"/v1/ordenes/{pedido_id}/avanzar", json=cuerpo)


async def test_un_destino_que_no_es_un_estado_es_422_y_el_pedido_no_cambia(entorno):
    http, _, _ = entorno
    pedido_id, _ = await _pedido_pagado(http)

    respuesta = await _avanzar(http, pedido_id, destino="volando")

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "error": "destino_invalido",
        "mensaje": "El estado destino no es uno de los del pedido.",
        "campo": "destino",
    }
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pagado"


async def test_no_se_avanza_un_pedido_sin_pagar_a_preparacion(entorno):
    http, _, _ = entorno
    pedido_id = await _crear_orden(http)

    respuesta = await _avanzar(http, pedido_id, destino="en_preparacion")

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "error": "transicion_invalida",
        "mensaje": "No se puede pasar el pedido a ese estado desde el actual.",
        "campo": "destino",
    }
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pendiente_pago"


@pytest.mark.parametrize("terminal", ["entregado", "cancelado"])
@pytest.mark.parametrize("destino", ["en_preparacion", "pagado", "cancelado", "incidencia"])
async def test_un_pedido_terminal_no_sale_de_su_estado(entorno, terminal, destino):
    http, motor, _ = entorno
    pedido_id = await _crear_orden(http)
    await _poner_estado(motor, pedido_id, terminal)

    respuesta = await _avanzar(http, pedido_id, destino=destino)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == terminal


@pytest.mark.parametrize(
    "faltante",
    [{"transportadora": "Servientrega"}, {"guia": "GUIA-0001"}, {"transportadora": "", "guia": "GUIA-0001"}],
    ids=["sin_guia", "sin_transportadora", "transportadora_vacia"],
)
async def test_despachar_exige_transportadora_y_guia_y_no_cambia_el_estado(entorno, faltante):
    http, motor, _ = entorno
    pedido_id, _ = await _pedido_pagado(http)
    await _avanzar(http, pedido_id, destino="en_preparacion")

    respuesta = await _avanzar(http, pedido_id, destino="despachado", **faltante)

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "error": "despacho_incompleto",
        "mensaje": "Un despacho necesita transportadora y guia para poder rastrearse.",
        "campo": "destino",
    }
    pedido = (await http.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == "en_preparacion"
    assert pedido["envio"]["guia"] is None


async def test_la_cadena_completa_sella_el_envio_y_no_borra_lo_ya_sellado(entorno):
    """Despachar sella transportadora, guia y fecha estimada; los pasos siguientes (que no los
    mandan) los conservan; entregar marca `entregado_en`. La respuesta es el pedido completo."""
    http, _, _ = entorno
    pedido_id, _ = await _pedido_pagado(http)
    await _avanzar(http, pedido_id, destino="en_preparacion")

    despachado = await _avanzar(
        http,
        pedido_id,
        destino="despachado",
        transportadora="Servientrega",
        guia="GUIA-0001",
        entrega_estimada="2026-03-05T17:00:00+00:00",
    )
    assert despachado.status_code == 200
    assert despachado.json()["estado"] == "despachado"
    assert despachado.json()["envio"]["entrega_estimada"].startswith("2026-03-05T17:00:00")
    assert despachado.json()["envio"]["entregado_en"] is None

    reparto = await _avanzar(http, pedido_id, destino="en_reparto")
    entregado = await _avanzar(http, pedido_id, destino="entregado")

    assert reparto.json()["estado"] == "en_reparto"
    assert reparto.json()["envio"]["guia"] == "GUIA-0001"
    cuerpo = entregado.json()
    assert cuerpo["estado"] == "entregado"
    assert (cuerpo["envio"]["transportadora"], cuerpo["envio"]["guia"]) == ("Servientrega", "GUIA-0001")
    assert cuerpo["envio"]["entregado_en"] is not None
    assert cuerpo["pago"]["estado"] == "aprobado"  # la respuesta es la misma vista completa del pedido


async def test_una_incidencia_vuelve_a_preparacion_o_cancela_pero_no_salta_pasos(entorno):
    http, _, _ = entorno
    pedido_id, _ = await _pedido_pagado(http)

    assert (await _avanzar(http, pedido_id, destino="incidencia")).json()["estado"] == "incidencia"
    saltar = await _avanzar(http, pedido_id, destino="despachado", transportadora="X", guia="Y")
    assert saltar.status_code == 409  # de incidencia no se despacha sin pasar por preparacion
    assert (await _avanzar(http, pedido_id, destino="en_preparacion")).json()["estado"] == "en_preparacion"
    assert (await _avanzar(http, pedido_id, destino="incidencia")).json()["estado"] == "incidencia"
    assert (await _avanzar(http, pedido_id, destino="cancelado")).json()["estado"] == "cancelado"


@pytest.mark.parametrize("destino", ["", "d" * 25])
async def test_un_destino_vacio_o_demasiado_largo_es_400(entorno, destino):
    http, _, _ = entorno
    pedido_id, _ = await _pedido_pagado(http)

    respuesta = await _avanzar(http, pedido_id, destino=destino)

    assert respuesta.status_code == 400
    assert respuesta.json()["campo"] == "destino"
