"""Las firmas de la pasarela, contra vectores conocidos.

Las formulas estan verificadas contra docs.wompi.co. Se fijan aqui como
funciones puras para que un cambio accidental en el orden de concatenacion o en
lo que se firma rompa una prueba y no un cobro real.
"""

from __future__ import annotations

import hashlib

from tukit_comercio.pasarela import PasarelaFalsa, firma_evento, firma_integridad


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
    evento = falsa.emitir_evento(referencia="ref-1", transaccion_id="txn-1", estado_wompi="APPROVED")
    assert falsa.verificar_firma(evento) is True

    # Alterar el cuerpo firmado invalida la firma: es exactamente lo que protege.
    evento["data"]["transaction"]["status"] = "DECLINED"
    assert falsa.verificar_firma(evento) is False


def test_parsear_evento_saca_solo_id_referencia_transaccion_y_estado():
    falsa = PasarelaFalsa()
    evento = falsa.emitir_evento(referencia="ref-7", transaccion_id="txn-7", estado_wompi="APPROVED")
    datos = falsa.parsear_evento(evento)
    assert datos.referencia == "ref-7"
    assert datos.transaccion_id == "txn-7"
    assert datos.evento_id
