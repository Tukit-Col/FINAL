"""La bandeja de salida de comercio con el repartidor de operacion corriendo.

Un pago aprobado escribe `pedido_pagado` en `bandeja_salida` en la MISMA
transaccion que pasa el pedido a `pagado` (QA:918), con el `correlacion_id` de
la peticion; el repartidor lo drena y operacion manda el aviso. La misma
transaccion se comprueba con `xmin`: Postgres sella cada fila con la transaccion
que la escribio, asi que el evento y el pedido tienen que traer el mismo. El
repartidor, al publicar, reescribe la fila del evento y cambia su `xmin`; si
llega antes que la consulta, se repite con un pedido nuevo.

Del lado de operacion el `correlacion_id` no se puede seguir: la notificacion
no lo guarda y el repartidor no lo registra (Tukit-QA, H-C-09).
"""

from __future__ import annotations

import time

import httpx
import pytest
from stack_vivo import logs_del_stack, orden_pagada

pytestmark = pytest.mark.integracion

_TOPE_REPARTO_SEGUNDOS = 20.0  # cuatro pasadas del repartidor (`--intervalo` 5 s)

_EVENTO_Y_PEDIDO = """
    select b.tipo, b.carga, b.publicado_en, b.xmin::text, p.xmin::text, p.estado
    from bandeja_salida b join pedido p on p.id::text = b.agregado_id::text
    where b.agregado_id::text = :p
"""


@pytest.mark.nfr("NFR-DIS-05")
async def test_el_pago_aprobado_escribe_el_evento_en_la_misma_transaccion(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, correlacion_id: str, record_property
):
    for intento in range(1, 4):  # noqa: B007 (se anota tras el bucle)
        pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
        filas = await consultar("comercio", _EVENTO_Y_PEDIDO, p=pedido)
        if filas and filas[0][2] is None:
            break
    else:
        pytest.fail("el repartidor publico el evento antes de poder leer su xmin en 3 intentos")

    record_property("intentos", intento)
    assert len(filas) == 1, filas
    tipo, carga, _, xmin_evento, xmin_pedido, estado = filas[0]
    assert (tipo, estado) == ("pedido_pagado", "pagado")
    assert carga["pedido_id"] == pedido
    assert carga["correlacion_id"] == correlacion_id
    assert xmin_evento == xmin_pedido


@pytest.mark.nfr("NFR-DIS-05")
async def test_el_repartidor_drena_el_evento_y_operacion_avisa_una_vez(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, record_property
):
    usuario_id = sesiones["acudiente"]["usuario_id"]
    pedido = orden_pagada(cliente, usuario_id, producto)
    inicio = time.monotonic()
    avisos: list = []
    publicado = None
    while time.monotonic() - inicio < _TOPE_REPARTO_SEGUNDOS:
        publicado = (await consultar("comercio", _EVENTO_Y_PEDIDO, p=pedido))[0][2]
        avisos = await consultar(
            "operacion",
            "select canal, estado, datos from notificacion "
            "where plantilla = 'pedido_pagado' and usuario_id::text = :u and datos->>'pedido' = :corto",
            u=usuario_id,
            corto=pedido[:8].upper(),
        )
        if publicado is not None and avisos:
            break
        time.sleep(0.5)
    segundos = time.monotonic() - inicio

    record_property("segundos_hasta_el_aviso", round(segundos, 2))
    assert publicado is not None, f"el evento sigue sin publicar a los {_TOPE_REPARTO_SEGUNDOS:.0f} s"
    assert len(avisos) == 1, avisos
    canal, estado, _ = avisos[0]
    assert (canal, estado) == ("correo", "enviada")


@pytest.mark.nfr("NFR-DIS-05")
def test_el_correlacion_id_del_borde_llega_a_los_logs_de_la_puerta_y_de_comercio(
    cliente: httpx.Client, sesiones: dict, producto: dict, correlacion_id: str
):
    orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    con_cid = {r.stem for r in logs_del_stack() if correlacion_id in r.read_text(errors="replace")}

    assert {"gateway", "comercio"} <= con_cid, sorted(con_cid)
