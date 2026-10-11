"""NFR-MAN-01: la pasarela de pago en modo falso: firma del webhook, montos, idempotencia y entorno.

`test_pasarela.py` fija las formulas de firma contra vectores. Aqui se ejerce el resto del puerto
`PasarelaPago` SIN red real: `WompiSandbox` contra un `httpx.MockTransport` (nada sale a
sandbox.wompi.co) y `PasarelaFalsa`. Se defiende lo que, si falla, cobra mal o no cobra:

- La verificacion de firma del webhook: valida, sin distinguir mayusculas, y rechazada ante cualquier
  alteracion del cuerpo firmado (estado, MONTO en centavos), otro secreto, o firma ausente.
- Los montos: en los datos del widget de Wompi viaja el total en CENTAVOS con su firma de
  integridad, y lo persistido es el total en pesos; un evento cuyo monto fue alterado se ignora sin
  mover el pedido.
- La idempotencia: el mismo evento repetido mueve el pedido y la bandeja de salida una sola vez.
- SG-03: los datos del widget, que van al navegador, no llevan ningun dato de medio de pago ni la
  llave privada ni los secretos.
- La consulta a Wompi: un fallo nunca se toma por un resultado.
- La eleccion de adaptador por `WOMPI_MODO`, que falla ruidoso si faltan llaves o el modo no existe.

Todo dato es ficticio (llaves, correos @example.test, referencias).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import BandejaSalida, Base, EstadoPago, EstadoPedido, Pago
from tukit_comercio.pasarela import (
    MONEDA,
    URL_PRODUCCION,
    URL_SANDBOX,
    EventoPasarela,
    PasarelaCaida,
    PasarelaFalsa,
    TransaccionCreada,
    TransaccionNoExiste,
    WompiSandbox,
    firma_evento,
    firma_integridad,
    pasarela_desde_entorno,
)
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

SECRETO_EVENTOS = "test_events_secreto_ficticio"
SECRETO_INTEGRIDAD = "test_integrity_secreto_ficticio"
LLAVE_PUBLICA = "pub_test_llave_ficticia"
LLAVE_PRIVADA = "prv_test_llave_ficticia"
TRANSACCION = "1234-1610641025-49201"
PROPIEDADES = ["transaction.id", "transaction.status", "transaction.amount_in_cents"]


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _evento_wompi(
    *,
    estado: str = "APPROVED",
    monto: int = 900_000,
    transaccion: str = TRANSACCION,
    referencia: str = "tukit-ref-1",
    timestamp: int = 1_530_291_411,
    secreto: str = SECRETO_EVENTOS,
    **extra: Any,
) -> dict[str, Any]:
    """Un webhook con la forma real de Wompi, firmado con la receta de la documentacion.

    El checksum se calcula aqui con `hashlib` y la concatenacion literal (id + estado + monto +
    timestamp + secreto), NO con `firma_evento`: asi la prueba no valida el codigo con el codigo."""
    evento: dict[str, Any] = {
        "event": "transaction.updated",
        "data": {
            "transaction": {
                "id": transaccion,
                "amount_in_cents": monto,
                "reference": referencia,
                "currency": MONEDA,
                "status": estado,
            }
        },
        "environment": "test",
        "signature": {"properties": list(PROPIEDADES)},
        "timestamp": timestamp,
        "sent_at": "2026-03-01T12:00:00.000Z",
        **extra,
    }
    evento["signature"]["checksum"] = _sha256(f"{transaccion}{estado}{monto}{timestamp}{secreto}")
    return evento


def _wompi(**kw: Any) -> WompiSandbox:
    return WompiSandbox(
        llave_publica=LLAVE_PUBLICA,
        llave_privada=LLAVE_PRIVADA,
        secreto_eventos=SECRETO_EVENTOS,
        secreto_integridad=SECRETO_INTEGRIDAD,
        **kw,
    )


# --- verificar_firma del adaptador real ---------------------------------------------------------


def test_wompi_acepta_un_evento_con_firma_valida_y_sin_distinguir_mayusculas():
    adaptador = _wompi()
    evento = _evento_wompi()
    assert adaptador.verificar_firma(evento) is True

    evento["signature"]["checksum"] = evento["signature"]["checksum"].upper()
    assert adaptador.verificar_firma(evento) is True


@pytest.mark.parametrize(
    ("alterar", "motivo"),
    [
        (lambda e: e["data"]["transaction"].update(amount_in_cents=100), "monto en centavos alterado"),
        (lambda e: e["data"]["transaction"].update(status="DECLINED"), "estado alterado"),
        (lambda e: e["data"]["transaction"].update(id="otra-transaccion"), "id de transaccion alterado"),
        (lambda e: e.update(timestamp=1), "timestamp alterado"),
        (lambda e: e["signature"].update(properties=PROPIEDADES[:2]), "propiedades firmadas recortadas"),
        (lambda e: e["signature"].update(checksum=""), "checksum vacio"),
        (lambda e: e["signature"].pop("checksum"), "checksum ausente"),
        (lambda e: e.pop("signature"), "sin bloque de firma"),
    ],
)
def test_wompi_rechaza_el_evento_alterado_o_sin_firma(alterar, motivo):
    """Cualquier cambio al cuerpo firmado (incluido el monto) o una firma ausente invalida el evento:
    es lo unico que separa un cobro real de uno inventado."""
    evento = _evento_wompi()
    alterar(evento)
    assert _wompi().verificar_firma(evento) is False, motivo


def test_wompi_rechaza_un_evento_firmado_con_otro_secreto():
    evento = _evento_wompi(secreto="secreto_de_otro_comercio")
    assert _wompi().verificar_firma(evento) is False


def test_una_propiedad_ausente_firma_cadena_vacia_y_no_revienta():
    """Un tramo inexistente (`transaction.nope`), un tramo que cruza un valor que no es objeto y un
    valor nulo valen cadena vacia: la firma cambia, no se lanza una excepcion."""
    base = {"timestamp": 1_700_000_000, "data": {"transaction": {"id": "txn-1", "nulo": None}}}
    esperado = _sha256("1700000000secreto")  # tres propiedades vacias + timestamp + secreto
    evento = {
        **base,
        "signature": {"properties": ["transaction.nope", "transaction.id.x", "transaction.nulo"]},
    }
    assert firma_evento(evento, "secreto") == esperado


def test_firma_evento_sin_bloque_de_firma_ni_datos_firma_solo_timestamp_y_secreto():
    assert firma_evento({"timestamp": 42}, "s") == _sha256("42s")
    assert firma_evento({}, "s") == _sha256("s")
    assert firma_evento({"timestamp": 42, "data": None, "signature": None}, "s") == _sha256("42s")


def test_firma_integridad_incluye_la_moneda_entre_el_monto_y_el_secreto():
    assert firma_integridad("ref", 1, "s") == _sha256(f"ref1{MONEDA}s")
    assert firma_integridad("ref", 1, "s", moneda="USD") == _sha256("ref1USDs")
    assert firma_integridad("ref", 1, "s", moneda="USD") != firma_integridad("ref", 1, "s")


# --- parsear_evento -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado_wompi", "esperado"),
    [
        ("APPROVED", EstadoPago.APROBADO),
        ("approved", EstadoPago.APROBADO),
        ("DECLINED", EstadoPago.RECHAZADO),
        ("VOIDED", EstadoPago.RECHAZADO),
        ("ERROR", EstadoPago.RECHAZADO),
        ("PENDING", EstadoPago.INICIADO),
        ("ESTADO_QUE_WOMPI_INVENTE_MANANA", EstadoPago.INICIADO),
        (None, EstadoPago.INICIADO),
    ],
)
def test_parsear_traduce_el_estado_de_wompi_al_vocabulario_del_pago(estado_wompi, esperado):
    """Lo desconocido NUNCA se traduce a `aprobado`: ante la duda el pago queda `iniciado`. La
    clave de idempotencia es `<transaccion>:<ESTADO>` y el monto viaja en centavos (7c2ae19)."""
    evento = _evento_wompi(estado="APPROVED")
    evento["data"]["transaction"]["status"] = estado_wompi
    datos = _wompi().parsear_evento(evento)
    assert datos == EventoPasarela(
        evento_id=f"{TRANSACCION}:{(estado_wompi or '').upper()}",
        referencia="tukit-ref-1",
        transaccion_id=TRANSACCION,
        estado=esperado,
        monto_centavos=900_000,
    )


@pytest.mark.parametrize(
    "extra",
    [{"id": "evt-1", "event_id": "evt-2"}, {"event_id": "evt-2"}, {}],
    ids=["id-y-event_id", "solo-event_id", "sin-id"],
)
def test_parsear_la_clave_de_idempotencia_es_transaccion_y_estado_y_no_el_id_del_evento(extra):
    """Desde 7c2ae19 el `id` y el `event_id` del sobre no cuentan: cada cambio de estado de una
    transaccion se aplica una vez y un reenvio del mismo estado choca con el candado."""
    adaptador = _wompi()
    assert adaptador.parsear_evento(_evento_wompi(**extra)).evento_id == f"{TRANSACCION}:APPROVED"
    otro_estado = adaptador.parsear_evento(_evento_wompi(estado="DECLINED", **extra)).evento_id
    assert otro_estado == f"{TRANSACCION}:DECLINED"


def test_parsear_un_cuerpo_vacio_no_inventa_datos():
    """Sin transaccion, la clave queda con sus dos partes vacias (`:`) y el webhook lo descarta
    como `evento_incompleto` por faltarle referencia y transaccion."""
    datos = _wompi().parsear_evento({})
    assert datos == EventoPasarela(
        evento_id=":", referencia=None, transaccion_id=None, estado=EstadoPago.INICIADO
    )


# --- crear_transaccion y consultar_transaccion contra un Wompi simulado -----------------------


def _wompi_simulado(
    *,
    estado_consulta: int = 200,
    estado_wompi: str = "APPROVED",
    monto: int = 900_000,
    referencia: str = "tukit-ref-1",
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """Wompi en memoria: `GET /v1/transactions/{id}` devuelve la transaccion; todo lo demas es 404.

    Desde 9cb4c43 crear no llama a Wompi (firma los datos del widget), asi que `vistas` sirve para
    comprobar que nada salio al crear y que la consulta usa la API publica sin llaves."""
    vistas: list[httpx.Request] = []

    def _responder(peticion: httpx.Request) -> httpx.Response:
        vistas.append(peticion)
        if peticion.method == "GET" and peticion.url.path.startswith("/v1/transactions/"):
            datos = {
                "id": peticion.url.path.rsplit("/", 1)[1],
                "status": estado_wompi,
                "amount_in_cents": monto,
                "reference": referencia,
                "currency": MONEDA,
                "payment_method_type": "PSE",
            }
            return httpx.Response(estado_consulta, json={"data": datos})
        return httpx.Response(404)

    return httpx.MockTransport(_responder), vistas


async def test_crear_transaccion_manda_centavos_firma_de_integridad_y_ningun_dato_de_medio():
    """Los datos del widget llevan el monto en CENTAVOS, la moneda, la referencia, el correo y la
    firma de integridad recalculada con el secreto. Van al navegador, asi que solo la llave publica
    viaja: ni la privada ni los secretos, y nada de tarjeta (SG-03). Crear no sale a la red."""
    transporte, vistas = _wompi_simulado()
    async with httpx.AsyncClient(transport=transporte) as http:
        creada = await _wompi(cliente=http).crear_transaccion(
            referencia="tukit-ref-1",
            monto_centavos=900_000,
            correo_cliente="acudiente@example.test",
            metodo="tarjeta",
        )
        assert http.is_closed is False  # el cliente inyectado no se cierra: es de quien lo paso

    assert vistas == []
    assert creada == TransaccionCreada(
        referencia="tukit-ref-1",
        transaccion_id=None,
        estado=EstadoPago.INICIADO,
        url_redireccion=None,
        widget={
            "publicKey": LLAVE_PUBLICA,
            "currency": MONEDA,
            "amountInCents": 900_000,
            "reference": "tukit-ref-1",
            "signature": {"integrity": _sha256(f"tukit-ref-1900000COP{SECRETO_INTEGRIDAD}")},
            "customerData": {"email": "acudiente@example.test"},
        },
    )
    for secreto in (LLAVE_PRIVADA, SECRETO_INTEGRIDAD, SECRETO_EVENTOS):
        assert secreto not in repr(creada.widget)


async def test_crear_transaccion_pone_la_url_de_redireccion_en_el_widget():
    """La URL de retorno va en `redirectUrl` del widget (PSE se lleva la pestana entera) y no se
    devuelve como `url_redireccion`: el modal deja al acudiente en Tukit (c3dbbff, 4e51eaf)."""
    con_url = await _wompi().crear_transaccion(
        referencia="r1",
        monto_centavos=100,
        correo_cliente="a@example.test",
        metodo="pse",
        url_redireccion="https://tienda.example.test/kit/1",
    )
    assert con_url.widget["redirectUrl"] == "https://tienda.example.test/kit/1"
    assert con_url.url_redireccion is None

    sin_url = await _wompi().crear_transaccion(
        referencia="r2", monto_centavos=100, correo_cliente="a@example.test", metodo="pse"
    )
    assert "redirectUrl" not in sin_url.widget


async def test_si_wompi_falla_al_consultar_se_levanta_pasarela_caida_y_no_un_resultado():
    """Un 5xx o la red caida al consultar levantan `PasarelaCaida`; un 4xx, `TransaccionNoExiste`.
    Nunca se devuelve un evento que el aplicador pudiera tomar por bueno."""
    transporte, _ = _wompi_simulado(estado_consulta=503)
    async with httpx.AsyncClient(transport=transporte) as http:
        with pytest.raises(PasarelaCaida):
            await _wompi(cliente=http).consultar_transaccion(TRANSACCION)

    def _sin_red(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=peticion)

    async with httpx.AsyncClient(transport=httpx.MockTransport(_sin_red)) as http:
        with pytest.raises(PasarelaCaida):
            await _wompi(cliente=http).consultar_transaccion(TRANSACCION)

    transporte, _ = _wompi_simulado(estado_consulta=404)
    async with httpx.AsyncClient(transport=transporte) as http:
        with pytest.raises(TransaccionNoExiste):
            await _wompi(cliente=http).consultar_transaccion(TRANSACCION)


async def test_sin_cliente_inyectado_el_adaptador_abre_uno_propio_y_lo_cierra(monkeypatch):
    """Crear no abre ningun cliente; consultar abre uno propio por llamada y lo cierra."""
    transporte, vistas = _wompi_simulado()
    original = httpx.AsyncClient
    abiertos: list[httpx.AsyncClient] = []

    def _fabrica(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        cliente = original(*args, transport=transporte, **kwargs)
        abiertos.append(cliente)
        return cliente

    monkeypatch.setattr(httpx, "AsyncClient", _fabrica)
    creada = await _wompi().crear_transaccion(
        referencia="r", monto_centavos=1, correo_cliente="a@example.test", metodo="pse"
    )
    assert (creada.transaccion_id, abiertos, vistas) == (None, [], [])

    consultada = await _wompi().consultar_transaccion(TRANSACCION)

    assert consultada.transaccion_id == TRANSACCION
    assert len(vistas) == 1
    assert "authorization" not in vistas[0].headers  # el GET es publico: la llave privada no viaja
    assert len(abiertos) == 1
    assert abiertos[0].is_closed is True


# --- la pasarela falsa --------------------------------------------------------------------------


async def test_la_pasarela_falsa_numera_sus_transacciones_y_redirige_a_la_pagina_simulada():
    """Desde 9cb4c43 la falsa manda a `/pago/simulado` del mismo origen cuando hay URL de retorno,
    y recuerda el monto por referencia para esa pagina; sin URL no redirige."""
    falsa = PasarelaFalsa()
    primera = await falsa.crear_transaccion(
        referencia="r-1",
        monto_centavos=100,
        correo_cliente="a@example.test",
        metodo="pse",
        url_redireccion="https://tienda.example.test/kit/1",
    )
    segunda = await falsa.crear_transaccion(
        referencia="r-2", monto_centavos=200, correo_cliente="a@example.test", metodo="pse"
    )
    assert (primera.transaccion_id, segunda.transaccion_id) == ("falsa-1", "falsa-2")
    assert primera.estado == EstadoPago.INICIADO
    assert primera.url_redireccion == "https://tienda.example.test/pago/simulado?ref=r-1"
    assert segunda.url_redireccion is None
    assert (primera.widget, segunda.widget) == (None, None)
    assert falsa.montos == {"r-1": 100, "r-2": 200}
    assert falsa.creadas == [primera, segunda]


def test_el_evento_sintetico_de_la_falsa_tiene_la_forma_de_wompi_y_solo_lo_verifica_su_secreto():
    """El evento sintetico firma tambien el monto (7c2ae19): alterarlo invalida la firma."""
    falsa = PasarelaFalsa()
    evento = falsa.emitir_evento(
        referencia="r-1", transaccion_id="falsa-1", estado_wompi="DECLINED", monto_centavos=100
    )
    assert evento["id"] == "evt-falsa-1"
    assert evento["signature"]["properties"] == PROPIEDADES
    assert evento["data"]["transaction"]["amount_in_cents"] == 100
    assert falsa.verificar_firma(evento) is True
    assert PasarelaFalsa(secreto_eventos="otro_secreto").verificar_firma(evento) is False

    sin_checksum = {**evento, "signature": {"properties": evento["signature"]["properties"]}}
    assert falsa.verificar_firma(sin_checksum) is False
    assert falsa.verificar_firma({}) is False

    evento["data"]["transaction"]["amount_in_cents"] = 1
    assert falsa.verificar_firma(evento) is False


# --- pasarela_desde_entorno ---------------------------------------------------------------------

_LLAVES = {
    "WOMPI_LLAVE_PUBLICA": LLAVE_PUBLICA,
    "WOMPI_LLAVE_PRIVADA": LLAVE_PRIVADA,
    "WOMPI_SECRETO_EVENTOS": SECRETO_EVENTOS,
    "WOMPI_SECRETO_INTEGRIDAD": SECRETO_INTEGRIDAD,
}


@pytest.fixture
def entorno_limpio(monkeypatch) -> pytest.MonkeyPatch:
    for nombre in ("WOMPI_MODO", *_LLAVES):
        monkeypatch.delenv(nombre, raising=False)
    return monkeypatch


@pytest.mark.parametrize("modo", [None, "falso", "  FALSO "])
def test_sin_modo_sandbox_el_adaptador_es_el_falso_y_no_pide_llaves(entorno_limpio, modo):
    """La omision es el adaptador falso: sin red y sin llaves."""
    if modo is not None:
        entorno_limpio.setenv("WOMPI_MODO", modo)
    assert isinstance(pasarela_desde_entorno(), PasarelaFalsa)


def test_un_modo_desconocido_no_cobra_y_falla_ruidoso(entorno_limpio):
    """Un modo desconocido tampoco cobra: desde 2ad5f1d no cae al falso en silencio, no arranca."""
    entorno_limpio.setenv("WOMPI_MODO", "desconocido")
    with pytest.raises(RuntimeError, match="WOMPI_MODO='desconocido' no es valido"):
        pasarela_desde_entorno()


def test_modo_sandbox_sin_llaves_falla_ruidoso_y_nombra_las_que_faltan(entorno_limpio):
    """Una pasarela a medio configurar que cobrara de verdad es peor que una que no arranca."""
    entorno_limpio.setenv("WOMPI_MODO", "sandbox")
    with pytest.raises(RuntimeError) as error:
        pasarela_desde_entorno()
    for nombre in _LLAVES:
        assert nombre in str(error.value)

    for nombre in ("WOMPI_LLAVE_PUBLICA", "WOMPI_SECRETO_EVENTOS"):
        entorno_limpio.setenv(nombre, _LLAVES[nombre])
    with pytest.raises(RuntimeError) as parcial:
        pasarela_desde_entorno()
    assert "WOMPI_LLAVE_PRIVADA" in str(parcial.value)
    assert "WOMPI_SECRETO_INTEGRIDAD" in str(parcial.value)
    assert "WOMPI_LLAVE_PUBLICA" not in str(parcial.value)
    assert "WOMPI_SECRETO_EVENTOS" not in str(parcial.value)


def test_modo_sandbox_con_las_cuatro_llaves_arma_el_adaptador_real_contra_el_sandbox(entorno_limpio):
    entorno_limpio.setenv("WOMPI_MODO", "Sandbox")
    for nombre, valor in _LLAVES.items():
        entorno_limpio.setenv(nombre, valor)

    pasarela = pasarela_desde_entorno()

    assert isinstance(pasarela, WompiSandbox)
    assert (pasarela.llave_publica, pasarela.llave_privada) == (LLAVE_PUBLICA, LLAVE_PRIVADA)
    assert (pasarela.secreto_eventos, pasarela.secreto_integridad) == (SECRETO_EVENTOS, SECRETO_INTEGRIDAD)
    assert pasarela.base == URL_SANDBOX != URL_PRODUCCION
    assert pasarela.verificar_firma(_evento_wompi()) is True


# --- el webhook de punta a punta con el adaptador de Wompi (montos, firma, idempotencia) ---------


class CatalogoFalso:
    async def resolver(self, sku: str):
        return uuid.uuid5(uuid.NAMESPACE_OID, sku), 4500


@pytest_asyncio.fixture
async def flujo() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio, list[httpx.Request]]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    transporte, vistas = _wompi_simulado()
    wompi = httpx.AsyncClient(transport=transporte)
    app.state.motor = motor
    app.state.catalogo = CatalogoFalso()
    app.state.pasarela = _wompi(cliente=wompi)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor, vistas
    await wompi.aclose()
    await engine.dispose()


async def _orden_con_pago(http: httpx.AsyncClient) -> tuple[str, str, dict[str, Any]]:
    """Crea una orden de 2 x $4.500 y la manda a cobrar. Devuelve (pedido_id, referencia, pago)."""
    orden = {
        "usuario_id": "22222222-2222-5222-8222-222222222222",
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 2, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }
    pedido_id = (await http.post("/v1/ordenes", json=orden)).json()["pedido_id"]
    pago = await http.post(
        f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": "acudiente@example.test", "metodo": "pse"}
    )
    assert pago.status_code == 201
    return pedido_id, pago.json()["referencia_wompi"], pago.json()


async def test_el_cobro_sale_a_wompi_en_centavos_y_se_persiste_en_pesos(flujo):
    """Total $9.000 COP: el widget lleva 900.000 centavos con su firma de integridad y nada sale a
    Wompi al crear (9cb4c43); en la base el monto del pago queda en pesos, sin transaccion todavia
    (llega con el webhook o al sincronizar). La respuesta no trae llaves privadas ni secretos."""
    http, motor, vistas = flujo
    pedido_id, referencia, respuesta = await _orden_con_pago(http)

    assert vistas == []
    widget = respuesta["widget"]
    assert widget["amountInCents"] == 900_000
    assert widget["reference"] == referencia == f"tukit-{pedido_id}-1"
    assert widget["signature"]["integrity"] == _sha256(f"{referencia}900000COP{SECRETO_INTEGRIDAD}")
    for secreto in (LLAVE_PRIVADA, SECRETO_INTEGRIDAD, SECRETO_EVENTOS):
        assert secreto not in str(respuesta)

    async with motor.sesion() as db:
        pago = (await db.execute(select(Pago))).scalar_one()
    assert (pago.monto, pago.estado, pago.transaccion_wompi) == (9000, EstadoPago.INICIADO.value, None)


async def test_un_evento_con_el_monto_alterado_se_ignora_y_el_pedido_sigue_pendiente(flujo):
    """Alguien reenvia el evento aprobado pero con otro monto: la firma ya no cuadra, no se marca
    el evento como procesado (el legitimo todavia puede llegar) y el pedido no se mueve."""
    http, motor, _ = flujo
    pedido_id, referencia, _ = await _orden_con_pago(http)
    falsificado = _evento_wompi(referencia=referencia, monto=900_000)
    falsificado["data"]["transaction"]["amount_in_cents"] = 100

    respuesta = await http.post("/v1/webhooks/wompi", json=falsificado)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ignorado", "motivo": "firma_invalida"}
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    async with motor.sesion() as db:
        assert await db.scalar(select(func.count()).select_from(BandejaSalida)) == 0

    legitimo = await http.post("/v1/webhooks/wompi", json=_evento_wompi(referencia=referencia))
    assert legitimo.json()["estado"] == "aplicado"


async def test_el_mismo_evento_repetido_mueve_el_pedido_y_la_bandeja_una_sola_vez(flujo, monkeypatch):
    """Wompi reintenta: la segunda entrega responde `repetido` (200), no re-aplica, no duplica el
    aviso `pedido_pagado` y no cuenta dos veces el pago aprobado."""
    from tukit_comercio.routers import comercio as router_comercio

    conteo: list[str] = []
    monkeypatch.setattr(router_comercio, "contar_pago_aprobado", lambda: conteo.append("pago"))
    http, motor, _ = flujo
    pedido_id, referencia, _ = await _orden_con_pago(http)
    evento = _evento_wompi(referencia=referencia, **{"id": "evt-wompi-ficticio-1"})
    clave = f"{TRANSACCION}:APPROVED"  # el `id` del sobre no cuenta desde 7c2ae19

    primera = await http.post("/v1/webhooks/wompi", json=evento)
    segunda = await http.post("/v1/webhooks/wompi", json=evento)

    assert primera.json() == {
        "estado": "aplicado",
        "evento_id": clave,
        "pago_estado": "aprobado",
        "pedido_transicionado": True,
    }
    assert segunda.status_code == 200
    assert segunda.json() == {"estado": "repetido", "evento_id": clave}
    assert conteo == ["pago"]
    pedido = (await http.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PAGADO.value
    assert pedido["pago"] == {
        "referencia_wompi": referencia,
        "metodo": "pse",
        "estado": "aprobado",
        "monto": 9000,
    }
    async with motor.sesion() as db:
        avisos = list(await db.scalars(select(BandejaSalida)))
    assert len(avisos) == 1
    assert avisos[0].tipo == "pedido_pagado"
    assert avisos[0].agregado_id == uuid.UUID(pedido_id)
    assert avisos[0].carga["total"] == 9000
