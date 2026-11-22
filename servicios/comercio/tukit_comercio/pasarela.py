"""Puerto de pago y sus dos adaptadores: Wompi sandbox y uno falso.

Decisiones:
- Una pasarela hace tres cosas desde Comercio: `crear_transaccion` (en Wompi firma los datos del
  widget y la transaccion nace siempre PENDIENTE, nunca se aprueba de forma sincrona),
  `verificar_firma` (un webhook con firma que no cuadra se ignora) y `parsear_evento` (solo el id
  del evento, la referencia, el id de transaccion y el estado).
- No se guarda ninguna tarjeta ni dato de contacto: el acudiente los digita en el widget.
- Las llaves salen del entorno (`WOMPI_MODO`, `WOMPI_LLAVE_*`, `WOMPI_SECRETO_*`), nunca del codigo.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from .modelos import EstadoPago

URL_SANDBOX = "https://sandbox.wompi.co/v1"
URL_PRODUCCION = "https://production.wompi.co/v1"
MONEDA = "COP"
ESPERA_SEGUNDOS = 30.0

_ESTADO_WOMPI = {
    "APPROVED": EstadoPago.APROBADO,
    "DECLINED": EstadoPago.RECHAZADO,
    "VOIDED": EstadoPago.RECHAZADO,
    "ERROR": EstadoPago.RECHAZADO,
    "PENDING": EstadoPago.INICIADO,
}

_METODO_WOMPI = {"CARD": "tarjeta", "PSE": "pse", "NEQUI": "nequi"}


class PasarelaCaida(Exception):
    pass


class TransaccionNoExiste(Exception):
    pass


@dataclass(frozen=True)
class TransaccionCreada:

    referencia: str
    transaccion_id: str | None
    estado: EstadoPago
    url_redireccion: str | None = None
    widget: dict[str, Any] | None = None


@dataclass(frozen=True)
class EventoPasarela:

    evento_id: str
    referencia: str | None
    transaccion_id: str | None
    estado: EstadoPago
    monto_centavos: int | None = None
    metodo: str | None = None


class PasarelaPago(Protocol):

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

    async def consultar_por_referencia(self, referencia: str) -> EventoPasarela | None: ...

    def verificar_firma(self, evento: dict[str, Any]) -> bool: ...

    def parsear_evento(self, evento: dict[str, Any]) -> EventoPasarela: ...


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _traducir_estado(estado_wompi: str | None) -> EstadoPago:
    return _ESTADO_WOMPI.get((estado_wompi or "").upper(), EstadoPago.INICIADO)


def _evento_desde_transaccion(transaccion: dict[str, Any]) -> EventoPasarela:
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
    firma = evento.get("signature") or {}
    propiedades = firma.get("properties") or []
    datos = evento.get("data") or {}
    partes = [str(_valor_por_ruta(datos, ruta)) for ruta in propiedades]
    partes.append(str(evento.get("timestamp", "")))
    return _sha256("".join(partes) + secreto)


def _valor_por_ruta(datos: dict[str, Any], ruta: str) -> Any:
    actual: Any = datos
    for tramo in ruta.split("."):
        if isinstance(actual, dict):
            actual = actual.get(tramo)
        else:
            return ""
    return "" if actual is None else actual


@dataclass
class WompiSandbox:

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
            raise TransaccionNoExiste(transaccion_id)
        if respuesta.status_code >= 500:
            raise PasarelaCaida(f"Wompi respondio {respuesta.status_code}")
        try:
            transaccion = respuesta.json()["data"]
            moneda = transaccion.get("currency")
            comercio = transaccion.get("merchant")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise PasarelaCaida("Wompi devolvio una respuesta ilegible") from exc
        if moneda != MONEDA:
            raise TransaccionNoExiste(transaccion_id)
        if (
            isinstance(comercio, dict)
            and "public_key" in comercio
            and comercio["public_key"] != self.llave_publica
        ):
            raise TransaccionNoExiste(transaccion_id)
        try:
            return _evento_desde_transaccion(transaccion)
        except (ValueError, KeyError, TypeError) as exc:
            raise PasarelaCaida("Wompi devolvio una respuesta ilegible") from exc

    async def consultar_por_referencia(self, referencia: str) -> EventoPasarela | None:
        propio = self.cliente is None
        cliente = self.cliente or httpx.AsyncClient(timeout=ESPERA_SEGUNDOS)
        try:
            respuesta = await cliente.get(
                f"{self.base}/transactions",
                params={"reference": referencia},
                headers={"Authorization": f"Bearer {self.llave_privada}"},
            )
        except httpx.HTTPError as exc:
            raise PasarelaCaida(f"Wompi no responde: {exc}") from exc
        finally:
            if propio:
                await cliente.aclose()
        if respuesta.status_code >= 400:
            raise PasarelaCaida(f"Wompi respondio {respuesta.status_code}")
        try:
            transacciones = list(respuesta.json()["data"])
        except (ValueError, KeyError, TypeError) as exc:
            raise PasarelaCaida("Wompi devolvio una respuesta ilegible") from exc
        if not transacciones:
            return None
        reciente = max(transacciones, key=lambda t: str(t.get("created_at") or ""))
        return _evento_desde_transaccion(reciente)


@dataclass
class PasarelaFalsa:

    secreto_eventos: str = "test_events_falso"
    secreto_integridad: str = "test_integrity_falso"
    creadas: list[TransaccionCreada] = field(default_factory=list)
    montos: dict[str, int] = field(default_factory=dict)
    resultados: dict[str, str] = field(default_factory=dict)
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
                urljoin(url_redireccion, "/pago/simulado") + f"?ref={referencia}" if url_redireccion else None
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
        datos = {
            "transaction": {
                "id": transaccion_id,
                "reference": referencia,
                "status": estado_wompi,
                "amount_in_cents": monto_centavos,
            }
        }
        if metodo_wompi is not None:
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

    def fijar_resultado(self, referencia: str, estado_wompi: str) -> None:
        self.resultados[referencia] = estado_wompi

    async def consultar_por_referencia(self, referencia: str) -> EventoPasarela | None:
        estado_wompi = self.resultados.get(referencia)
        if estado_wompi is None:
            return None
        return await self.consultar_transaccion(f"falsa-{estado_wompi}-{referencia}")


_PREFIJOS_PRUEBA = {
    "WOMPI_LLAVE_PUBLICA": "pub_test_",
    "WOMPI_LLAVE_PRIVADA": "prv_test_",
    "WOMPI_SECRETO_EVENTOS": "test_events_",
    "WOMPI_SECRETO_INTEGRIDAD": "test_integrity_",
}


def pasarela_desde_entorno() -> PasarelaPago:
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
