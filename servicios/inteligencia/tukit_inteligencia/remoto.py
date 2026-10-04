"""Los dos servicios de los que depende el pipeline, detras de un puerto.

Inteligencia no puede leer la base del catalogo ni importar su paquete: son
los invariantes 1 y 3, y son la razon de ser del rediseno entero. Lo que el
pipeline necesita del catalogo (emparejar renglones, leer la lista oficial de
un colegio) llega por HTTP, y lo que necesita de identidad (registrar el
contacto y devolver un identificador) tambien.

Que esten los dos en un solo modulo no es pereza: es que comparten la unica
decision interesante de esta capa, que es **como degradar**. La seccion 8 del
contrato dice que ningun fallo externo devuelve 500 si hay una respuesta
parcial honesta, y aqui eso se concreta asi:

- Sin catalogo no hay pipeline. Se levanta `RemotoCaido`, el trabajo queda
  `fallido` con su diagnostico y es reintentable. No se arma un kit vacio:
  un kit sin productos se parece demasiado a un kit sin huecos.
- Sin identidad si hay pipeline. El trabajo corre sin `usuario_id`, se anota
  la degradacion y al final no hay a quien avisarle. Perder el aviso es malo;
  perder el kit por no poder avisar es peor.

Las URL salen del entorno y no se derivan de ningun nombre de base: este
modulo no sabe donde vive el dato del otro servicio, solo con quien habla.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from tukit_comun.http import cliente_efimero

# Puertos por omision del arranque local. Coinciden con los que documenta el
# contrato y con los que levanta el ejecutor de tareas; se sobreescriben con
# TUKIT_CATALOGO_URL y TUKIT_IDENTIDAD_URL.
URL_CATALOGO_POR_OMISION = "http://127.0.0.1:8012"
URL_IDENTIDAD_POR_OMISION = "http://127.0.0.1:8011"
URL_COMERCIO_POR_OMISION = "http://127.0.0.1:8014"

# Generoso a proposito. El emparejamiento de una lista entera carga el indice
# del catalogo y compara cada renglon contra 100 conceptos; medio segundo de
# tiempo de espera convertiria una lista larga en un fallo intermitente, que
# es la peor clase de fallo que se puede tener en un pipeline asincrono.
ESPERA_SEGUNDOS = 60.0


class RemotoCaido(Exception):
    """Una dependencia externa no respondio. No es un defecto del kit."""

    def __init__(self, servicio: str, detalle: str) -> None:
        super().__init__(f"{servicio}: {detalle}")
        self.servicio = servicio
        self.detalle = detalle


def url_catalogo() -> str:
    return os.environ.get("TUKIT_CATALOGO_URL", URL_CATALOGO_POR_OMISION).rstrip("/")


def url_identidad() -> str:
    return os.environ.get("TUKIT_IDENTIDAD_URL", URL_IDENTIDAD_POR_OMISION).rstrip("/")


def url_comercio() -> str:
    return os.environ.get("TUKIT_COMERCIO_URL", URL_COMERCIO_POR_OMISION).rstrip("/")


@dataclass
class ClienteCatalogo:
    """Lo que el pipeline le pide al catalogo, y nada mas.

    Es una clase y no cuatro funciones sueltas para poder sustituirla entera
    en las pruebas: el doble implementa los mismos tres metodos y el pipeline
    no se entera. Sin eso, probar la orquestacion exigiria levantar el otro
    servicio, y una prueba que necesita dos procesos no se corre.
    """

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_catalogo()

    async def _pedir(self, metodo: str, ruta: str, **kw: Any) -> Any:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.request(metodo, f"{self._base()}{ruta}", **kw)
                respuesta.raise_for_status()
                return respuesta.json()
        except httpx.HTTPStatusError as error:
            raise RemotoCaido("catalogo", f"{ruta} respondio {error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise RemotoCaido("catalogo", f"{ruta} no respondio ({error})") from error

    async def emparejar(
        self, renglones: list[str], conceptos: list[str | None] | None = None
    ) -> list[dict[str, Any]]:
        """`conceptos`, si viene, es el codigo ya asignado a cada renglon (o None)."""
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

    async def producto(self, sku: str) -> dict[str, Any]:
        """El producto autoritativo por sku, con precio y empaque frescos.

        Se usa al fijar un producto en una linea que NO era candidato del item
        (p. ej. un personaje que el optimizador deprioriza): la linea no puede
        copiar campos de un CANDIDATO que no existe, asi que los pide aqui.
        """
        return await self._pedir("GET", f"/v1/catalogo/productos/{sku}")

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        """El producto de un concepto ancla para un personaje, o None si no hay.

        Es la misma consulta que el interruptor de personaje del Fan hace en la
        consola (concepto + personaje, primera pagina), pero del lado del
        servidor: la ruta de aplicacion del acudiente congela las anclas del kit
        canonico al personaje elegido sin depender del navegador.
        """
        cuerpo = await self._pedir(
            "GET",
            "/v1/catalogo/productos",
            params={"concepto": concepto, "personaje": personaje, "por_pagina": 1},
        )
        productos = list(cuerpo.get("productos") or ())
        return productos[0] if productos else None

    async def listas_por_contacto(self, contacto_referencia: str) -> list[dict[str, Any]]:
        """Las listas que subio un acudiente, para su panel "Mis solicitudes".

        Cuelga de `/interno` A PROPOSITO: la puerta no rutea ese prefijo, asi que
        esta lectura servicio-a-servicio no existe hacia el navegador (nadie de
        fuera pide "las listas de un contacto"). Inteligencia le pega directo al
        Catalogo con el `usuario_id` de la sesion que ya valido: `contacto_referencia`
        JAMAS viene del navegador.
        """
        cuerpo = await self._pedir("GET", f"/interno/listas-por-contacto/{contacto_referencia}")
        return list(cuerpo.get("listas") or ())

    async def resueltos(self, version_id: str) -> dict[str, Any]:
        """La ruta rapida: items ya resueltos + candidatos curados de una lista revisada.

        Para una version REVISADA, el catalogo devuelve cada item con su
        concepto y los productos candidatos curados (los mismos que devolveria
        `emparejar`, pero indexados por el concepto ya resuelto: sin busqueda de
        texto, sin recomputo). Es la fuente de datos de la optimizacion cuando
        la lista ya paso por revision humana, y por eso no toca Gemini.
        """
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
    ) -> dict[str, Any]:
        """Escribe una lista percibida en el catalogo, con su evidencia.

        El PDF viaja en base64 y la percepcion cruda por pagina viaja al lado
        para que la revision humana del catalogo pueda contrastar lo que se
        importo contra lo que el modelo leyo. Inteligencia no escribe en la
        base del catalogo: le entrega el renglon y la evidencia por HTTP y es
        el catalogo quien decide como guardarlo (invariantes 1 y 3).

        Cuando la subida viene de un acudiente, `contacto_referencia` es su
        `usuario_id` (nunca su correo ni telefono): la traza que deja al padre
        esperando para poder avisarle cuando la version se apruebe.

        `colegio_datos` viaja cuando el colegio AUN NO existe en Tukit (lo eligio
        del directorio de Bogota o lo escribio a mano): trae su nombre y DANE
        para que la cola lo muestre y la aprobacion cree su identidad. Un colegio
        aliado ya conocido no lo trae.
        """
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
        return await self._pedir("POST", "/v1/admin/listas/importar", json=cuerpo)


@dataclass
class ClienteIdentidad:
    """Registrar el contacto y quedarse con el identificador, nunca el correo.

    Es la mitad que hace cumplible la nota del manifiesto: el trabajo guarda
    `usuario_id` y no el correo, asi que el derecho al olvido alcanza el dato
    de contacto borrandolo en un solo sitio.
    """

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_identidad()

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        """Devuelve el identificador del usuario, o `None` si identidad no esta.

        `None` y no una excepcion: la caida de identidad degrada el trabajo,
        no lo tumba. Quien llama anota la degradacion.
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

    async def sesion(self, token: str) -> dict[str, Any] | None:
        """La sesion del portador del token contra identidad
        (`GET /v1/sesiones/actual`), o `None` si el token no vale (401).

        A diferencia del resto de este cliente, la autorizacion FALLA CERRADA:
        una caida de identidad es `RemotoCaido` (no `None`), para que quien
        valida NUNCA abra el acceso por no poder preguntar. Devuelve el JSON con
        `roles`, que es lo que la puerta de inteligencia necesita para exigir
        operador/admin con la misma semantica que `/v1/admin/acudientes`."""
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

    async def datos_directorio(self, dane: str) -> dict[str, Any] | None:
        """Los datos DUEB (direccion, contacto, sitio) del colegio con ese DANE,
        para pre-llenar el perfil del colegio nuevo. `None` si el DANE no esta en
        el directorio o identidad no responde: la subida degrada a nombre+dane,
        no se cae (el revisor completa a mano lo que falte)."""
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/directorio/{dane}")
                if respuesta.status_code == 404:
                    return None
                respuesta.raise_for_status()
                return dict(respuesta.json())
        except httpx.HTTPError:
            return None


