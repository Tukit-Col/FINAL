"""El puerto de pago y sus dos adaptadores: Wompi sandbox y uno falso.

El §9 del contrato dice que la integracion vive tras un puerto `PasarelaPago`
con adaptador falso para las pruebas, y aqui esta el puerto. Tres cosas hace
una pasarela desde la vista de Comercio, y ninguna mas:

- **crear_transaccion**: manda a cobrar y devuelve la referencia con la que el
  webhook la va a encontrar mas tarde. En Wompi la transaccion nace SIEMPRE en
  PENDIENTE; nunca se aprueba sincronica.
- **verificar_firma**: dado el cuerpo crudo de un webhook, dice si de verdad lo
  firmo Wompi. Es lo unico que separa un cobro real de uno inventado, asi que
  un evento con firma que no cuadra se ignora.
- **parsear_evento**: saca de ese cuerpo lo unico que Comercio persiste
  (SG-03): el id del evento —para el candado de idempotencia—, la referencia,
  el id de transaccion y el estado ya traducido al vocabulario de `EstadoPago`.

Ni una tarjeta, ni un `acceptance_token`, ni un dato de contacto se guardan:
entran, viajan a Wompi y se olvidan. Las llaves salen del entorno y NUNCA del
codigo (`WOMPI_MODO`, `WOMPI_LLAVE_*`, `WOMPI_SECRETO_*`), mismo idioma que
`cifrador_desde_entorno` de Identidad.

Las formulas de firma estan verificadas contra docs.wompi.co (Colombia):

- Firma de integridad = SHA256("<referencia><monto_centavos><moneda><secreto>")
  en hexadecimal. El monto va en CENTAVOS. Es lo que autentica el POST de
  creacion.
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


@dataclass(frozen=True)
class TransaccionCreada:
    """Lo que Comercio necesita saber tras mandar a cobrar. Sin datos de medio."""

    referencia: str
    transaccion_id: str | None
    estado: EstadoPago
    # A donde mandar al acudiente para completar el pago, cuando la pasarela lo
    # da. `None` en flujos que no redirigen.
    url_redireccion: str | None = None


@dataclass(frozen=True)
class EventoPasarela:
    """El evento del webhook, reducido a lo unico que se persiste (SG-03)."""

    evento_id: str
    referencia: str | None
    transaccion_id: str | None
    estado: EstadoPago


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

    def verificar_firma(self, evento: dict[str, Any]) -> bool: ...

    def parsear_evento(self, evento: dict[str, Any]) -> EventoPasarela: ...


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _traducir_estado(estado_wompi: str | None) -> EstadoPago:
    return _ESTADO_WOMPI.get((estado_wompi or "").upper(), EstadoPago.INICIADO)


def firma_integridad(referencia: str, monto_centavos: int, secreto: str, moneda: str = MONEDA) -> str:
    """SHA256(referencia + monto_centavos + moneda + secreto). Monto en CENTAVOS.

    Funcion pura y expuesta a proposito: es la que una prueba puede fijar
    contra un vector conocido sin levantar la pasarela entera.
    """
    return _sha256(f"{referencia}{monto_centavos}{moneda}{secreto}")


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

    Se inyecta un `cliente` httpx en las pruebas de integracion para no salir a
    la red; en produccion abre el suyo por llamada. No guarda nada: es un puente
    de ida (crear) y de verificacion (webhook).
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
        propio = self.cliente is None
        cliente = self.cliente or httpx.AsyncClient(timeout=ESPERA_SEGUNDOS)
        try:
            token = await self._token_aceptacion(cliente)
            cuerpo: dict[str, Any] = {
                "acceptance_token": token,
                "amount_in_cents": monto_centavos,
                "currency": MONEDA,
                "customer_email": correo_cliente,
                "reference": referencia,
                "signature": firma_integridad(referencia, monto_centavos, self.secreto_integridad),
            }
            if url_redireccion:
                cuerpo["redirect_url"] = url_redireccion
            respuesta = await cliente.post(
                f"{self.base}/transactions",
                headers={"Authorization": f"Bearer {self.llave_privada}"},
                json=cuerpo,
            )
            respuesta.raise_for_status()
            datos = respuesta.json().get("data") or {}
            return TransaccionCreada(
                referencia=referencia,
                transaccion_id=datos.get("id"),
                estado=_traducir_estado(datos.get("status")),
                url_redireccion=datos.get("redirect_url") or url_redireccion,
            )
        finally:
            if propio:
                await cliente.aclose()

    async def _token_aceptacion(self, cliente: httpx.AsyncClient) -> str:
        """El `acceptance_token` que la creacion de transaccion exige.

        Sale de `GET /merchants/info` con la llave publica en cabecera; es lo
        que representa la aceptacion de los terminos y no se guarda.
        """
        respuesta = await cliente.get(
            f"{self.base}/merchants/info",
            headers={"x-merchant-public-key": self.llave_publica},
        )
        respuesta.raise_for_status()
        datos = respuesta.json().get("data") or {}
        presigned = datos.get("presigned_acceptance") or {}
        return presigned.get("acceptance_token", "")

    def verificar_firma(self, evento: dict[str, Any]) -> bool:
        firma = evento.get("signature") or {}
        declarada = firma.get("checksum")
        if not declarada:
            return False
        calculada = firma_evento(evento, self.secreto_eventos)
        return calculada.lower() == str(declarada).lower()

    def parsear_evento(self, evento: dict[str, Any]) -> EventoPasarela:
        datos = evento.get("data") or {}
        transaccion = datos.get("transaction") or {}
        return EventoPasarela(
            evento_id=str(evento.get("id") or evento.get("event_id") or transaccion.get("id") or ""),
            referencia=transaccion.get("reference"),
            transaccion_id=transaccion.get("id"),
            estado=_traducir_estado(transaccion.get("status")),
        )


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
            url_redireccion=url_redireccion,
        )
        self.creadas.append(creada)
        return creada

    def emitir_evento(
        self,
        *,
        referencia: str,
        transaccion_id: str,
        estado_wompi: str,
        timestamp: int = 1_700_000_000,
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
                "amount_in_cents": 0,
            }
        }
        evento: dict[str, Any] = {
            "id": f"evt-{transaccion_id}",
            "event": "transaction.updated",
            "timestamp": timestamp,
            "data": datos,
            "signature": {
                "properties": ["transaction.id", "transaction.status"],
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
        transaccion = datos.get("transaction") or {}
        return EventoPasarela(
            evento_id=str(evento.get("id") or ""),
            referencia=transaccion.get("reference"),
            transaccion_id=transaccion.get("id"),
            estado=_traducir_estado(transaccion.get("status")),
        )


def pasarela_desde_entorno() -> PasarelaPago:
    """Elige el adaptador segun `WOMPI_MODO`, mismo idioma que el cifrador.

    `sandbox` exige las cuatro llaves en el entorno y falla ruidoso si falta
    alguna: una pasarela a medio configurar que cobrara de verdad es peor que
    uno que no arranca. `falso` (por omision) no toca la red.
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
        return WompiSandbox(
            llave_publica=os.environ["WOMPI_LLAVE_PUBLICA"],
            llave_privada=os.environ["WOMPI_LLAVE_PRIVADA"],
            secreto_eventos=os.environ["WOMPI_SECRETO_EVENTOS"],
            secreto_integridad=os.environ["WOMPI_SECRETO_INTEGRIDAD"],
        )
    return PasarelaFalsa()


__all__ = [
    "PasarelaPago",
    "TransaccionCreada",
    "EventoPasarela",
    "WompiSandbox",
    "PasarelaFalsa",
    "pasarela_desde_entorno",
    "firma_integridad",
    "firma_evento",
    "URL_SANDBOX",
    "URL_PRODUCCION",
]
