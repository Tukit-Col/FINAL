"""Lo que Comercio le pregunta a otros servicios por HTTP: a Catalogo antes de
cobrar, y a Identidad quien es el portador de un token.

La primera invariante del §9 no se negocia: antes de cerrar una orden se vuelven
a leer precio y disponibilidad, y si cambiaron la orden no se cierra. Esa lectura
es contra Catalogo POR HTTP y NO un cruce a su base: Comercio no toca la base de
otro servicio (regla 1-2 de las fronteras). El precio publico vive en Catalogo;
Comercio solo lo consulta para congelarlo en la linea (ADR 0012) una vez.

Es una clase y no una funcion suelta para poder sustituirla entera en las
pruebas: el doble implementa `precio_de` y el endpoint no se entera de que no
salio a la red.
"""

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
    """Catalogo no respondio. No se puede re-verificar, asi que no se cobra."""


@dataclass
class ClienteCatalogo:
    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_catalogo()

    async def resolver(self, sku: str) -> tuple[uuid.UUID, int | None] | None:
        """El id canonico y el precio publico vigente de un sku.

        `None` cuando el sku no existe; `(id, None)` cuando existe pero no tiene
        precio vigente (el `precio_desde` del contrato es `null` en ese caso).
        Levanta `CatalogoCaido` si Catalogo no responde: sin poder re-verificar,
        la orden NO se cierra, que es lo contrario de degradar en silencio.

        Pega al endpoint INTERNO `/interno/resolver-sku` (no `/v1/catalogo`):
        Comercio necesita el id canonico para congelar la linea y reservar, y
        ese id la superficie publica nunca lo expone (RPO cero, ADR 0017). La
        puerta no rutea `/interno`, asi que el navegador no lo alcanza.

        Es un GET idempotente, asi que va protegido (ADR 0020): reintento con
        backoff ante timeout/red, y disyuntor por-destino que corta la tormenta
        si Catalogo esta caido. `CircuitoAbierto` se traduce a `CatalogoCaido`,
        que es lo que el checkout ya sabe manejar (503, no cobra a ciegas).
        """

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
    """Identidad no respondio. Sin poder validar la sesion, no se abre el acceso."""


@dataclass
class ClienteIdentidad:
    """Valida un token contra Identidad (`GET /v1/sesiones/actual`).

    Es lo que deja a Comercio exigir sesion y rol sin leer la base de Identidad
    (regla 1 de las fronteras): pregunta por HTTP, como inteligencia.
    """

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_identidad()

    async def sesion(self, token: str) -> dict[str, Any] | None:
        """La sesion del portador (`usuario_id`, `roles`), o `None` si el token
        no vale (401).

        FALLA CERRADA: una caida de Identidad es `IdentidadCaida`, no `None`, para
        que quien valida nunca abra el acceso por no poder preguntar. Sin reintento
        ni disyuntor, igual que en inteligencia: quien espera es una persona y un
        503 claro le sirve mas que un reintento a ciegas."""
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
