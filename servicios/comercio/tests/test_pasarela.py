"""Las firmas de la pasarela, contra vectores conocidos.

Las formulas estan verificadas contra docs.wompi.co. Se fijan aqui como
funciones puras para que un cambio accidental en el orden de concatenacion o en
lo que se firma rompa una prueba y no un cobro real.
"""

from __future__ import annotations

import hashlib
import urllib.parse

import httpx
import pytest

from tukit_comercio.modelos import EstadoPago

from tukit_comercio.pasarela import (
    URL_CHECKOUT,
    PasarelaCaida,
    PasarelaFalsa,
    TransaccionNoExiste,
    WompiSandbox,
    firma_evento,
    firma_integridad,
    pasarela_desde_entorno,
    url_checkout,
)


def test_firma_integridad_es_sha256_de_la_concatenacion():
    # SHA256("<referencia><monto_centavos><moneda><secreto>"), monto en centavos.
    esperado = hashlib.sha256(b"ref-1250000COPsecreto").hexdigest()
    assert firma_integridad("ref-1", 250000, "secreto") == esperado


def test_firma_integridad_usa_centavos_no_pesos():
    a = firma_integridad("ref-1", 250000, "secreto")
    b = firma_integridad("ref-1", 2500, "secreto")
    assert a != b


def test_firma_evento_concatena_propiedades_timestamp_y_secreto_al_final():
    evento = {
        "timestamp": 1700000000,
        "data": {"transaction": {"id": "txn-9", "status": "APPROVED"}},
        "signature": {"properties": ["transaction.id", "transaction.status"]},
    }
    esperado = hashlib.sha256(b"txn-9APPROVED1700000000eventos").hexdigest()
    assert firma_evento(evento, "eventos") == esperado


def test_la_pasarela_falsa_verifica_su_propia_firma():
    falsa = PasarelaFalsa()
    evento = falsa.emitir_evento(referencia="ref-1", transaccion_id="txn-1", estado_wompi="APPROVED", monto_centavos=500)
    assert falsa.verificar_firma(evento) is True

    # Alterar el cuerpo firmado invalida la firma: es exactamente lo que protege.
    evento["data"]["transaction"]["status"] = "DECLINED"
    assert falsa.verificar_firma(evento) is False


def test_parsear_evento_saca_solo_id_referencia_transaccion_y_estado():
    falsa = PasarelaFalsa()
    evento = falsa.emitir_evento(referencia="ref-7", transaccion_id="txn-7", estado_wompi="APPROVED", monto_centavos=500)
    datos = falsa.parsear_evento(evento)
    assert datos.referencia == "ref-7"
    assert datos.transaccion_id == "txn-7"
    assert datos.evento_id == "txn-7:APPROVED"


def test_url_checkout_lleva_parametros_y_firma():
    url = url_checkout(
        llave_publica="pub_test_x",
        referencia="tukit-abc",
        monto_centavos=900000,
        secreto_integridad="test_integrity_s",
        url_redireccion="http://localhost:3000/pago/resultado",
        correo="ana@ejemplo.com",
    )
    partes = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(partes.query))
    assert url.startswith("https://checkout.wompi.co/p/?")
    assert q["public-key"] == "pub_test_x"
    assert q["currency"] == "COP"
    assert q["amount-in-cents"] == "900000"
    assert q["reference"] == "tukit-abc"
    assert q["signature:integrity"] == firma_integridad("tukit-abc", 900000, "test_integrity_s")
    assert q["redirect-url"] == "http://localhost:3000/pago/resultado"
    assert q["customer-data:email"] == "ana@ejemplo.com"


def test_url_checkout_omite_redirect_url_si_no_se_pasa():
    url = url_checkout(
        llave_publica="pub_test_x",
        referencia="tukit-abc",
        monto_centavos=100,
        secreto_integridad="test_integrity_s",
        url_redireccion=None,
        correo="ana@ejemplo.com",
    )
    assert "redirect-url" not in dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


async def test_wompi_sandbox_crear_no_sale_a_la_red():
    def _falla(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no debe salir a la red")

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(_falla))
    pasarela = WompiSandbox(
        llave_publica="pub_test_x",
        llave_privada="prv_test_x",
        secreto_eventos="test_events_x",
        secreto_integridad="test_integrity_x",
        cliente=cliente,
    )
    creada = await pasarela.crear_transaccion(
        referencia="tukit-1",
        monto_centavos=100,
        correo_cliente="a@b.co",
        metodo="pse",
        url_redireccion="http://localhost:3000/pago/resultado",
    )
    await cliente.aclose()
    assert creada.transaccion_id is None
    assert creada.url_redireccion.startswith(URL_CHECKOUT)


async def test_pasarela_falsa_manda_a_la_pagina_simulada():
    falsa = PasarelaFalsa()
    creada = await falsa.crear_transaccion(
        referencia="tukit-1",
        monto_centavos=100,
        correo_cliente="a@b.co",
        metodo="pse",
        url_redireccion="http://localhost:3000/pago/resultado",
    )
    assert creada.url_redireccion == "http://localhost:3000/pago/simulado?ref=tukit-1"
    assert falsa.montos == {"tukit-1": 100}


