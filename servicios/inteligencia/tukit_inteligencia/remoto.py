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

    async def emparejar(self, renglones: list[str]) -> list[dict[str, Any]]:
        cuerpo = await self._pedir("POST", "/v1/catalogo/emparejar", json={"renglones": renglones})
        return list(cuerpo.get("emparejamientos") or ())

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo: int | None = None) -> list[dict]:
        parametros: dict[str, Any] = {"colegio_id": colegio_id, "grado": grado, "por_pagina": 5}
        if anio_lectivo is not None:
            parametros["anio_lectivo"] = anio_lectivo
        cuerpo = await self._pedir("GET", "/v1/listas", params=parametros)
        return list(cuerpo.get("listas") or ())

    async def lista(self, lista_id: str) -> dict[str, Any]:
        return await self._pedir("GET", f"/v1/listas/{lista_id}")

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
    ) -> dict[str, Any]:
        """Escribe una lista percibida en el catalogo, con su evidencia.

        El PDF viaja en base64 y la percepcion cruda por pagina viaja al lado
        para que la revision humana del catalogo pueda contrastar lo que se
        importo contra lo que el modelo leyo. Inteligencia no escribe en la
        base del catalogo: le entrega el renglon y la evidencia por HTTP y es
        el catalogo quien decide como guardarlo (invariantes 1 y 3).
        """
        return await self._pedir(
            "POST",
            "/v1/admin/listas/importar",
            json={
                "colegio_id": colegio_id,
                "grado": grado,
                "anio_lectivo": anio_lectivo,
                "items": items,
                "evidencia": {
                    "documento_base64": documento_base64,
                    "percepcion_cruda": percepcion_cruda,
                },
            },
        )


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


__all__ = [
    "ESPERA_SEGUNDOS",
    "ClienteCatalogo",
    "ClienteIdentidad",
    "RemotoCaido",
    "url_catalogo",
    "url_identidad",
]
