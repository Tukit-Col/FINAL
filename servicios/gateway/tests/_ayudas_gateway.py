"""Ayudas compartidas de las pruebas del limite de tasa de la puerta.

`Atras` reemplaza el cliente compartido de la puerta por uno que responde 200 y
anota lo que le llega; las fixtures `atras` y `redis` viven en `conftest.py`.
"""

from __future__ import annotations

import httpx
from tukit_gateway.api import app


class Atras:
    """Los servicios de atras: responden 200 a todo y cuentan lo que les llega."""

    def __init__(self) -> None:
        self.peticiones: list[tuple[str, str]] = []
        atras = self

        class Cliente:
            async def aclose(self) -> None:
                return None

            async def request(self, metodo, url, **_kwargs) -> httpx.Response:
                atras.peticiones.append((metodo, url))
                return httpx.Response(200, json={"ok": True})

        self.cliente = Cliente()


def http_de(cliente: tuple[str, int] = ("127.0.0.1", 50_000)) -> httpx.AsyncClient:
    """Un cliente de prueba sobre la puerta, con la IP de conexion dada."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=cliente), base_url="http://prueba")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def codigos(http: httpx.AsyncClient, veces: int, metodo: str, ruta: str, **kwargs) -> list[int]:
    """Los codigos de `veces` peticiones iguales seguidas."""
    return [(await http.request(metodo, ruta, **kwargs)).status_code for _ in range(veces)]
