"""El puerto de pago y sus dos adaptadores: Wompi sandbox y uno falso.

El §9 del contrato dice que la integracion vive tras un puerto `PasarelaPago`
con adaptador falso para las pruebas, y aqui esta el puerto. Tres cosas hace
una pasarela desde la vista de Comercio, y ninguna mas:

- **crear_transaccion**: arma el cobro y devuelve la referencia con la que el
  webhook la va a encontrar mas tarde. En Wompi (solo sandbox) no se llama a
  ninguna API: se firman los datos del widget de Wompi, que el navegador abre
  en un modal sin salir de Tukit; la transaccion nace SIEMPRE en PENDIENTE y
  nunca se aprueba sincronica.
- **verificar_firma**: dado el cuerpo crudo de un webhook, dice si de verdad lo
  firmo Wompi. Es lo unico que separa un cobro real de uno inventado, asi que
  un evento con firma que no cuadra se ignora.
- **parsear_evento**: saca de ese cuerpo lo unico que Comercio persiste
  (SG-03): el id del evento —para el candado de idempotencia—, la referencia,
  el id de transaccion y el estado ya traducido al vocabulario de `EstadoPago`.

Ni una tarjeta ni un dato de contacto se guardan: el acudiente los digita en
el widget de Wompi y aqui nunca se ven. Las llaves salen del entorno y NUNCA del
codigo (`WOMPI_MODO`, `WOMPI_LLAVE_*`, `WOMPI_SECRETO_*`), mismo idioma que
`cifrador_desde_entorno` de Identidad. En modo sandbox solo se aceptan llaves
de prueba (`pub_test_`, `prv_test_`, `test_events_`, `test_integrity_`).

Las formulas de firma estan verificadas contra docs.wompi.co (Colombia):

- Firma de integridad = SHA256("<referencia><monto_centavos><moneda><secreto>")
  en hexadecimal. El monto va en CENTAVOS. Es lo que autentica los datos del
  widget (`signature.integrity`).
- Firma del evento (webhook) = SHA256 de, en orden, los valores de los campos
  que el propio evento nombra en `signature.properties` (leidos de `data`),
  luego el `timestamp` (entero UNIX), y de ULTIMO el secreto de eventos. Se
  compara sin distinguir mayusculas contra `signature.checksum`.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from .modelos import EstadoPago

# El sandbox y produccion son URLs distintas con llaves distintas; nunca se
# cruzan. La de sandbox es la unica que este repositorio usa por defecto.
URL_SANDBOX = "https://sandbox.wompi.co/v1"
URL_PRODUCCION = "https://production.wompi.co/v1"
MONEDA = "COP"
ESPERA_SEGUNDOS = 30.0

# El vocabulario de Wompi (mayusculas) traducido al de `EstadoPago`. Lo que
# Wompi llama VOIDED o ERROR es, para el acudiente, un pago que no prospero.
_ESTADO_WOMPI = {
    "APPROVED": EstadoPago.APROBADO,
    "DECLINED": EstadoPago.RECHAZADO,
    "VOIDED": EstadoPago.RECHAZADO,
    "ERROR": EstadoPago.RECHAZADO,
    "PENDING": EstadoPago.INICIADO,
}

# El `payment_method_type` de Wompi traducido a los medios de Tukit; otro valor
# no se adivina y queda en `None`.
_METODO_WOMPI = {"CARD": "tarjeta", "PSE": "pse", "NEQUI": "nequi"}


class PasarelaCaida(Exception):
    """La pasarela no respondio bien (red caida o 5xx): reintentar mas tarde."""


class TransaccionNoExiste(Exception):
    """La pasarela no conoce esa transaccion."""


@dataclass(frozen=True)
class TransaccionCreada:
    """Lo que Comercio necesita saber tras mandar a cobrar. Sin datos de medio."""

    referencia: str
    transaccion_id: str | None
    estado: EstadoPago
    # A donde mandar al acudiente para completar el pago, cuando la pasarela lo
    # da. `None` en flujos que no redirigen.
    url_redireccion: str | None = None
    # Lo que el navegador le pasa a `new WidgetCheckout({...})` de Wompi para
    # abrir el pago en un modal sin salir de Tukit. `None` si no hay widget.
    widget: dict[str, Any] | None = None


@dataclass(frozen=True)
class EventoPasarela:
    """El evento del webhook, reducido a lo unico que se persiste (SG-03)."""

    evento_id: str
    referencia: str | None
    transaccion_id: str | None
    estado: EstadoPago
    monto_centavos: int | None = None
    metodo: str | None = None


class PasarelaPago(Protocol):
    """El puerto. Comercio depende de esto, no de Wompi."""

    async def crear_transaccion(
        self,
        *,
        referencia: str,
        monto_centavos: int,
        correo_cliente: str,
        metodo: str,
        url_redireccion: str | None = None,
    ) -> TransaccionCreada: ...

    async def consultar_transaccion(self, transaccion_id: str) -> EventoPasarela: ...

    def verificar_firma(self, evento: dict[str, Any]) -> bool: ...

    def parsear_evento(self, evento: dict[str, Any]) -> EventoPasarela: ...


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _traducir_estado(estado_wompi: str | None) -> EstadoPago:
    return _ESTADO_WOMPI.get((estado_wompi or "").upper(), EstadoPago.INICIADO)


def _evento_desde_transaccion(transaccion: dict[str, Any]) -> EventoPasarela:
    """Reduce una transaccion de Wompi a lo que se persiste. La clave de
    idempotencia es `<transaccion>:<ESTADO>`: cada cambio de estado cuenta una
    vez, pero un reenvio del mismo estado no."""
    transaccion_id = transaccion.get("id")
    estado_wompi = str(transaccion.get("status") or "")
    return EventoPasarela(
        evento_id=f"{transaccion_id or ''}:{estado_wompi.upper()}",
        referencia=transaccion.get("reference"),
        transaccion_id=transaccion_id,
        estado=_traducir_estado(estado_wompi),
        monto_centavos=transaccion.get("amount_in_cents"),
        metodo=_METODO_WOMPI.get(str(transaccion.get("payment_method_type") or "").upper()),
    )


def firma_integridad(referencia: str, monto_centavos: int, secreto: str, moneda: str = MONEDA) -> str:
    """SHA256(referencia + monto_centavos + moneda + secreto). Monto en CENTAVOS.

    Funcion pura y expuesta a proposito: es la que una prueba puede fijar
    contra un vector conocido sin levantar la pasarela entera.
    """
    return _sha256(f"{referencia}{monto_centavos}{moneda}{secreto}")


def datos_widget(
    *,
    llave_publica: str,
    referencia: str,
    monto_centavos: int,
    secreto_integridad: str,
    correo: str,
    url_redireccion: str | None = None,
) -> dict[str, Any]:
    """Las opciones de `new WidgetCheckout({...})`, con los nombres de Wompi.

    Se arman aqui y no en el navegador porque la firma de integridad necesita el
    secreto, que nunca sale del servidor. Sin red.

    `redirectUrl` hace falta para PSE: el banco se lleva la pestana entera, el
    modal y su callback se pierden, y solo con `redirectUrl` el comprobante de
    Wompi devuelve al acudiente a Tukit. Wompi acepta localhost como retorno,
    pero su CDN responde 403 si `redirect-url` va en una URL: el navegador abre
    el widget con `bootstrapTransport: "postmessage"` (apps/web/src/lib/wompi.ts)
    para que la configuracion viaje por mensaje y no en la URL del iframe.
    Con tarjeta o Nequi el modal sigue vivo y manda el callback.
    """
    datos: dict[str, Any] = {
        "publicKey": llave_publica,
        "currency": MONEDA,
        "amountInCents": monto_centavos,
        "reference": referencia,
        "signature": {"integrity": firma_integridad(referencia, monto_centavos, secreto_integridad)},
        "customerData": {"email": correo},
    }
    if url_redireccion:
        datos["redirectUrl"] = url_redireccion
    return datos


def firma_evento(evento: dict[str, Any], secreto: str) -> str:
    """La firma que un webhook de Wompi debe traer, recalculada del cuerpo.

    Sigue la receta de la documentacion: se leen los valores de los campos que
    el evento nombra en `signature.properties` (rutas con punto dentro de
    `data`), en ese orden; se les concatena el `timestamp`; y se cierra con el
    secreto de eventos. El resultado es el SHA256 hexadecimal.
    """
    firma = evento.get("signature") or {}
    propiedades = firma.get("properties") or []
    datos = evento.get("data") or {}
    partes = [str(_valor_por_ruta(datos, ruta)) for ruta in propiedades]
    partes.append(str(evento.get("timestamp", "")))
    return _sha256("".join(partes) + secreto)


def _valor_por_ruta(datos: dict[str, Any], ruta: str) -> Any:
    """Resuelve `transaction.status` navegando `datos["transaction"]["status"]`.

    Las `properties` del evento vienen como rutas con punto relativas a `data`.
    Un tramo ausente devuelve cadena vacia para que la firma no cuadre por
    accidente en vez de reventar.
    """
    actual: Any = datos
    for tramo in ruta.split("."):
        if isinstance(actual, dict):
            actual = actual.get(tramo)
        else:
            return ""
    return "" if actual is None else actual


@dataclass
class WompiSandbox:
    """Adaptador real contra Wompi. Las llaves salen del entorno.

    Crear es puro (firma los datos del widget). El `cliente` httpx queda para
    las consultas a la API de Wompi; se inyecta en las pruebas para no salir a
    la red. No guarda nada.
    """

    llave_publica: str = ""
    llave_privada: str = ""
    secreto_eventos: str = ""
    secreto_integridad: str = ""
    base: str = URL_SANDBOX
    cliente: httpx.AsyncClient | None = None

    async def crear_transaccion(
        self,
        *,
        referencia: str,
        monto_centavos: int,
        correo_cliente: str,
        metodo: str,
        url_redireccion: str | None = None,
    ) -> TransaccionCreada:
        # No hay llamada a Wompi: el navegador abre el widget con estos datos
        # firmados. El id de transaccion llega despues, en el callback del
        # widget (que lo manda a sincronizar) o por el webhook.
        return TransaccionCreada(
            referencia=referencia,
            transaccion_id=None,
            estado=EstadoPago.INICIADO,
            widget=datos_widget(
                llave_publica=self.llave_publica,
                referencia=referencia,
                monto_centavos=monto_centavos,
                secreto_integridad=self.secreto_integridad,
                correo=correo_cliente,
                url_redireccion=url_redireccion,
            ),
        )

    def verificar_firma(self, evento: dict[str, Any]) -> bool:
        firma = evento.get("signature") or {}
        declarada = firma.get("checksum")
        if not declarada:
            return False
        calculada = firma_evento(evento, self.secreto_eventos)
        return calculada.lower() == str(declarada).lower()

    def parsear_evento(self, evento: dict[str, Any]) -> EventoPasarela:
        datos = evento.get("data") or {}
        return _evento_desde_transaccion(datos.get("transaction") or {})

    async def consultar_transaccion(self, transaccion_id: str) -> EventoPasarela:
        """GET publico a `/transactions/{id}`: la fuente de verdad al regreso."""
        propio = self.cliente is None
        cliente = self.cliente or httpx.AsyncClient(timeout=ESPERA_SEGUNDOS)
        try:
            respuesta = await cliente.get(f"{self.base}/transactions/{transaccion_id}")
        except httpx.HTTPError as exc:
            raise PasarelaCaida(f"Wompi no responde: {exc}") from exc
        finally:
            if propio:
                await cliente.aclose()
        if 400 <= respuesta.status_code < 500:
            # Cualquier 4xx (404, 422...) es "esa transaccion no existe" para nosotros.
            raise TransaccionNoExiste(transaccion_id)
        if respuesta.status_code >= 500:
            raise PasarelaCaida(f"Wompi respondio {respuesta.status_code}")
        try:
            transaccion = respuesta.json()["data"]
            moneda = transaccion.get("currency")
            comercio = transaccion.get("merchant")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise PasarelaCaida("Wompi devolvio una respuesta ilegible") from exc
        # El GET es publico: cualquier comercio podria crear una transaccion con
        # nuestra referencia. Se exige la moneda y, si Wompi dice de que comercio
        # es, que sea el nuestro. En produccion esta verificacion del comercio debe
        # ser obligatoria, y el campo `merchant.public_key` hay que confirmarlo en
        # el primer pago real de sandbox (aqui, si falta, se acepta).
        if moneda != MONEDA:
            raise TransaccionNoExiste(transaccion_id)
        if isinstance(comercio, dict) and "public_key" in comercio:
            if comercio["public_key"] != self.llave_publica:
                raise TransaccionNoExiste(transaccion_id)
        try:
            return _evento_desde_transaccion(transaccion)
        except (ValueError, KeyError, TypeError) as exc:
            raise PasarelaCaida("Wompi devolvio una respuesta ilegible") from exc


@dataclass
class PasarelaFalsa:
    """Pasarela determinista para las pruebas y el desarrollo sin red.

    Crea transacciones con id predecible, firma sus propios eventos con el mismo
    algoritmo que Wompi (asi la verificacion se ejerce de verdad) y sabe fabricar
    un webhook sintetico para un estado dado. No sale a ninguna parte.
    """

    secreto_eventos: str = "test_events_falso"
    secreto_integridad: str = "test_integrity_falso"
    # Registro de lo creado, para que una prueba compruebe que se llamo.
    creadas: list[TransaccionCreada] = field(default_factory=list)
    # Monto en centavos por referencia, para la pagina de pago simulado.
    montos: dict[str, int] = field(default_factory=dict)
    _contador: int = 0

    async def crear_transaccion(
        self,
        *,
        referencia: str,
        monto_centavos: int,
        correo_cliente: str,
        metodo: str,
        url_redireccion: str | None = None,
    ) -> TransaccionCreada:
        self._contador += 1
        creada = TransaccionCreada(
            referencia=referencia,
            transaccion_id=f"falsa-{self._contador}",
            estado=EstadoPago.INICIADO,
            url_redireccion=(
                urljoin(url_redireccion, "/pago/simulado") + f"?ref={referencia}"
                if url_redireccion
                else None
            ),
        )
        self.montos[referencia] = monto_centavos
        self.creadas.append(creada)
        return creada

    def emitir_evento(
        self,
        *,
        referencia: str,
        transaccion_id: str,
        estado_wompi: str,
        monto_centavos: int,
        timestamp: int = 1_700_000_000,
        metodo_wompi: str | None = None,
    ) -> dict[str, Any]:
        """Un webhook con la MISMA forma y firma que mandaria Wompi.

        `signature.properties` nombra los campos firmados; `firma_evento` los
        vuelve a leer al verificar, asi que la firma cuadra si y solo si el
        cuerpo no se altero.
        """
        datos = {
            "transaction": {
                "id": transaccion_id,
                "reference": referencia,
                "status": estado_wompi,
                "amount_in_cents": monto_centavos,
            }
        }
        if metodo_wompi is not None:
            # Informativo: no entra en las propiedades firmadas.
            datos["transaction"]["payment_method_type"] = metodo_wompi
        evento: dict[str, Any] = {
            "id": f"evt-{transaccion_id}",
            "event": "transaction.updated",
            "timestamp": timestamp,
            "data": datos,
            "signature": {
                "properties": [
                    "transaction.id",
                    "transaction.status",
                    "transaction.amount_in_cents",
                ],
            },
        }
        evento["signature"]["checksum"] = firma_evento(evento, self.secreto_eventos)
        return evento

    def verificar_firma(self, evento: dict[str, Any]) -> bool:
        firma = evento.get("signature") or {}
        declarada = firma.get("checksum")
        if not declarada:
            return False
        return firma_evento(evento, self.secreto_eventos).lower() == str(declarada).lower()

    def parsear_evento(self, evento: dict[str, Any]) -> EventoPasarela:
        datos = evento.get("data") or {}
        return _evento_desde_transaccion(datos.get("transaction") or {})

    async def consultar_transaccion(self, transaccion_id: str) -> EventoPasarela:
        """Descompone `falsa-<ESTADO>-<referencia>`; el monto sale de `montos`."""
        partes = transaccion_id.split("-", 2)
        if len(partes) != 3 or partes[0] != "falsa" or partes[1] not in _ESTADO_WOMPI:
            raise TransaccionNoExiste(transaccion_id)
        _, estado_wompi, referencia = partes
        if referencia not in self.montos:
            raise TransaccionNoExiste(transaccion_id)
        return _evento_desde_transaccion(
            {
                "id": transaccion_id,
                "reference": referencia,
                "status": estado_wompi,
                "amount_in_cents": self.montos[referencia],
                "payment_method_type": "PSE",
            }
        )


_PREFIJOS_PRUEBA = {
    "WOMPI_LLAVE_PUBLICA": "pub_test_",
    "WOMPI_LLAVE_PRIVADA": "prv_test_",
    "WOMPI_SECRETO_EVENTOS": "test_events_",
    "WOMPI_SECRETO_INTEGRIDAD": "test_integrity_",
}


def pasarela_desde_entorno() -> PasarelaPago:
    """Elige el adaptador segun `WOMPI_MODO`, mismo idioma que el cifrador.

    `sandbox` exige las cuatro llaves en el entorno y falla ruidoso si falta
    alguna: una pasarela a medio configurar que cobrara de verdad es peor que
    uno que no arranca. Ademas exige que cada llave tenga el prefijo de prueba
    (`pub_test_`, `prv_test_`, `test_events_`, `test_integrity_`). `falso` (por
    omision) no toca la red; cualquier otro modo es un error ruidoso.
    """
    modo = os.environ.get("WOMPI_MODO", "falso").strip().lower()
    if modo == "sandbox":
        faltan = [
            nombre
            for nombre in (
                "WOMPI_LLAVE_PUBLICA",
                "WOMPI_LLAVE_PRIVADA",
                "WOMPI_SECRETO_EVENTOS",
                "WOMPI_SECRETO_INTEGRIDAD",
            )
            if not os.environ.get(nombre)
        ]
        if faltan:
            raise RuntimeError(
                "WOMPI_MODO=sandbox exige las llaves en el entorno; faltan: " + ", ".join(faltan)
            )
        for nombre, prefijo in _PREFIJOS_PRUEBA.items():
            if not os.environ[nombre].startswith(prefijo):
                raise RuntimeError(
                    f"{nombre} no es una llave de prueba (debe empezar por {prefijo}); "
                    "esta rama solo opera en sandbox"
                )
        return WompiSandbox(
            llave_publica=os.environ["WOMPI_LLAVE_PUBLICA"],
            llave_privada=os.environ["WOMPI_LLAVE_PRIVADA"],
            secreto_eventos=os.environ["WOMPI_SECRETO_EVENTOS"],
            secreto_integridad=os.environ["WOMPI_SECRETO_INTEGRIDAD"],
        )
    if modo != "falso":
        raise RuntimeError(f"WOMPI_MODO={modo!r} no es valido; usa 'falso' o 'sandbox'")
    return PasarelaFalsa()


__all__ = [
    "PasarelaPago",
    "TransaccionCreada",
    "EventoPasarela",
    "PasarelaCaida",
    "TransaccionNoExiste",
    "WompiSandbox",
    "PasarelaFalsa",
    "pasarela_desde_entorno",
    "firma_integridad",
    "firma_evento",
    "datos_widget",
    "URL_SANDBOX",
    "URL_PRODUCCION",
]
