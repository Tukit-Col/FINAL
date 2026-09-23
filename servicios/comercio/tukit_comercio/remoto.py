"""Lo que Comercio le pregunta a Catalogo por HTTP antes de cobrar, y nada mas.

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
from dataclasses import dataclass

import httpx
from tukit_comun.http import cliente_efimero

URL_CATALOGO_POR_OMISION = "http://127.0.0.1:8012"
ESPERA_SEGUNDOS = 30.0


def url_catalogo() -> str:
    return os.environ.get("TUKIT_CATALOGO_URL", URL_CATALOGO_POR_OMISION).rstrip("/")


class CatalogoCaido(Exception):
    """Catalogo no respondio. No se puede re-verificar, asi que no se cobra."""


@dataclass
class ClienteCatalogo:
    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_catalogo()

    async def precio_de(self, sku: str) -> int | None:
        """El precio publico vigente mas bajo del producto, en pesos COP.

        `None` cuando el producto existe pero no tiene precio vigente (el
        `precio_desde` del contrato de Catalogo es `null` en ese caso). Levanta
        `CatalogoCaido` si Catalogo no responde: sin poder re-verificar, la
        orden NO se cierra, que es lo contrario de degradar en silencio.
        """
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/catalogo/productos/{sku}")
                if respuesta.status_code == 404:
                    return None
                respuesta.raise_for_status()
                valor = respuesta.json().get("precio_desde")
                return int(valor) if valor is not None else None
        except httpx.HTTPError as error:
            raise CatalogoCaido(str(error)) from error


__all__ = ["ClienteCatalogo", "CatalogoCaido", "url_catalogo", "ESPERA_SEGUNDOS"]
