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

import httpx
from tukit_comun.http import cliente_efimero

URL_IDENTIDAD_POR_OMISION = "http://127.0.0.1:8011"
ESPERA_SEGUNDOS = 30.0


def url_identidad() -> str:
    return os.environ.get("TUKIT_IDENTIDAD_URL", URL_IDENTIDAD_POR_OMISION).rstrip("/")


@dataclass
class ClienteIdentidad:
    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_identidad()

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


__all__ = ["ClienteIdentidad", "url_identidad", "ESPERA_SEGUNDOS"]
