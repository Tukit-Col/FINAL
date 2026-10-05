"""El guard del avance de un pedido por la cadena de entrega, como dominio puro.

Que una transicion sea legal lo responde la tabla `TRANSICIONES_PEDIDO`; aqui se
prueba lo que la tabla no expresa: que el back-office solo mueve lo que tiene
boton (`AVANCES_DE_LOGISTICA`), que un despacho de reparto propio exige nombre y
celular del repartidor, y que una incidencia exige su tipo (y nota si es
`otro`). Tambien que avisos salen y que entradas se guardan por destino.
"""

from __future__ import annotations

import pytest
from tukit_comercio.dominio.despacho import (
    AVANCES_DE_LOGISTICA,
    TIPOS_INCIDENCIA,
    preparar_avance,
    tipo_aviso,
    validar_avance,
)
from tukit_comercio.modelos import TRANSICIONES_PEDIDO

DESPACHO = {"repartidor_nombre": "Luis", "repartidor_celular": "3001234567"}


def test_la_matriz_de_logistica_es_subconjunto_de_la_tabla():
    # Si alguien agrega un boton que la maquina de estados no permite, esto
    # falla antes de que llegue a produccion.
    for desde, destinos in AVANCES_DE_LOGISTICA.items():
        assert destinos <= TRANSICIONES_PEDIDO[desde], desde


def test_avance_legal_devuelve_none():
    assert validar_avance("pagado", "en_preparacion") is None


def test_transicion_ilegal_se_rechaza_por_la_tabla():
    # pagado -> entregado se salta pasos: la tabla lo prohibe.
    rechazo = validar_avance("pagado", "entregado")
    assert rechazo is not None
    assert rechazo.razon == "transicion_invalida"
    assert rechazo.estado == 409


@pytest.mark.parametrize(
    ("actual", "destino"),
    [
        # Legales en la tabla, pero no le tocan al back-office: el pago lo pone
        # el webhook, y el barredor y el retracto cancelan por su cuenta.
        ("pendiente_pago", "pagado"),
        ("pendiente_pago", "cancelado"),
        ("pagado", "cancelado"),
    ],
)
def test_transiciones_fuera_de_la_matriz_se_rechazan(actual, destino):
    rechazo = validar_avance(actual, destino)
    assert rechazo is not None
    assert rechazo.razon == "transicion_invalida"
    assert rechazo.estado == 409


def test_destino_desconocido_se_rechaza():
    rechazo = validar_avance("pagado", "teletransportado")
    assert rechazo is not None
    assert rechazo.razon == "destino_invalido"
    assert rechazo.estado == 422


def test_estado_actual_desconocido_no_lanza():
    rechazo = validar_avance("raro", "en_preparacion")
    assert rechazo is not None
    assert rechazo.razon == "transicion_invalida"


@pytest.mark.parametrize(
    ("entradas", "campo"),
    [
        ({}, "repartidor_nombre"),
        ({"repartidor_celular": "3001234567"}, "repartidor_nombre"),
        ({"repartidor_nombre": "Luis"}, "repartidor_celular"),
        ({"repartidor_nombre": "   ", "repartidor_celular": "3001234567"}, "repartidor_nombre"),
        ({"repartidor_nombre": "Luis", "repartidor_celular": "  "}, "repartidor_celular"),
    ],
)
def test_despachar_sin_repartidor_completo_se_rechaza(entradas, campo):
    rechazo = validar_avance("en_preparacion", "despachado", **entradas)
    assert rechazo is not None
    assert rechazo.razon == "despacho_incompleto"
    assert rechazo.estado == 422
    assert rechazo.campo == campo


def test_despachar_con_nombre_y_celular_pasa():
    assert validar_avance("en_preparacion", "despachado", **DESPACHO) is None


def test_incidencia_sin_tipo_se_rechaza():
    rechazo = validar_avance("en_reparto", "incidencia")
    assert rechazo is not None
    assert (rechazo.razon, rechazo.estado, rechazo.campo) == ("incidencia_sin_tipo", 422, "tipo_incidencia")


def test_incidencia_con_tipo_desconocido_se_rechaza():
    rechazo = validar_avance("en_reparto", "incidencia", tipo_incidencia="se_lo_comio_el_perro")
    assert rechazo is not None
    assert (rechazo.razon, rechazo.campo) == ("tipo_incidencia_invalido", "tipo_incidencia")


def test_incidencia_otro_sin_nota_se_rechaza():
    rechazo = validar_avance("en_reparto", "incidencia", tipo_incidencia="otro", nota="  ")
    assert rechazo is not None
    assert (rechazo.razon, rechazo.campo) == ("incidencia_sin_nota", "nota")


def test_incidencia_otro_con_nota_pasa():
    assert validar_avance("en_reparto", "incidencia", tipo_incidencia="otro", nota="Perro bravo") is None


@pytest.mark.parametrize("tipo", TIPOS_INCIDENCIA[:-1])
def test_incidencia_con_tipo_conocido_no_exige_nota(tipo):
    assert validar_avance("despachado", "incidencia", tipo_incidencia=tipo) is None


@pytest.mark.parametrize(
    ("destino", "aviso"),
    [
        ("despachado", "pedido_despachado"),
        ("en_reparto", "pedido_en_reparto"),
        ("entregado", "pedido_entregado"),
        ("incidencia", "incidencia"),
        ("en_preparacion", None),
        ("cancelado", None),
        ("teletransportado", None),
    ],
)
def test_tipo_aviso_por_destino(destino, aviso):
    assert tipo_aviso(destino) == aviso


def test_preparar_despacho_guarda_el_repartidor_limpio():
    avance = preparar_avance("despachado", repartidor_nombre=" Luis ", repartidor_celular=" 300 ", nota="")
    assert avance.repartidor_nombre == "Luis"
    assert avance.repartidor_celular == "300"
    assert avance.nota is None
    assert avance.tipo_incidencia is None
    assert avance.aviso == "pedido_despachado"


def test_preparar_otro_destino_descarta_repartidor_y_tipo():
    # Un repartidor que llega con un `en_reparto` no debe pisar el del envio.
    avance = preparar_avance(
        "en_reparto", repartidor_nombre="Otro", repartidor_celular="1", tipo_incidencia="otro", nota=" ok "
    )
    assert avance.repartidor_nombre is None
    assert avance.repartidor_celular is None
    assert avance.tipo_incidencia is None
    assert avance.nota == "ok"


def test_preparar_incidencia_guarda_tipo_y_nota():
    avance = preparar_avance("incidencia", tipo_incidencia="rechazado", nota="No lo quiso")
    assert (avance.tipo_incidencia, avance.nota, avance.aviso) == ("rechazado", "No lo quiso", "incidencia")
