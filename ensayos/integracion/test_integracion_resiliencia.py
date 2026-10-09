"""Fase 6 de QA, NFR-DIS-05: idempotencia y degradacion honesta contra el stack vivo.

Las pruebas de nivel 1 (`servicios/comercio/tests/test_comercio_resiliencia_patrones.py`)
simulan la carrera del webhook y el reenvio de la orden sobre SQLite. Aqui se
repite contra Postgres y los procesos de `make arriba`, por el gateway:

- **El webhook, diez veces a la vez.** Diez hilos, soltados juntos por una
  barrera, entregan el mismo evento aprobado. El efecto tiene que ser uno: una
  fila en `evento_pasarela_procesado`, un `pedido_pagado` en la bandeja, el
  pedido pagado. Las respuestas 5xx se anotan: dependen de como se crucen las
  transacciones, y el defecto lo fija el nivel 1 (H-A-57).
- **La orden reenviada.** El mismo `POST /v1/ordenes` dos veces con la misma
  `Idempotency-Key` (H-A-56).
- **Lo que el stack apago.** Sin `RABBITMQ_URL`, sin collector y con
  `WOMPI_MODO` de omision, el stack atiende. Lo que se pide ademas es que lo
  diga en sus registros (H-A-58).

El evento del webhook lleva un id de transaccion propio (`qa-<uuid>`), no el
`falsa-N` del pago: tras un reinicio de Comercio la pasarela falsa repite sus
ids y el evento se tomaria por repetido (H-A-57). Los datos son ficticios.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest
from stack_vivo import ENTREGA_FICTICIA, GATEWAY, crear_orden, logs_del_stack, portador

pytestmark = [pytest.mark.integracion, pytest.mark.nfr("NFR-DIS-05")]

ENTREGAS_SIMULTANEAS = 10


def _pago_iniciado(cliente: httpx.Client, sesiones: dict, producto: dict) -> tuple[str, dict[str, Any]]:
    orden = crear_orden(cliente, sesiones["acudiente"]["usuario_id"], producto)
    assert orden.status_code == 201, orden.text
    pedido_id = orden.json()["pedido_id"]
    pago = cliente.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": "acudiente@example.test"})
    assert pago.status_code == 201, pago.text
    return pedido_id, pago.json()


def _a_la_vez(evento: dict[str, Any], correlacion_id: str) -> list[tuple[int, str]]:
    barrera = threading.Barrier(ENTREGAS_SIMULTANEAS)

    def entregar(_: int) -> tuple[int, str]:
        with httpx.Client(
            base_url=GATEWAY, timeout=30.0, headers={"x-correlation-id": correlacion_id}
        ) as http:
            barrera.wait()
            respuesta = http.post("/v1/webhooks/wompi", json=evento)
        try:
            return respuesta.status_code, respuesta.json().get("estado") or respuesta.json().get("error", "")
        except ValueError:
            return respuesta.status_code, respuesta.text[:40]

    with ThreadPoolExecutor(ENTREGAS_SIMULTANEAS) as hilos:
        return list(hilos.map(entregar, range(ENTREGAS_SIMULTANEAS)))


async def test_diez_entregas_simultaneas_del_webhook_pagan_el_pedido_una_sola_vez(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, correlacion_id: str, record_property
):
    from tukit_comercio.pasarela import PasarelaFalsa

    pedido_id, pago = _pago_iniciado(cliente, sesiones, producto)
    evento = PasarelaFalsa().emitir_evento(
        referencia=pago["referencia_wompi"], transaccion_id=f"qa-{uuid.uuid4().hex}", estado_wompi="APPROVED"
    )

    respuestas = _a_la_vez(evento, correlacion_id)
    eventos = await consultar(
        "comercio", "select count(*) from evento_pasarela_procesado where evento_id = :e", e=evento["id"]
    )
    avisos = await consultar(
        "comercio",
        "select count(*) from bandeja_salida where tipo = 'pedido_pagado' and agregado_id::text = :p",
        p=pedido_id,
    )
    estado = await consultar(
        "comercio",
        "select p.estado, g.estado from pedido p join pago g on g.pedido_id = p.id where p.id::text = :p",
        p=pedido_id,
    )

    cuenta = Counter(f"{codigo}:{estado}" for codigo, estado in respuestas)
    record_property("entregas_simultaneas", ENTREGAS_SIMULTANEAS)
    record_property("respuestas", " ".join(f"{k}x{v}" for k, v in sorted(cuenta.items())))
    record_property("respuestas_5xx", sum(codigo >= 500 for codigo, _ in respuestas))
    record_property("aplicadas", cuenta.get("200:aplicado", 0))
    record_property("eventos_registrados", eventos[0][0])
    record_property("avisos_pedido_pagado", avisos[0][0])
    assert cuenta.get("200:aplicado", 0) == 1, cuenta
    assert (eventos[0][0], avisos[0][0]) == (1, 1)
    assert [tuple(fila) for fila in estado] == [("pagado", "aprobado")]


@pytest.mark.xfail(
    strict=True,
    reason="H-A-56: POST /v1/ordenes no tiene idempotencia de aplicacion; el reenvio con la misma "
    "Idempotency-Key crea un segundo pedido",
)
async def test_la_orden_reenviada_con_la_misma_idempotency_key_crea_un_solo_pedido(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, record_property
):
    cuerpo = {
        "usuario_id": sesiones["acudiente"]["usuario_id"],
        "lineas": [
            {
                "sku": producto["sku"],
                "nombre": producto["nombre"][:120],
                "cantidad": 1,
                "precio_unitario": producto["precio_desde"],
            }
        ],
        "entrega": ENTREGA_FICTICIA,
    }
    cabeceras = {**portador(sesiones, "acudiente"), "Idempotency-Key": uuid.uuid4().hex}
    primera = cliente.post("/v1/ordenes", json=cuerpo, headers=cabeceras)
    segunda = cliente.post("/v1/ordenes", json=cuerpo, headers=cabeceras)
    ids = {r.json().get("pedido_id") for r in (primera, segunda) if r.status_code == 201}
    filas = await consultar(
        "comercio", "select count(*) from pedido where id::text = any(:ids)", ids=[i for i in ids if i]
    )

    record_property("estados_http", f"{primera.status_code} {segunda.status_code}")
    record_property("pedidos_creados", filas[0][0])
    assert primera.status_code == 201, primera.text
    assert filas[0][0] == 1, f"la misma Idempotency-Key creo {filas[0][0]} pedidos"


async def test_sin_broker_ni_collector_y_con_la_pasarela_falsa_el_stack_atiende(
    cliente: httpx.Client, stack: dict, sesiones: dict, producto: dict, record_property
):
    vivos = {}
    for nombre, servicio in stack["servicios"].items():
        vivos[nombre] = httpx.get(f"{servicio['url']}/health/live", timeout=10.0).status_code
    _, pago = _pago_iniciado(cliente, sesiones, producto)

    record_property("health_live", " ".join(f"{n}:{c}" for n, c in sorted(vivos.items())))
    record_property("transaccion_wompi", pago["transaccion_wompi"])
    assert vivos == dict.fromkeys(stack["servicios"], 200)
    assert re.fullmatch(r"falsa-\d+", pago["transaccion_wompi"]), pago
    assert pago["url_redireccion"] is None


# Un aviso es una linea que el proceso escribe por su cuenta: `[servicio] ...`, como el de
# identidad sin `TUKIT_LLAVE_SESION`, o una linea de registro. No cuentan los accesos de uvicorn
# ni las llamadas salientes de httpx (`HTTP/1.1`), que nombran rutas como `/v1/webhooks/wompi`,
# ni las trazas de una excepcion. El `\b` va solo tras el nivel: entre `]` y el espacio no hay
# borde de palabra, y con el los avisos `[servicio]` nunca contarian.
_AVISO = re.compile(r"^(\[[\w-]+\]|(INFO|WARNING|ERROR|CRITICAL)\b)")
_PETICION = re.compile(r"HTTP/\d")
_APAGADOS = {
    "broker": re.compile(r"rabbit|broker|amqp", re.IGNORECASE),
    "trazas": re.compile(r"otel|opentelemetry|traza|telemetr|collector", re.IGNORECASE),
    "pasarela": re.compile(r"wompi|pasarela", re.IGNORECASE),
}


@pytest.mark.xfail(
    strict=True,
    reason="H-A-58: el stack arranca sin broker, sin trazas y con la pasarela falsa, y ninguno de "
    "sus registros lo dice",
)
def test_los_registros_del_stack_dicen_que_quedo_apagado(stack: dict, record_property):
    logs = logs_del_stack()
    avisos = {
        linea
        for log in logs
        for linea in log.read_text(errors="replace").splitlines()
        if _AVISO.match(linea) and not _PETICION.search(linea)
    }
    menciones = {
        nombre: sorted(a for a in avisos if patron.search(a)) for nombre, patron in _APAGADOS.items()
    }

    record_property("logs_barridos", len(logs))
    record_property("avisos_distintos", len(avisos))
    record_property("avisos_con_corchete", " | ".join(sorted(a for a in avisos if a.startswith("["))[:5]))
    for nombre, lineas in menciones.items():
        record_property(f"avisos_sobre_{nombre}", len(lineas))
    callados = [nombre for nombre, lineas in menciones.items() if not lineas]
    assert callados == [], f"ningun aviso del stack menciona: {', '.join(callados)}"
