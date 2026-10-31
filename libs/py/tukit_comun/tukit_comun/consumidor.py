"""El consumidor de una cola de RabbitMQ: confirma, reintenta, descarta y no repite (ADR 0046).

Cada consumidor (el repartidor, los dos sondeadores y el trabajador) escucha su
propia cola de la topologia y aporta solo su `manejar(evento) -> Resultado`, el
mismo que usa cuando sondea la bandeja. Lo demas vive aqui una vez:

- `HECHO` u `OMITIR`: se anota el evento en el registro, si hay, y se confirma
  (ack). Se confirma DESPUES de procesar y guardar: si el proceso cae antes, el
  broker lo vuelve a entregar.
- `REINTENTAR`, o un error que no es una caida: el mensaje va a la cola de
  reintentos con su intento en la cabecera `tukit-intentos`, y vuelve a la
  principal cuando vence la espera. Al llegar a `max_intentos`, va a la cola de
  descartados con el motivo en `tukit-motivo` y un registro de error.
- Una caida de la base o del broker (`es_caida_transitoria`) no gasta intentos:
  el mensaje vuelve a la cola (nack con reencolar) y el error sube, para que
  `bucle_resiliente` espere y reconecte.
- Un cuerpo que no es un sobre de evento va directo a descartados: reintentarlo
  no lo arregla.
- **Al menos una vez.** RabbitMQ puede entregar un mensaje dos veces (un ack que
  se pierde, un publicador que publica de nuevo). Con un `registro`, el
  consumidor salta el evento que ya proceso, por su origen y su id. El
  consumidor que es idempotente por naturaleza no lo necesita.

El correlacion_id del evento se re-vincula antes de manejarlo, como en
`drenar`, para que los registros del consumo sigan el hilo de la peticion.

`procesar` no importa `aio-pika`: recibe un mensaje con `body`, `headers`,
`ack`, `nack` y `reject`, y prueba con dobles. `escuchar` y `consumir` son los
que hablan con el broker.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import BigInteger, Column, DateTime, MetaData, String, Table, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from .bandeja import Resultado
from .http import fijar_correlacion, reset_correlacion
from .mensajes import Evento, MensajeInvalido, evento_de
from .resiliencia import bucle_resiliente, es_caida_transitoria
from .topologia import CABECERA_INTENTOS, CABECERA_MOTIVO, TOPOLOGIA, Cola, Topologia, declarar

log = logging.getLogger(__name__)

# Intentos antes de descartar. Con la espera de la cola de reintentos (10 s),
# un mensaje que falla siempre pasa unos 40 s reintentandose.
MAX_INTENTOS = 5
PREFETCH_POR_OMISION = 10
# Lo que se guarda del motivo en la cabecera: suficiente para leerlo en la consola.
_MOTIVO_MAXIMO = 500

Manejar = Callable[[Evento], Awaitable[Resultado]]


class Decision(enum.StrEnum):
    """Lo que el consumidor hizo con un mensaje."""

    HECHO = "hecho"
    OMITIDO = "omitido"
    DUPLICADO = "duplicado"
    REINTENTO = "reintento"
    DESCARTADO = "descartado"


# --- deduplicacion -----------------------------------------------------------


class Registro(Protocol):
    """Los eventos que un consumidor ya proceso, por origen e id."""

    async def ya_procesado(self, origen: str, evento_id: int) -> bool: ...

    async def marcar(self, origen: str, evento_id: int) -> None: ...


@dataclass
class RegistroEnMemoria:
    """Un registro que vive lo que vive el proceso. Para pruebas."""

    vistos: set[tuple[str, int]] = field(default_factory=set)

    async def ya_procesado(self, origen: str, evento_id: int) -> bool:
        return (origen, evento_id) in self.vistos

    async def marcar(self, origen: str, evento_id: int) -> None:
        self.vistos.add((origen, evento_id))


def eventos_procesados_reflejada(metadatos: MetaData | None = None) -> Table:
    """La tabla `evento_procesado` con la forma que espera `RegistroEnTabla`.

    El servicio que la usa la declara en sus modelos, con su migracion; aqui se
    refleja con las mismas columnas, como `bandeja_reflejada`."""
    return Table(
        "evento_procesado",
        metadatos if metadatos is not None else MetaData(),
        Column("origen", String(32), primary_key=True),
        Column("evento_id", BigInteger, primary_key=True, autoincrement=False),
        Column("procesado_en", DateTime(timezone=True), nullable=False),
    )


async def marcar_procesado(conexion: Any, origen: str, evento_id: int) -> bool:
    """Anota el evento en la transaccion de `conexion`. `False` si ya estaba.

    Para el manejador que tiene que anotarlo junto con su efecto, en la misma
    transaccion: si el efecto vuelve atras, la marca tambien. La llave primaria
    es la ultima guarda si dos entregas corren a la vez."""
    tabla = eventos_procesados_reflejada()
    ya = await conexion.scalar(
        select(tabla.c.evento_id).where(tabla.c.origen == origen, tabla.c.evento_id == evento_id)
    )
    if ya is not None:
        return False
    await conexion.execute(
        insert(tabla).values(origen=origen, evento_id=evento_id, procesado_en=datetime.now(UTC))
    )
    return True


@dataclass
class RegistroEnTabla:
    """El registro en la tabla `evento_procesado` de la base del consumidor."""

    motor: AsyncEngine

    async def ya_procesado(self, origen: str, evento_id: int) -> bool:
        tabla = eventos_procesados_reflejada()
        async with self.motor.connect() as conexion:
            encontrado = await conexion.scalar(
                select(tabla.c.evento_id).where(tabla.c.origen == origen, tabla.c.evento_id == evento_id)
            )
        return encontrado is not None

    async def marcar(self, origen: str, evento_id: int) -> None:
        async with self.motor.begin() as conexion:
            await marcar_procesado(conexion, origen, evento_id)


# --- el consumidor -----------------------------------------------------------


class Reenvio(Protocol):
    """Publica una copia del mensaje en la cola `cola` (por el exchange por
    omision), con `cabeceras`, y vuelve cuando el broker confirmo."""

    async def __call__(self, mensaje: Any, *, cola: str, cabeceras: dict[str, Any]) -> None: ...


def _intentos(cabeceras: dict[str, Any] | None) -> int:
    try:
        return max(int((cabeceras or {}).get(CABECERA_INTENTOS, 0)), 0)
    except (TypeError, ValueError):
        return 0


def _cabeceras_propias(mensaje: Any) -> dict[str, Any]:
    # Solo las nuestras: las `x-death` que pone RabbitMQ no se copian al reenviar.
    return {clave: valor for clave, valor in (mensaje.headers or {}).items() if clave.startswith("tukit-")}


@dataclass
class Consumidor:
    """Procesa los mensajes de `cola` con `manejar`."""

    cola: Cola
    manejar: Manejar
    reenviar: Reenvio | None = None
    registro: Registro | None = None
    max_intentos: int = MAX_INTENTOS

    async def procesar(self, mensaje: Any) -> Decision:
        """Procesa un mensaje y lo confirma, lo reenvia o lo descarta."""
        intentos = _intentos(mensaje.headers)
        try:
            evento = evento_de(mensaje.body, intentos=intentos)
        except MensajeInvalido as error:
            return await self._descartar(mensaje, intentos, f"mensaje invalido: {error}")

        try:
            if self.registro is not None and await self.registro.ya_procesado(evento.origen, evento.id):
                await mensaje.ack()
                return Decision.DUPLICADO
            token = fijar_correlacion(evento.correlacion_id)
            try:
                resultado = await self.manejar(evento)
            finally:
                reset_correlacion(token)
        except Exception as error:
            if es_caida_transitoria(error):
                await self._devolver(mensaje)
                raise
            log.exception("%s: el evento %s fallo", self.cola.nombre, evento.message_id)
            return await self._fallo(mensaje, evento, f"{type(error).__name__}: {error}")

        if resultado is Resultado.REINTENTAR:
            return await self._fallo(mensaje, evento, "el manejador pidio reintentar")
        try:
            if self.registro is not None:
                await self.registro.marcar(evento.origen, evento.id)
            await mensaje.ack()
        except Exception as error:
            # Procesado pero sin confirmar: vuelve a la cola y, con registro, la
            # entrega siguiente lo da por repetido.
            if es_caida_transitoria(error):
                await self._devolver(mensaje)
            raise
        return Decision.HECHO if resultado is Resultado.HECHO else Decision.OMITIDO

    async def _fallo(self, mensaje: Any, evento: Evento, motivo: str) -> Decision:
        siguiente = evento.intentos + 1
        if siguiente >= self.max_intentos:
            return await self._descartar(mensaje, siguiente, motivo)
        await self._reenviar(mensaje, self.cola.reintentos, {CABECERA_INTENTOS: siguiente})
        await mensaje.ack()
        log.warning(
            "%s: el evento %s va a reintentos (intento %d de %d): %s",
            self.cola.nombre,
            evento.message_id,
            siguiente,
            self.max_intentos,
            motivo,
        )
        return Decision.REINTENTO

    async def _descartar(self, mensaje: Any, intentos: int, motivo: str) -> Decision:
        await self._reenviar(
            mensaje,
            self.cola.descartados,
            {CABECERA_INTENTOS: intentos, CABECERA_MOTIVO: motivo[:_MOTIVO_MAXIMO]},
        )
        await mensaje.ack()
        log.error(
            "%s: mensaje %s descartado tras %d intentos: %s",
            self.cola.nombre,
            getattr(mensaje, "message_id", None),
            intentos,
            motivo,
        )
        return Decision.DESCARTADO

    async def _reenviar(self, mensaje: Any, cola: str, cabeceras: dict[str, Any]) -> None:
        if self.reenviar is None:
            raise RuntimeError("el consumidor no tiene con que reenviar: falta `reenviar`")
        await self.reenviar(mensaje, cola=cola, cabeceras={**_cabeceras_propias(mensaje), **cabeceras})

    async def _devolver(self, mensaje: Any) -> None:
        # Si el canal ya cayo, el broker lo reencola solo al cerrar la conexion.
        try:
            await mensaje.nack(requeue=True)
        except Exception:
            log.debug("%s: no se pudo devolver el mensaje; vuelve al cerrar la conexion", self.cola.nombre)


# --- el broker ---------------------------------------------------------------


def _reenvio_amqp(canal: Any) -> Reenvio:
    import aio_pika

    async def reenviar(mensaje: Any, *, cola: str, cabeceras: dict[str, Any]) -> None:
        copia = aio_pika.Message(
            body=mensaje.body,
            headers=cabeceras,
            content_type=mensaje.content_type,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=mensaje.message_id,
            type=mensaje.type,
            app_id=mensaje.app_id,
            correlation_id=mensaje.correlation_id,
        )
        await canal.default_exchange.publish(copia, routing_key=cola, mandatory=False)

    return reenviar


async def escuchar(
    url: str,
    consumidor: Consumidor,
    *,
    topologia: Topologia = TOPOLOGIA,
    prefetch: int = PREFETCH_POR_OMISION,
    hasta_vaciar: bool = False,
) -> int:
    """Escucha la cola del consumidor y devuelve cuantos mensajes proceso.

    Con `hasta_vaciar`, procesa lo que hay y vuelve (una pasada, sin `--seguir`);
    si no, escucha hasta que la conexion o el consumo terminen."""
    import aio_pika

    conexion = await aio_pika.connect_robust(url)
    try:
        canal = await conexion.channel(publisher_confirms=True)
        await canal.set_qos(prefetch_count=prefetch)
        _, colas = await declarar(canal, topologia)
        cola = colas[consumidor.cola.nombre]
        consumidor.reenviar = _reenvio_amqp(canal)
        procesados = 0
        if hasta_vaciar:
            while (mensaje := await cola.get(no_ack=False, fail=False)) is not None:
                await consumidor.procesar(mensaje)
                procesados += 1
            return procesados
        async with cola.iterator() as mensajes:
            async for mensaje in mensajes:
                await consumidor.procesar(mensaje)
                procesados += 1
        return procesados
    finally:
        await conexion.close()


async def consumir(
    url: str,
    consumidor: Consumidor,
    *,
    seguir: bool,
    proceso: str,
    intervalo: float = 5.0,
    topologia: Topologia = TOPOLOGIA,
    prefetch: int = PREFETCH_POR_OMISION,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    """Una pasada hasta vaciar la cola, o escuchar sobre `bucle_resiliente`.

    En el bucle, una caida del broker o de la base reconecta tras la espera; si
    el consumo termina sin error (el broker lo cancelo), se vuelve a escuchar
    tras `intervalo`."""
    if not seguir:
        return await escuchar(url, consumidor, topologia=topologia, prefetch=prefetch, hasta_vaciar=True)

    async def _vuelta() -> None:
        await escuchar(url, consumidor, topologia=topologia, prefetch=prefetch)

    await bucle_resiliente(_vuelta, intervalo=intervalo, proceso=proceso, dormir=dormir)
    return 0


__all__ = [
    "MAX_INTENTOS",
    "Consumidor",
    "Decision",
    "Manejar",
    "Registro",
    "RegistroEnMemoria",
    "RegistroEnTabla",
    "consumir",
    "escuchar",
    "eventos_procesados_reflejada",
    "marcar_procesado",
]
