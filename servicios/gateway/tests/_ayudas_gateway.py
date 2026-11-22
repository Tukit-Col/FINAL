from __future__ import annotations

import httpx
from tukit_gateway.api import app


class Atras:

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
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=cliente), base_url="http://prueba")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def codigos(http: httpx.AsyncClient, veces: int, metodo: str, ruta: str, **kwargs) -> list[int]:
    return [(await http.request(metodo, ruta, **kwargs)).status_code for _ in range(veces)]