@dataclass
class ClienteComercio:
    """El checkout server-to-server: Inteligencia arma la orden, Comercio cobra.

    El navegador nunca habla con Comercio directo: manda solo `trabajo_id` +
    perfil + direccion, e Inteligencia -que tiene el `usuario_id` del trabajo y
    las lineas del kit- monta la orden aqui. Asi el id canonico de cada producto
    (que Comercio necesita para reservar) jamas sale a la superficie publica
    (RPO cero, ADR 0017): la orden viaja con sku y Comercio resuelve el id.

    Devuelve `(estado_http, cuerpo)` en vez de levantar en los rechazos de
    negocio: un `422 precio_cambiado` es una respuesta legitima que el acudiente
    tiene que ver, no un fallo. Solo la caida de red o un 5xx es `RemotoCaido`.
    """

    base: str = ""
    cliente: httpx.AsyncClient | None = None

    def _base(self) -> str:
        return self.base or url_comercio()

    async def crear_orden(self, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return await self._postear("/v1/ordenes", cuerpo)

    async def iniciar_pago(self, pedido_id: str, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return await self._postear(f"/v1/ordenes/{pedido_id}/pago", cuerpo)

    async def pedidos_pagados(self) -> list[dict[str, Any]]:
        """Los pedidos en estado confirmado con su trabajo: `{trabajo_id,
        usuario_id, estado}`. Comercio es el dueno de la definicion de "pagado";
        aqui solo se lee para cruzar con los hijos del trabajo. Una caida de
        Comercio es `RemotoCaido`, no un cruce a medias."""
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.get(f"{self._base()}/v1/comercio/pedidos-pagados")
                respuesta.raise_for_status()
        except httpx.HTTPError as error:
            raise RemotoCaido("comercio", str(error)) from error
        return list(respuesta.json().get("pedidos") or ())

    async def _postear(self, ruta: str, cuerpo: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                respuesta = await cliente.post(f"{self._base()}{ruta}", json=cuerpo)
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
