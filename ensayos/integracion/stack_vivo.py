"""Lo que comparten las pruebas de integracion: rutas del stack, usuarios y flujos.

Va aparte del `conftest.py` para poder importarlo desde las pruebas
(`from stack_vivo import ...`); el `conftest.py` deja solo las fixtures.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import random
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
# CONTRATO_API §9 (desde 173ee80): bajo `/v1/ordenes` la puerta solo expone el
# avance. Crear, pagar, leer, cancelar y retractar una orden son llamadas
# internas, asi que los flujos las hacen directo a comercio, como inteligencia.
# El webhook de Wompi sigue entrando por la puerta.
COMERCIO = os.environ.get("TUKIT_COMERCIO_URL", "http://127.0.0.1:8014").rstrip("/")
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


# El limite de la puerta (ADR 0047, 45dc0b7) cuenta por token y por IP, y la puerta confia en el
# `X-Forwarded-For` que le llega desde 127.0.0.1 (`PROXIES_POR_OMISION`). Cada familia simulada
# manda su propia IP de 198.18.0.0/15 (RFC 2544, reservada para pruebas de red), como si llegara
# por su lado (decision N-120). Es al azar para que dos corridas seguidas dentro de la misma
# ventana no compartan cupo.
_RED_DE_FAMILIAS = ipaddress.IPv4Network("198.18.0.0/15")
CABECERA_IP = "x-forwarded-for"


def ip_de_familia() -> str:
    """Una IP de 198.18.0.0/15 que ninguna otra familia de la corrida usa, salvo por azar."""
    return str(_RED_DE_FAMILIAS[random.randrange(1, _RED_DE_FAMILIAS.num_addresses - 1)])


def cabecera_de_familia(ip: str | None = None) -> dict[str, str]:
    """La cabecera con que una familia llega a la puerta: la IP dada o una nueva."""
    return {CABECERA_IP: ip or ip_de_familia()}


def portador(sesiones: dict[str, dict[str, str]], rol: str) -> dict[str, str]:
    """El token del rol y, si la sesion la trae, la IP con que ese usuario entro."""
    sesion = sesiones[rol]
    return {
        "authorization": f"Bearer {sesion['token']}",
        **({CABECERA_IP: sesion["ip"]} if "ip" in sesion else {}),
    }


def como_json(datos: bytes) -> Any:
    try:
        return json.loads(datos)
    except ValueError:
        return datos


# --------------------------------------------------------------- flujos


def crear_orden(
    http: httpx.Client,
    usuario_id: str,
    producto: dict[str, Any],
    *,
    comercio: str = COMERCIO,
    **extra: Any,
) -> httpx.Response:
    """`POST /v1/ordenes` de una linea, directo a `comercio` (la del stack o una copia).

    Va con el cliente de la prueba (URL absoluta), asi que el `correlacion_id`
    de su cabecera llega igual.
    """
    linea = {
        "sku": producto["sku"],
        "nombre": producto["nombre"][:120],
        "cantidad": 1,
        "precio_unitario": producto["precio_desde"],
    }
    linea.update(extra.pop("linea", {}))
    return http.post(
        f"{comercio}/v1/ordenes",
        json={"usuario_id": usuario_id, "lineas": [linea], "entrega": ENTREGA_FICTICIA, **extra},
    )


def monto_centavos(http: httpx.Client, pedido_id: str) -> int:
    """El total del pedido en centavos, leido en comercio: el webhook lo firma y comercio
    lo compara con el pago (desde fe8c030)."""
    orden = http.get(f"{COMERCIO}/v1/ordenes/{pedido_id}")
    assert orden.status_code == 200, orden.text
    return int(orden.json()["total"]) * 100


def pagar(http: httpx.Client, pedido_id: str, estado_wompi: str = "APPROVED") -> dict[str, Any]:
    """Inicia el pago directo en comercio y entrega el webhook firmado por la puerta, como Wompi.

    Con `WOMPI_MODO=falso` (el de omision) la pasarela firma con un secreto
    fijo, asi que el evento se arma con la misma `PasarelaFalsa` del producto.
    """
    from tukit_comercio.pasarela import PasarelaFalsa

    pago = http.post(
        f"{COMERCIO}/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": "acudiente@example.test"}
    )
    assert pago.status_code == 201, pago.text
    datos = pago.json()
    evento = PasarelaFalsa().emitir_evento(
        referencia=datos["referencia_wompi"],
        transaccion_id=datos["transaccion_wompi"],
        estado_wompi=estado_wompi,
        monto_centavos=monto_centavos(http, pedido_id),
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
