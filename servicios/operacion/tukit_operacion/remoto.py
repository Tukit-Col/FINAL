"""Lo que Operacion le pide a Identidad por HTTP, y nada mas.

Un caso lo abre una persona que deja un correo y un celular. Ese contacto NO
se guarda en Operacion: se resuelve a un `usuario_id` llamando a Identidad
(`POST /v1/contactos`, alta idempotente por correo), que es exactamente el
mecanismo para el que esa ruta se construyo. Asi la notificacion y el caso
referencian al titular por identificador y el derecho al olvido lo alcanza en
un solo sitio.

Es una clase y no una funcion suelta para poder sustituirla entera en las
pruebas: el doble implementa el mismo metodo y el endpoint no se entera.
"""

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
    """Identidad no respondio. Sin poder validar la sesion, no se abre el acceso."""


@dataclass
class ClienteIdentidad:
    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_identidad()

    async def sesion(self, token: str) -> dict[str, Any] | None:
        """La sesion del portador (`usuario_id`, `correo`, `roles`), o `None` si el
        token no vale (401). FALLA CERRADA: una caida de Identidad es
        `IdentidadCaida`, nunca `None`, para no abrir el acceso por no poder preguntar."""
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
        """Devuelve el `usuario_id` del contacto, o `None` si Identidad no esta.

        `None` y no una excepcion: si Identidad esta caida, el caso se puede
        abrir igual sin titular resuelto y la degradacion se anota. El correo
        no se guarda aqui pase lo que pase.
        """
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
        """Resuelve un `usuario_id` a su contacto para enviar el aviso, sin
        guardarlo. Es la contraparte de `resolver_contacto`: alli el correo entra
        y se cambia por un id; aqui el id se cambia por el correo justo en el
        momento del envio (`GET /v1/contactos/{usuario_id}`).

        Devuelve `{"correo", "celular"}` o `None` si Identidad no responde o el
        usuario no existe: el repartidor sube `intentos` y reintenta luego, sin
        que el correo llegue a persistirse en Operacion en ningun caso.
        """
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/contactos/{usuario_id}")
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return {"correo": cuerpo.get("correo"), "celular": cuerpo.get("celular")}
        except httpx.HTTPError:
            return None


@dataclass
class ClienteMetricas:
    """Lo que el snapshot de metricas le pide a Catalogo e Inteligencia por HTTP.

    Lee el resumen global del catalogo (Catalogo), el listado de colegios
    (Identidad) y las metricas en vivo por colegio (Inteligencia). Cada llamada
    degrada a `None`/`[]` si el servicio esta caido: un snapshot parcial es una
    respuesta valida, no un fallo — al dia siguiente se vuelve a intentar. No
    guarda nada aqui; solo trae los agregados que el escritor persiste.
    """

    cliente: httpx.AsyncClient | None = None
    base_catalogo: str = ""
    base_identidad: str = ""
    base_inteligencia: str = ""

    async def resumen_catalogo(self) -> dict[str, Any] | None:
        """Las siete cifras del catalogo curado, o `None` si Catalogo no esta."""
        base = self.base_catalogo or url_catalogo()
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{base}/v1/catalogo/resumen")
                respuesta.raise_for_status()
                return respuesta.json()
        except httpx.HTTPError:
            return None

    async def colegios(self) -> list[dict[str, Any]]:
        """Los colegios activos (`colegio_id`, `nombre`), o `[]` si Identidad no esta."""
        base = self.base_identidad or url_identidad()
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{base}/v1/colegios")
                respuesta.raise_for_status()
                return list(respuesta.json().get("colegios", []))
        except httpx.HTTPError:
            return []

    async def metricas_colegio(self, colegio_id: str) -> dict[str, Any] | None:
        """Las metricas en vivo de un colegio, o `None` si Inteligencia no esta."""
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
