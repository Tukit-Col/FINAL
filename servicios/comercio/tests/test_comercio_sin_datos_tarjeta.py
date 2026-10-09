"""NFR-MAN-01: Comercio nunca guarda, repite ni registra datos de tarjeta (SG-03, CONTRATO_API §9).

La regla es del sistema, no del medio de pago: aunque el PSE no pase tarjeta, un cliente puede mandar
`numero_tarjeta` o `cvv` donde no debe, y Wompi devuelve en el evento un `payment_method` con datos del
titular. Lo unico que Comercio persiste es el id de la transaccion y su estado. Se comprueba en
cuatro frentes, siempre con un numero de prueba PUBLICO (no es de nadie) y un titular ficticio:

- El esquema: ninguna tabla ni columna del modelo se llama como un dato de tarjeta.
- La entrada: los campos de tarjeta de una peticion de pago se descartan en la frontera; ni llegan al
  puerto de la pasarela ni se guardan, ni aparecen en la respuesta.
- El webhook: un evento firmado con `payment_method` completo se reduce a id y estado; ni la base ni
  la bandeja de salida lo conservan.
- Los errores y los logs: una validacion fallida jamas repite lo recibido y nada de la tarjeta sale por
  `logging` ni por la salida estandar.

Sin red: SQLite en memoria, `PasarelaFalsa` (espia) y un Catalogo en memoria.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, Pago
from tukit_comercio.pasarela import PasarelaFalsa, TransaccionCreada
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

# Numero de prueba publico de las pasarelas: no pertenece a ninguna cuenta real.
PAN = "4242424242424242"
CVV = "737"
TITULAR = "Titular Ficticio Tarjeta"
VENCIMIENTO = "12/2031"
CORREO = "acudiente@example.test"
ACUDIENTE = "22222222-2222-5222-8222-222222222222"

# Los trozos de un nombre de tabla o columna que delatan un dato de medio de pago.
TOKENS_DE_TARJETA = {
    "pan",
    "cvv",
    "cvc",
    "cvv2",
    "tarjeta",
    "card",
    "cardholder",
    "holder",
    "titular",
    "expiry",
    "expiracion",
    "vencimiento",
    "bin",
    "ultimos",
    "cuatro",
}

SECRETOS = (PAN, TITULAR, VENCIMIENTO)


class PasarelaEspia(PasarelaFalsa):
    """Anota con que llamo el router al puerto: lo que no llega aqui no puede viajar a Wompi."""

    def __init__(self) -> None:
        super().__init__()
        self.llamadas: list[dict[str, Any]] = []

    async def crear_transaccion(self, **kwargs: Any) -> TransaccionCreada:
        self.llamadas.append(kwargs)
        return await super().crear_transaccion(**kwargs)


class CatalogoFalso:
    async def resolver(self, sku: str):
        return uuid.uuid5(uuid.NAMESPACE_OID, sku), 4500


@pytest_asyncio.fixture
async def entorno() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio, PasarelaEspia]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    pasarela = PasarelaEspia()
    app.state.motor = motor
    app.state.pasarela = pasarela
    app.state.catalogo = CatalogoFalso()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor, pasarela
    await engine.dispose()


def _orden() -> dict[str, Any]:
    return {
        "usuario_id": ACUDIENTE,
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 2, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }


def _con_tarjeta(cuerpo: dict[str, Any]) -> dict[str, Any]:
    """El cuerpo de pago + los campos de tarjeta que un cliente mal armado podria colar."""
    return {
        **cuerpo,
        "numero_tarjeta": PAN,
        "cvv": CVV,
        "titular": TITULAR,
        "vencimiento": VENCIMIENTO,
        "payment_method": {"type": "CARD", "number": PAN, "cvc": CVV, "card_holder": TITULAR},
    }


def _evento_con_tarjeta(pasarela: PasarelaFalsa, pago: dict[str, Any], estado: str) -> dict[str, Any]:
    """Un evento firmado como el de Wompi, con el `payment_method` completo dentro de la transaccion.

    Las propiedades firmadas son `transaction.id` y `transaction.status`; agregar campos a la
    transaccion no rompe la firma, asi que el evento se acepta y el reto es lo que se conserva."""
    evento = pasarela.emitir_evento(
        referencia=pago["referencia_wompi"], transaccion_id=pago["transaccion_wompi"], estado_wompi=estado
    )
    evento["data"]["transaction"]["payment_method"] = {
        "type": "CARD",
        "extra": {"number": PAN, "cvc": CVV, "card_holder": TITULAR, "exp": VENCIMIENTO, "last_four": "4242"},
    }
    return evento


async def _volcado(motor: MotorServicio) -> str:
    """Todo lo que hay en la base, de todas las tablas, como un solo texto."""
    partes: list[str] = []
    async with motor.sesion() as db:
        for tabla in Base.metadata.sorted_tables:
            for fila in await db.execute(select(tabla)):
                partes.append(
                    f"{tabla.name}: " + json.dumps([str(valor) for valor in fila], ensure_ascii=False)
                )
    return "\n".join(partes)


def _sin_datos_de_tarjeta(texto: str) -> None:
    for secreto in SECRETOS:
        assert secreto not in texto, f"aparece un dato de tarjeta ({secreto[:4]}...)"
    assert f'"{CVV}"' not in texto  # el CVV como valor completo de una celda


async def _crear_y_pagar(
    http: httpx.AsyncClient, cuerpo_pago: dict[str, Any] | None = None
) -> tuple[str, httpx.Response]:
    pedido_id = (await http.post("/v1/ordenes", json=_orden())).json()["pedido_id"]
    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/pago", json=cuerpo_pago or {"correo_cliente": CORREO, "metodo": "pse"}
    )
    return pedido_id, respuesta


# --- el esquema ---------------------------------------------------------------------------------


def test_ninguna_tabla_ni_columna_del_modelo_nombra_un_dato_de_tarjeta():
    """SG-03 en el esquema: si alguien agrega `numero_tarjeta`, `cvv` o `titular_tarjeta`, esto avisa
    antes de que llegue una migracion. Se comparan los trozos del nombre (`ultimos_cuatro` cae, `pagado`
    no)."""
    sospechosos = [
        f"{tabla.name}.{columna.name}" if columna is not None else tabla.name
        for tabla in Base.metadata.sorted_tables
        for columna in (None, *tabla.columns)
        if TOKENS_DE_TARJETA & set((tabla.name if columna is None else columna.name).lower().split("_"))
    ]

    assert "pago" in Base.metadata.tables  # la prueba mira el modelo real, no un conjunto vacio
    assert sospechosos == []


def test_el_pago_solo_guarda_referencia_transaccion_metodo_estado_y_monto():
    assert {columna.name for columna in Pago.__table__.columns} == {
        "id",
        "pedido_id",
        "referencia_wompi",
        "transaccion_wompi",
        "metodo",
        "estado",
        "monto",
        "creado_en",
        "actualizado_en",
    }


# --- la entrada: iniciar el pago ----------------------------------------------------------------


async def test_los_campos_de_tarjeta_de_una_peticion_de_pago_se_descartan_en_la_frontera(entorno):
    http, motor, pasarela = entorno

    pedido_id, respuesta = await _crear_y_pagar(
        http, _con_tarjeta({"correo_cliente": CORREO, "metodo": "pse"})
    )

    assert respuesta.status_code == 201
    # La respuesta no repite nada de la tarjeta ni agrega campos.
    assert set(respuesta.json()) == {
        "pago_id",
        "referencia_wompi",
        "transaccion_wompi",
        "estado",
        "url_redireccion",
    }
    _sin_datos_de_tarjeta(respuesta.text)
    # Al puerto de la pasarela solo llegan los cinco argumentos del contrato, sin rastro de la tarjeta.
    (llamada,) = pasarela.llamadas
    assert set(llamada) == {"referencia", "monto_centavos", "correo_cliente", "metodo", "url_redireccion"}
    _sin_datos_de_tarjeta(repr(llamada))
    # Y en la base, ni en el pago ni en ninguna otra tabla.
    _sin_datos_de_tarjeta(await _volcado(motor))
    async with motor.sesion() as db:
        pago = (await db.execute(select(Pago).where(Pago.pedido_id == uuid.UUID(pedido_id)))).scalar_one()
    assert (pago.metodo, pago.estado, pago.monto) == ("pse", "iniciado", 9000)


@pytest.mark.parametrize(
    "metodo", [PAN, " ".join([PAN[:4], PAN[4:8], PAN[8:12], PAN[12:]])], ids=["16_digitos", "con_espacios"]
)
async def test_un_numero_de_tarjeta_pegado_en_el_campo_metodo_se_rechaza_sin_repetirlo(entorno, metodo):
    """El error mas realista: el cliente pega el numero en el campo equivocado. Es 4xx, el sobre no
    lo repite (ni como mensaje ni como `campo`) y no queda pago alguno."""
    http, motor, pasarela = entorno
    pedido_id = (await http.post("/v1/ordenes", json=_orden())).json()["pedido_id"]

    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": CORREO, "metodo": metodo}
    )

    assert respuesta.status_code in (400, 422)
    assert respuesta.json()["campo"] == "metodo"
    assert PAN not in respuesta.text
    assert PAN[:4] + " " + PAN[4:8] not in respuesta.text
    assert pasarela.llamadas == []
    async with motor.sesion() as db:
        assert (await db.execute(select(Pago))).first() is None


async def test_un_numero_de_tarjeta_en_el_correo_tampoco_se_repite_en_el_error(entorno):
    http, _, _ = entorno
    pedido_id = (await http.post("/v1/ordenes", json=_orden())).json()["pedido_id"]

    respuesta = await http.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": PAN[:4], "cvv": CVV})

    assert respuesta.status_code == 400
    assert respuesta.json()["campo"] == "correo_cliente"
    assert PAN[:4] not in respuesta.text
    assert CVV not in respuesta.text


# --- el webhook ---------------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["APPROVED", "DECLINED", "PENDING"])
async def test_un_evento_con_payment_method_se_reduce_a_id_y_estado(entorno, estado):
    """Wompi manda en la transaccion el medio usado; Comercio lo ignora. Ni la base, ni la bandeja de
    salida (que viaja a otros servicios), ni la respuesta del webhook conservan un dato de tarjeta."""
    http, motor, pasarela = entorno
    _, pago = await _crear_y_pagar(http)
    evento = _evento_con_tarjeta(pasarela, pago.json(), estado)

    respuesta = await http.post("/v1/webhooks/wompi", json=evento)

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aplicado"
    _sin_datos_de_tarjeta(respuesta.text)
    volcado = await _volcado(motor)
    _sin_datos_de_tarjeta(volcado)
    assert "last_four" not in volcado
    assert "payment_method" not in volcado


async def test_un_evento_aprobado_deja_en_la_bandeja_solo_pedido_usuario_y_total(entorno):
    http, motor, pasarela = entorno
    pedido_id, pago = await _crear_y_pagar(http)

    await http.post("/v1/webhooks/wompi", json=_evento_con_tarjeta(pasarela, pago.json(), "APPROVED"))

    async with motor.sesion() as db:
        cargas = [fila.carga for fila in await db.execute(select(Base.metadata.tables["bandeja_salida"]))]
    assert len(cargas) == 1
    assert set(cargas[0]) <= {"pedido_id", "usuario_id", "total", "correlacion_id"}
    assert cargas[0]["pedido_id"] == pedido_id
    _sin_datos_de_tarjeta(json.dumps(cargas))


# --- logs y salida estandar ---------------------------------------------------------------------


async def test_nada_de_la_tarjeta_sale_por_logging_ni_por_la_salida_estandar(entorno, caplog, capsys):
    """Un recorrido completo (orden, pago con campos de tarjeta, error de validacion y webhook con
    `payment_method`) con el registro al maximo detalle: ni un `logging` ni un `print` repite el cuerpo."""
    http, _, pasarela = entorno
    caplog.set_level(logging.DEBUG)

    _, pago = await _crear_y_pagar(http, _con_tarjeta({"correo_cliente": CORREO, "metodo": "pse"}))
    await http.post(f"/v1/ordenes/{uuid.uuid4()}/pago", json={"correo_cliente": PAN, "metodo": PAN})
    await http.post("/v1/webhooks/wompi", json=_evento_con_tarjeta(pasarela, pago.json(), "APPROVED"))

    salida = capsys.readouterr()
    assert any(
        r.name == "httpx" for r in caplog.records
    )  # la captura esta viva: el cliente de prueba registra
    _sin_datos_de_tarjeta(caplog.text)
    _sin_datos_de_tarjeta(salida.out)
    _sin_datos_de_tarjeta(salida.err)
