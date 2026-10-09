"""Lo que comparten las pruebas de integracion: rutas del stack, usuarios y flujos.

Va aparte del `conftest.py` para poder importarlo desde las pruebas
(`from stack_vivo import ...`); el `conftest.py` deja solo las fixtures.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from tukit_comun.bd import crear_motor

GATEWAY = os.environ.get("TUKIT_QA_GATEWAY_URL", "http://127.0.0.1:8010").rstrip("/")
RAIZ = Path(__file__).resolve().parents[2]
# Donde `make arriba` deja los logs y los pid de cada proceso.
EJECUCION = Path(os.environ.get("TUKIT_QA_EJECUCION", RAIZ / ".ejecucion"))
SERVICIOS_CON_BASE = ("identidad", "catalogo", "inteligencia", "comercio", "operacion")

# Los usuarios que siembra `tukit_identidad.sembrar_acceso`, uno por rol. La
# clave es la de demostracion que el propio sembrador publica: no es secreta.
CLAVE_DEMO = "demo1234"
USUARIOS_DEMO = {
    "acudiente": "mama@ejemplo.com",
    "acudiente_2": "papa@ejemplo.com",
    "colegio_admin": "rectoria@colegio.edu.co",
    "operador": "operador@tukit.co",
    "admin": "admin@tukit.co",
}

ENTREGA_FICTICIA = {
    "destinatario": "Acudiente Ficticio QA",
    "direccion": "Calle Ficticia 1 # 2-3",
    "ciudad": "Bogota",
}


def portador(sesiones: dict[str, dict[str, str]], rol: str) -> dict[str, str]:
    return {"authorization": f"Bearer {sesiones[rol]['token']}"}


def como_json(datos: bytes) -> Any:
    try:
        return json.loads(datos)
    except ValueError:
        return datos


# --------------------------------------------------------------- flujos


def crear_orden(
    http: httpx.Client, usuario_id: str, producto: dict[str, Any], **extra: Any
) -> httpx.Response:
    linea = {
        "sku": producto["sku"],
        "nombre": producto["nombre"][:120],
        "cantidad": 1,
        "precio_unitario": producto["precio_desde"],
    }
    linea.update(extra.pop("linea", {}))
    return http.post(
        "/v1/ordenes",
        json={"usuario_id": usuario_id, "lineas": [linea], "entrega": ENTREGA_FICTICIA, **extra},
    )


def pagar(http: httpx.Client, pedido_id: str, estado_wompi: str = "APPROVED") -> dict[str, Any]:
    """Inicia el pago y entrega el webhook firmado como lo haria Wompi.

    Con `WOMPI_MODO=falso` (el de omision) la pasarela firma con un secreto
    fijo, asi que el evento se arma con la misma `PasarelaFalsa` del producto.
    """
    from tukit_comercio.pasarela import PasarelaFalsa

    pago = http.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": "acudiente@example.test"})
    assert pago.status_code == 201, pago.text
    datos = pago.json()
    evento = PasarelaFalsa().emitir_evento(
        referencia=datos["referencia_wompi"],
        transaccion_id=datos["transaccion_wompi"],
        estado_wompi=estado_wompi,
    )
    webhook = http.post("/v1/webhooks/wompi", json=evento)
    assert webhook.status_code == 200, webhook.text
    return {"pago": datos, "evento": evento, "webhook": webhook.json()}


def orden_pagada(http: httpx.Client, usuario_id: str, producto: dict[str, Any]) -> str:
    """Crea una orden de una linea, la paga y devuelve su `pedido_id`."""
    orden = crear_orden(http, usuario_id, producto)
    assert orden.status_code == 201, orden.text
    pedido_id = orden.json()["pedido_id"]
    assert pagar(http, pedido_id)["webhook"]["pedido_transicionado"] is True
    return pedido_id


# --------------------------------------------------------------- bases y procesos


@contextlib.asynccontextmanager
async def conexion_a(servicio: str) -> AsyncIterator[AsyncConnection]:
    """Una conexion a la base del servicio, para barridos de varias consultas."""
    motor = crear_motor(servicio)
    try:
        async with motor.engine.connect() as conexion:
            yield conexion
    finally:
        await motor.cerrar()


def procesos_del_stack() -> dict[int, str]:
    """`pid -> nombre` de los procesos que levanto `make arriba`."""
    procesos = {}
    for archivo in EJECUCION.glob("*.pid"):
        contenido = archivo.read_text().strip()
        if contenido.isdigit():
            procesos[int(contenido)] = archivo.stem
    return procesos


def logs_del_stack() -> list[Path]:
    logs = sorted(EJECUCION.glob("*.log"))
    if not logs:
        pytest.fail(f"no hay logs del stack en {EJECUCION}; `make arriba` los deja ahi")
    return logs


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def instancia(modulo: str, registro: Path, **entorno: str) -> Iterator[str]:
    """Levanta una copia aparte de un servicio (`python -m modulo --puerto N`).

    Sirve para cortarle un destino sin tocar el stack compartido: la copia lee
    las URL de sus vecinos del entorno, que aqui se sobreescribe. Devuelve la URL
    base y la apaga al salir. Las variables de Gemini no pasan a la copia.
    """
    puerto = puerto_libre()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GEMINI")}
    env.update(entorno)
    with registro.open("w") as salida:
        proceso = subprocess.Popen(
            [sys.executable, "-m", modulo, "--puerto", str(puerto)],
            cwd=RAIZ,
            env=env,
            stdout=salida,
            stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{puerto}"
        try:
            for _ in range(150):
                try:
                    httpx.get(f"{base}/salud", timeout=1.0)
                    break
                except httpx.HTTPError:
                    time.sleep(0.1)
            else:
                pytest.fail(f"{modulo} no arranco en {base}; ver {registro}")
            yield base
        finally:
            # Uvicorn espera a las peticiones en vuelo antes de salir; con un
            # destino mudo eso son 300 s, asi que tras 5 s se mata.
            proceso.terminate()
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=5)
