"""Los servicios de los que depende el pipeline, detras de un puerto.

Decisiones:
- Inteligencia no lee la base del Catalogo ni importa su paquete: lo que necesita llega por HTTP,
  y las URL salen del entorno.
- Como degradar: sin Catalogo no hay pipeline (`RemotoCaido`, el trabajo queda `fallido` y es
  reintentable; no se arma un kit vacio). Sin Identidad si hay pipeline: corre sin `usuario_id`, se
  anota la degradacion y no hay a quien avisar; perder el aviso es mejor que perder el kit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from tukit_comun.http import cliente_efimero
from tukit_comun.resiliencia import CircuitoAbierto, disyuntor_de, reintentar_get

URL_CATALOGO_POR_OMISION = "http://127.0.0.1:8012"
URL_IDENTIDAD_POR_OMISION = "http://127.0.0.1:8011"
URL_COMERCIO_POR_OMISION = "http://127.0.0.1:8014"

ESPERA_SEGUNDOS = 60.0


class RemotoCaido(Exception):

    def __init__(self, servicio: str, detalle: str, estado: int | None = None) -> None:
        super().__init__(f"{servicio}: {detalle}")
        self.servicio = servicio
        self.detalle = detalle
        self.estado = estado

    @property
    def transitorio(self) -> bool:
        return self.estado is None or self.estado >= 500 or self.estado in (408, 429)


def url_catalogo() -> str:
    return os.environ.get("TUKIT_CATALOGO_URL", URL_CATALOGO_POR_OMISION).rstrip("/")


def url_identidad() -> str:
    return os.environ.get("TUKIT_IDENTIDAD_URL", URL_IDENTIDAD_POR_OMISION).rstrip("/")


def url_comercio() -> str:
    return os.environ.get("TUKIT_COMERCIO_URL", URL_COMERCIO_POR_OMISION).rstrip("/")


_ORDEN_NIVEL = {"confiable": 0, "economico": 1, "premium": 2}


def elegir_producto_de_personaje(productos: list[dict[str, Any]]) -> dict[str, Any] | None:

    return min(productos, key=_clave_de_personaje) if productos else None


def _clave_de_personaje(p: dict[str, Any]) -> tuple[Any, ...]:
    precio = p.get("precio_desde")
    return (precio is None, _ORDEN_NIVEL.get(p.get("nivel"), 9), precio or 0, str(p.get("sku") or ""))


@dataclass
class ClienteCatalogo:

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_catalogo()

    async def _pedir(self, metodo: str, ruta: str, **kw: Any) -> Any:

        async def _una_vez() -> Any:
            async with (
                disyuntor_de("catalogo"),
                cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente,
            ):
                respuesta = await cliente.request(metodo, f"{self._base()}{ruta}", **kw)
                respuesta.raise_for_status()
                return respuesta.json()

        llamar = reintentar_get(_una_vez) if metodo.upper() == "GET" else _una_vez
        try:
            return await llamar()
        except CircuitoAbierto as error:
            raise RemotoCaido("catalogo", f"circuito abierto ({error})") from error
        except httpx.HTTPStatusError as error:
            codigo = error.response.status_code
            raise RemotoCaido("catalogo", f"{ruta} respondio {codigo}", estado=codigo) from error
        except httpx.HTTPError as error:
            raise RemotoCaido("catalogo", f"{ruta} no respondio ({error})") from error

    async def emparejar(
        self, renglones: list[str], conceptos: list[str | None] | None = None
    ) -> list[dict[str, Any]]:
        pedido: dict[str, Any] = {"renglones": renglones}
        if conceptos is not None:
            pedido["conceptos"] = conceptos
        cuerpo = await self._pedir("POST", "/v1/catalogo/emparejar", json=pedido)
        return list(cuerpo.get("emparejamientos") or ())

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo: int | None = None) -> list[dict]:
        parametros: dict[str, Any] = {"colegio_id": colegio_id, "grado": grado, "por_pagina": 5}
        if anio_lectivo is not None:
            parametros["anio_lectivo"] = anio_lectivo
        cuerpo = await self._pedir("GET", "/v1/listas", params=parametros)
        return list(cuerpo.get("listas") or ())

    async def lista(self, lista_id: str) -> dict[str, Any]:
        return await self._pedir("GET", f"/v1/listas/{lista_id}")

    async def revision(self, version_id: str) -> dict[str, Any]:
        return await self._pedir("GET", f"/v1/admin/listas/{version_id}/revision")

    async def producto(self, sku: str) -> dict[str, Any]:
        return await self._pedir("GET", f"/v1/catalogo/productos/{sku}")

    async def productos_del_concepto(self, concepto: str, *, maximo: int = 40) -> list[dict[str, Any]]:
        cuerpo = await self._pedir(
            "GET",
            "/v1/catalogo/productos",
            params={"concepto": concepto, "con_precio": "true", "por_pagina": maximo},
        )
        return list(cuerpo.get("productos") or ())

    async def productos_de_personaje(
        self, concepto: str, personaje: str, *, limite: int = 8
    ) -> list[dict[str, Any]]:
        cuerpo = await self._pedir(
            "GET",
            "/v1/catalogo/productos",
            params={"concepto": concepto, "personaje": personaje, "por_pagina": limite},
        )
        productos = list(cuerpo.get("productos") or ())
        return sorted(productos, key=_clave_de_personaje)

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        productos = await self.productos_de_personaje(concepto, personaje, limite=20)
        return productos[0] if productos else None

    async def listas_por_contacto(self, contacto_referencia: str) -> list[dict[str, Any]]:
        cuerpo = await self._pedir("GET", f"/interno/listas-por-contacto/{contacto_referencia}")
        return list(cuerpo.get("listas") or ())

    async def retirar_de_contacto(
        self, contacto_referencia: str, *, tarea_id: str | None = None, version_id: str | None = None
    ) -> int:
        cuerpo = {k: v for k, v in (("tarea_id", tarea_id), ("version_id", version_id)) if v}
        respuesta = await self._pedir(
            "POST", f"/interno/listas-por-contacto/{contacto_referencia}/retirar", json=cuerpo
        )
        return int(respuesta.get("retiradas") or 0)

    async def resueltos(self, version_id: str) -> dict[str, Any]:
        return await self._pedir("GET", f"/v1/admin/listas/{version_id}/resueltos")

    async def importar_lista(
        self,
        *,
        colegio_id: str,
        grado: str,
        anio_lectivo: int,
        items: list[dict],
        documento_base64: str,
        percepcion_cruda: list[dict],
        contacto_referencia: str | None = None,
        preferencias: dict[str, Any] | None = None,
        colegio_datos: dict[str, Any] | None = None,
        origen: str = "onboarding",
        clave_idempotencia: str | None = None,
        referencias: list[str] | None = None,
    ) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {
            "colegio_id": colegio_id,
            "grado": grado,
            "anio_lectivo": anio_lectivo,
            "items": items,
            "origen": origen,
            "evidencia": {
                "documento_base64": documento_base64,
                "percepcion_cruda": percepcion_cruda,
            },
        }
        if contacto_referencia is not None:
            cuerpo["contacto_referencia"] = contacto_referencia
        if preferencias:
            cuerpo["preferencias"] = preferencias
        if colegio_datos:
            cuerpo["colegio_datos"] = colegio_datos
        if referencias:
            cuerpo["referencias"] = list(referencias)
        if clave_idempotencia is not None:
            cuerpo["clave_idempotencia"] = clave_idempotencia
        return await self._pedir("POST", "/v1/admin/listas/importar", json=cuerpo)


@dataclass
class ClienteIdentidad:

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_identidad()

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
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

    async def usuario_del_token(self, token: str) -> str | None:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(
                    f"{self._base()}/v1/sesiones/actual",
                    headers={"Authorization": f"Bearer {token}"},
                )
                respuesta.raise_for_status()
                return str(respuesta.json()["usuario_id"])
        except (httpx.HTTPError, KeyError):
            return None

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
            raise RemotoCaido("identidad", str(error)) from error

    async def tiene_credencial(self, usuario_id: str) -> bool:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/contactos/{usuario_id}/credencial")
                if respuesta.status_code == 404:
                    raise RemotoCaido(
                        "identidad",
                        "identidad no tiene GET /v1/contactos/{id}/credencial: reiniciala antes",
                    )
                respuesta.raise_for_status()
                return bool(respuesta.json()["tiene_credencial"])
        except (httpx.HTTPError, KeyError, ValueError) as error:
            raise RemotoCaido("identidad", str(error)) from error

    async def datos_directorio(self, dane: str) -> dict[str, Any] | None:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/directorio/{dane}")
                if respuesta.status_code == 404:
                    return None
                respuesta.raise_for_status()
                return dict(respuesta.json())
        except httpx.HTTPError:
            return None

    async def colegios_conocidos(self) -> list[dict[str, Any]]:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/colegios")
                respuesta.raise_for_status()
                return list(respuesta.json().get("colegios") or [])
        except (httpx.HTTPError, ValueError):
            return []


@dataclass
class ClienteComercio:

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_comercio()

    async def crear_orden(self, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return await self._postear("/v1/ordenes", cuerpo)

    async def iniciar_pago(self, pedido_id: str, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return await self._postear(f"/v1/ordenes/{pedido_id}/pago", cuerpo)

    async def pedidos_pagados(self) -> list[dict[str, Any]]:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/comercio/pedidos-pagados")
                respuesta.raise_for_status()
        except httpx.HTTPError as error:
            raise RemotoCaido("comercio", str(error)) from error
        return list(respuesta.json().get("pedidos") or ())

    async def pedidos_de(self, token: str) -> list[dict[str, Any]]:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(
                    f"{self._base()}/v1/comercio/mis-pedidos",
                    headers={"Authorization": f"Bearer {token}"},
                )
                respuesta.raise_for_status()
        except httpx.HTTPError as error:
            raise RemotoCaido("comercio", str(error)) from error
        return list(respuesta.json().get("pedidos") or ())

    async def _postear(self, ruta: str, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            async with (
                disyuntor_de("comercio"),
                cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente,
            ):
                respuesta = await cliente.post(f"{self._base()}{ruta}", json=cuerpo)
        except CircuitoAbierto as error:
            raise RemotoCaido("comercio", f"circuito abierto ({error})") from error
        except httpx.HTTPError as error:
            raise RemotoCaido("comercio", str(error)) from error
        if respuesta.status_code >= 500:
            raise RemotoCaido("comercio", f"{respuesta.status_code} en {ruta}")
        return respuesta.status_code, respuesta.json()


__all__ = [
    "ESPERA_SEGUNDOS",
    "ClienteCatalogo",
    "ClienteComercio",
    "ClienteIdentidad",
    "RemotoCaido",
    "url_catalogo",
    "url_comercio",
    "url_identidad",
]
