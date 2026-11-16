"""Las reglas puras de como se interpreta un evento de bandeja de salida.

Son el nucleo del repartidor sin base ni red: que plantilla le toca a cada tipo
de evento, de donde sale el destinatario cuando la carga ya lo trae, y como se
arma el cuerpo del aviso (codigo del pedido, enlace) sin filtrar contacto. El
worker (`repartidor.py`) las orquesta; aqui se prueban solas (ADR 0019).
"""

from __future__ import annotations

import uuid

import pytest
from tukit_operacion.dominio.reparto import (
    datos_plantilla,
    destinatario_en_carga,
    plantilla_para,
)


def test_plantilla_por_tipo_conocido():
    assert plantilla_para("kits_publicados") == "kits_publicados"
    assert plantilla_para("pedido_pagado") == "pedido_pagado"
    assert plantilla_para("incidencia") == "incidencia"


def test_plantilla_tipo_desconocido_es_none():
    # Un tipo que el repartidor no maneja: no nos toca, no es un fallo.
    assert plantilla_para("algo_raro") is None


def test_destinatario_de_la_carga_cuando_el_evento_lo_trae():
    assert destinatario_en_carga("pedido_pagado", {"usuario_id": "u-1"}) == "u-1"
    assert destinatario_en_carga("incidencia", {"usuario_id": "u-2"}) == "u-2"


def test_destinatario_none_si_la_carga_no_trae_usuario():
    assert destinatario_en_carga("pedido_pagado", {}) is None
    assert destinatario_en_carga("pedido_pagado", None) is None


def test_kits_publicados_no_saca_destinatario_de_la_carga():
    # kits_publicados lo lee de trabajo_pipeline (eso es del worker), nunca de la
    # carga, aunque venga poblada.
    assert destinatario_en_carga("kits_publicados", {"usuario_id": "u-1"}) is None


def test_los_datos_no_llevan_turno():
    # "Turno" era el id del agregado: en un evento de pedido, el mismo codigo repetido.
    agregado = uuid.UUID("abcdef12-0000-4000-8000-000000000000")
    datos = datos_plantilla("pedido_pagado", agregado, {"pedido_id": str(agregado)}, base_web="https://tukit.co")
    assert "turno" not in datos and datos["pedido"] == "ABCDEF12"


def test_kits_publicados_arma_enlace_de_precompra_con_el_agregado():
    agregado = uuid.uuid4()
    datos = datos_plantilla("kits_publicados", agregado, {}, base_web="https://tukit.co")
    assert datos["enlace"] == f"https://tukit.co/kits/{agregado}"


def test_aviso_de_pedido_lleva_codigo_y_enlace_a_su_linea_de_tiempo():
    agregado = uuid.uuid4()
    pedido = uuid.UUID("11112222-0000-4000-8000-000000000000")
    datos = datos_plantilla(
        "pedido_pagado", agregado, {"pedido_id": str(pedido), "total": 609343}, base_web="https://tukit.co"
    )
    assert datos["pedido"] == "11112222"
    assert datos["enlace"] == f"https://tukit.co/pedidos/{pedido}"
    assert datos["total"] == 609343


def test_pedido_id_invalido_no_arma_enlace():
    datos = datos_plantilla("pedido_pagado", uuid.uuid4(), {"pedido_id": "../x"}, base_web="https://tukit.co")
    assert "enlace" not in datos and "pedido" not in datos


def test_cancelado_lleva_si_hay_reembolso_y_preparacion_si_retoma():
    cancelado = datos_plantilla("pedido_cancelado", uuid.uuid4(), {"reembolso": True}, base_web="https://tukit.co")
    assert cancelado["reembolso"] is True
    assert datos_plantilla("pedido_cancelado", uuid.uuid4(), {}, base_web="https://tukit.co")["reembolso"] is False
    retoma = datos_plantilla("pedido_en_preparacion", uuid.uuid4(), {"retoma": True}, base_web="https://tukit.co")
    assert retoma["retoma"] is True


# Los avisos de logistica: el back-office mueve el pedido y Comercio escribe el
# evento con el usuario en la carga, igual que `pedido_pagado`.
AVISOS_DE_LOGISTICA = ("pedido_despachado", "pedido_en_reparto", "pedido_entregado")


