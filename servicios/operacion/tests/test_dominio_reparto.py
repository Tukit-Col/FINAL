"""Las reglas puras de como se interpreta un evento de bandeja de salida.

Son el nucleo del repartidor sin base ni red: que plantilla le toca a cada tipo
de evento, de donde sale el destinatario cuando la carga ya lo trae, y como se
arma el cuerpo del aviso (turno, enlace de pre-compra) sin filtrar contacto. El
worker (`repartidor.py`) las orquesta; aqui se prueban solas (ADR 0019).
"""

from __future__ import annotations

import uuid

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


def test_datos_llevan_turno_corto_del_agregado():
    agregado = uuid.UUID("abcdef12-0000-4000-8000-000000000000")
    datos = datos_plantilla("pedido_pagado", agregado, {}, base_web="https://tukit.co")
    assert datos["turno"] == "ABCDEF12"


def test_kits_publicados_arma_enlace_de_precompra_con_el_agregado():
    agregado = uuid.uuid4()
    datos = datos_plantilla("kits_publicados", agregado, {}, base_web="https://tukit.co")
    assert datos["enlace"] == f"https://tukit.co/kits/{agregado}"


def test_pedido_pagado_no_lleva_enlace_pero_si_pedido_corto():
    agregado = uuid.uuid4()
    pedido = uuid.UUID("11112222-0000-4000-8000-000000000000")
    datos = datos_plantilla(
        "pedido_pagado", agregado, {"pedido_id": str(pedido)}, base_web="https://tukit.co"
    )
    assert "enlace" not in datos
    assert datos["pedido"] == "11112222"
