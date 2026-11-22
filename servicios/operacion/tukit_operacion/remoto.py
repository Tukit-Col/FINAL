from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from tukit_comun.http import cliente_efimero

URL_IDENTIDAD_POR_OMISION = "http://127.0.0.1:8011"
URL_CATALOGO_POR_OMISION = "http://127.0.0.1:8012"
URL_INTELIGENCIA_POR_OMISION = "http://127.0.0.1:8013"
ESPERA_SEGUNDOS = 30.0


def url_identidad() -> str:
    return os.environ.get("TUKIT_IDENTIDAD_URL", URL_IDENTIDAD_POR_OMISION).rstrip("/")


def url_catalogo() -> str:
    return os.environ.get("TUKIT_CATALOGO_URL", URL_CATALOGO_POR_OMISION).rstrip("/")


def url_inteligencia() -> str:
    return os.environ.get("TUKIT_INTELIGENCIA_URL", URL_INTELIGENCIA_POR_OMISION).rstrip("/")


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

    async def resolver_contacto(self, correo: str, celular: str | None = None) -> str | None:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.post(
                    f"{self._base()}/v1/contactos",
                    json={"correo": correo, "celular": celular},
                )
                respuesta.raise_for_status()
                return str(respuesta.json().get("usuario_id"))
        except httpx.HTTPError:
            return None

    async def contacto_de(self, usuario_id: str) -> dict[str, str | None] | None:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/contactos/{usuario_id}")
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return {"correo": cuerpo.get("correo"), "celular": cuerpo.get("celular")}
        except httpx.HTTPError:
            return None

    async def nombre_colegio(self, colegio_id: str) -> str | None:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/colegios/{colegio_id}")
                respuesta.raise_for_status()
                nombre = respuesta.json().get("nombre")
                return str(nombre) if nombre else None
        except (httpx.HTTPError, ValueError):
            return None


@dataclass
class ClienteMetricas:

    cliente: httpx.AsyncClient | None = None
    base_catalogo: str = ""
    base_identidad: str = ""
    base_inteligencia: str = ""

    async def resumen_catalogo(self) -> dict[str, Any] | None:
        base = self.base_catalogo or url_catalogo()
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{base}/v1/catalogo/resumen")
                respuesta.raise_for_status()
                return respuesta.json()
        except httpx.HTTPError:
            return None

    async def colegios(self) -> list[dict[str, Any]]:
        base = self.base_identidad or url_identidad()
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{base}/v1/colegios")
                respuesta.raise_for_status()
                return list(respuesta.json().get("colegios", []))
        except httpx.HTTPError:
            return []

    async def metricas_colegio(self, colegio_id: str) -> dict[str, Any] | None:
        base = self.base_inteligencia or url_inteligencia()
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{base}/v1/metricas/colegios/{colegio_id}")
                respuesta.raise_for_status()
                return respuesta.json()
        except httpx.HTTPError:
            return None


__all__ = [
    "IdentidadCaida",
    "ClienteIdentidad",
    "IdentidadCaida",
    "ClienteMetricas",
    "url_identidad",
    "url_catalogo",
    "url_inteligencia",
    "ESPERA_SEGUNDOS",
]