async def test_pasarela_falsa_sin_url_no_redirige():
    creada = await PasarelaFalsa().crear_transaccion(
        referencia="tukit-1", monto_centavos=100, correo_cliente="a@b.co", metodo="pse"
    )
    assert creada.url_redireccion is None


_LLAVES_PRUEBA = {
    "WOMPI_LLAVE_PUBLICA": "pub_test_x",
    "WOMPI_LLAVE_PRIVADA": "prv_test_x",
    "WOMPI_SECRETO_EVENTOS": "test_events_x",
    "WOMPI_SECRETO_INTEGRIDAD": "test_integrity_x",
}


@pytest.mark.parametrize(
    "variable,valor",
    [
        ("WOMPI_LLAVE_PUBLICA", "pub_prod_x"),
        ("WOMPI_LLAVE_PRIVADA", "prv_prod_x"),
        ("WOMPI_SECRETO_EVENTOS", "prod_events_x"),
        ("WOMPI_SECRETO_INTEGRIDAD", "prod_integrity_x"),
    ],
)
def test_sandbox_rechaza_llaves_que_no_son_de_prueba(monkeypatch, variable, valor):
    monkeypatch.setenv("WOMPI_MODO", "sandbox")
    for nombre, v in _LLAVES_PRUEBA.items():
        monkeypatch.setenv(nombre, v)
    monkeypatch.setenv(variable, valor)
    with pytest.raises(RuntimeError, match=variable):
        pasarela_desde_entorno()


def test_sandbox_acepta_llaves_de_prueba(monkeypatch):
    monkeypatch.setenv("WOMPI_MODO", "sandbox")
    for nombre, v in _LLAVES_PRUEBA.items():
        monkeypatch.setenv(nombre, v)
    assert isinstance(pasarela_desde_entorno(), WompiSandbox)


def test_parsear_evento_usa_transaccion_y_estado_como_clave():
    ev = PasarelaFalsa().emitir_evento(
        referencia="tukit-1", transaccion_id="tx-9", estado_wompi="APPROVED", monto_centavos=500
    )
    datos = PasarelaFalsa().parsear_evento(ev)
    assert datos.evento_id == "tx-9:APPROVED"
    assert datos.monto_centavos == 500


def _wompi_con(manejador) -> WompiSandbox:
    return WompiSandbox(cliente=httpx.AsyncClient(transport=httpx.MockTransport(manejador)))


async def test_wompi_consultar_traduce_estado_monto_y_metodo():
    def _ok(peticion: httpx.Request) -> httpx.Response:
        assert peticion.method == "GET"
        assert peticion.url.path == "/v1/transactions/tx-1"
        assert "authorization" not in peticion.headers
        return httpx.Response(
            200,
            json={"data": {"id": "tx-1", "reference": "tukit-1", "status": "APPROVED",
                           "amount_in_cents": 900000, "payment_method_type": "CARD"}},
        )

    ev = await _wompi_con(_ok).consultar_transaccion("tx-1")
    assert (ev.evento_id, ev.referencia, ev.estado, ev.monto_centavos, ev.metodo) == (
        "tx-1:APPROVED", "tukit-1", EstadoPago.APROBADO, 900000, "tarjeta",
    )


async def test_wompi_consultar_metodo_desconocido_es_none():
    def _ok(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"id": "tx-1", "reference": "r", "status": "PENDING",
                           "amount_in_cents": 1, "payment_method_type": "BANCOLOMBIA_TRANSFER"}},
        )

    ev = await _wompi_con(_ok).consultar_transaccion("tx-1")
    assert ev.metodo is None


async def test_wompi_consultar_404_es_transaccion_no_existe():
    wompi = _wompi_con(lambda p: httpx.Response(404, json={}))
    with pytest.raises(TransaccionNoExiste):
        await wompi.consultar_transaccion("tx-x")


async def test_wompi_consultar_500_es_pasarela_caida():
    wompi = _wompi_con(lambda p: httpx.Response(500))
    with pytest.raises(PasarelaCaida):
        await wompi.consultar_transaccion("tx-x")


async def test_wompi_consultar_error_de_red_es_pasarela_caida():
    def _cae(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    with pytest.raises(PasarelaCaida):
        await _wompi_con(_cae).consultar_transaccion("tx-x")


async def test_falsa_consultar_descompone_el_id():
    p = PasarelaFalsa()
    await p.crear_transaccion(referencia="tukit-1", monto_centavos=700, correo_cliente="a@b.co", metodo="pse")
    ev = await p.consultar_transaccion("falsa-DECLINED-tukit-1")
    assert (ev.referencia, ev.estado, ev.monto_centavos, ev.metodo) == (
        "tukit-1", EstadoPago.RECHAZADO, 700, "pse",
    )


async def test_falsa_consultar_formato_invalido_o_referencia_desconocida():
    p = PasarelaFalsa()
    with pytest.raises(TransaccionNoExiste):
        await p.consultar_transaccion("basura")
    with pytest.raises(TransaccionNoExiste):
        await p.consultar_transaccion("falsa-APPROVED-tukit-nada")