@pytest.mark.parametrize("tipo", [*AVISOS_DE_LOGISTICA, "pedido_en_preparacion", "pedido_cancelado"])
def test_los_avisos_de_pedido_tienen_plantilla_y_usuario_en_carga(tipo):
    assert plantilla_para(tipo) == tipo
    assert destinatario_en_carga(tipo, {"usuario_id": "u-3"}) == "u-3"


def test_despachado_lleva_el_nombre_del_repartidor():
    datos = datos_plantilla(
        "pedido_despachado", uuid.uuid4(), {"repartidor": " Luis "}, base_web="https://tukit.co"
    )
    assert datos["repartidor"] == "Luis"


def test_despachado_sin_nombre_cae_al_texto_por_omision():
    for carga in ({}, {"repartidor": ""}, {"repartidor": None}, None):
        datos = datos_plantilla("pedido_despachado", uuid.uuid4(), carga, base_web="https://tukit.co")
        assert datos["repartidor"] == "nuestro repartidor"


def test_solo_el_despacho_lleva_repartidor():
    datos = datos_plantilla(
        "pedido_en_reparto", uuid.uuid4(), {"repartidor": "Luis"}, base_web="https://tukit.co"
    )
    assert "repartidor" not in datos


def test_textos_de_los_avisos_de_logistica():
    from tukit_operacion.notificador import texto_de

    assert (
        texto_de("pedido_despachado", {"pedido": "ABCD1234", "repartidor": "Luis"})
        == "Tu pedido ABCD1234 salió y va con Luis."
    )
    assert texto_de("pedido_en_reparto", {"pedido": "ABCD1234"}) == "Tu pedido ABCD1234 llega hoy."
    assert (
        texto_de("pedido_entregado", {"pedido": "ABCD1234"})
        == "Tu pedido ABCD1234 fue entregado. ¡Gracias por confiar en Tukit!"
    )


# --- kits_publicados con varias listas del hogar (hermanos, 13-nov) -----------


def test_lugares_de_mismo_colegio_dos_grados():
    from tukit_operacion.dominio.reparto import lugares_de

    listas = [{"colegio_id": "c1", "grado": "Septimo"}, {"colegio_id": "c1", "grado": "Jardin"}]
    assert lugares_de(listas, {"c1": "Colegio X"}) == "Colegio X, grados Septimo y Jardin"


def test_lugares_de_dos_colegios():
    from tukit_operacion.dominio.reparto import lugares_de

    listas = [{"colegio_id": "a", "grado": "3"}, {"colegio_id": "b", "grado": "5"}]
    nombres = {"a": "Colegio A", "b": "Colegio B"}
    assert lugares_de(listas, nombres) == "Colegio A, grado 3 y Colegio B, grado 5"
    # Tres colegios: comas y una "y" al final, sin truncar.
    tres = [*listas, {"colegio_id": "c", "grado": "1"}]
    assert (
        lugares_de(tres, {"a": "Colegio A", "b": "Colegio B", "c": "Colegio C"})
        == "Colegio A, grado 3, Colegio B, grado 5 y Colegio C, grado 1"
    )
    # Un colegio sin nombre resuelto conserva su grado.
    assert lugares_de(listas, {"a": "Colegio A"}) == "Colegio A, grado 3 y grado 5"


def test_evento_viejo_sin_listas_sigue_igual():
    agregado = uuid.uuid4()
    carga = {"colegio_id": "c1", "grado": "3"}
    viejo = datos_plantilla(
        "kits_publicados", agregado, carga, base_web="https://tukit.co", colegio_nombre="Colegio X"
    )
    assert viejo["lugar"] == "Colegio X, grado 3"
    con_mapa = datos_plantilla(
        "kits_publicados", agregado, carga, base_web="https://tukit.co", colegios={"c1": "Colegio X"}
    )
    assert con_mapa["lugar"] == "Colegio X, grado 3"


def test_kits_publicados_con_listas_nombra_todas():
    carga = {
        "colegio_id": "c1",
        "grado": "Septimo",
        "listas": [{"colegio_id": "c1", "grado": "Septimo"}, {"colegio_id": "c1", "grado": "Jardin"}],
    }
    datos = datos_plantilla(
        "kits_publicados", uuid.uuid4(), carga, base_web="https://tukit.co", colegios={"c1": "Colegio X"}
    )
    assert datos["lugar"] == "Colegio X, grados Septimo y Jardin"
    assert datos["listas"] == ["Colegio X, grado Septimo", "Colegio X, grado Jardin"]
