from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from tukit_comun.http import cliente_efimero
from tukit_comun.resiliencia import CircuitoAbierto, disyuntor_de, reintentar_get

URL_CATALOGO_POR_OMISION = "http://127.0.0.1:8012"
URL_IDENTIDAD_POR_OMISION = "http://127.0.0.1:8011"
ESPERA_SEGUNDOS = 30.0


def url_catalogo() -> str:
    return os.environ.get("TUKIT_CATALOGO_URL", URL_CATALOGO_POR_OMISION).rstrip("/")


def url_identidad() -> str:
    return os.environ.get("TUKIT_IDENTIDAD_URL", URL_IDENTIDAD_POR_OMISION).rstrip("/")


class CatalogoCaido(Exception):
    pass


@dataclass
class ClienteCatalogo:
    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_catalogo()

    async def resolver(self, sku: str) -> tuple[uuid.UUID, int | None] | None:

        @reintentar_get
        async def _pedir() -> tuple[uuid.UUID, int | None] | None:
            async with (
                disyuntor_de("catalogo"),
                cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente,
            ):
                respuesta = await cliente.get(f"{self._base()}/interno/resolver-sku/{sku}")
                if respuesta.status_code == 404:
                    return None
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                valor = cuerpo.get("precio_desde")
                return uuid.UUID(cuerpo["producto_canonico_id"]), (int(valor) if valor is not None else None)

        try:
            return await _pedir()
        except CircuitoAbierto as error:
            raise CatalogoCaido(f"circuito abierto: {error}") from error
        except httpx.HTTPError as error:
            raise CatalogoCaido(str(error)) from error


class IdentidadCaida(Exception):
    pass


@dataclass
class ClienteIdentidad:
    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_identidad()

    async def sesion(self, token: str) -> dict[str, Any] | None:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(
                    f"{self._base()}/v1/sesiones/actual",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if respuesta.status_code == 401:
                    return None
                respuesta.raise_for_status()
                return dict(respuesta.json())
        except httpx.HTTPError as error:
            raise IdentidadCaida(str(error)) from error


__all__ = [
    "ClienteCatalogo",
    "CatalogoCaido",
    "ClienteIdentidad",
    "IdentidadCaida",
    "url_catalogo",
    "url_identidad",
    "ESPERA_SEGUNDOS",
]
