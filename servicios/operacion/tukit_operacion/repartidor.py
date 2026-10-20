"""El repartidor: la mitad de ENTREGA que faltaba (§10 del contrato).

Inteligencia escribe `kits_publicados` en su bandeja al publicar un trabajo, y
Comercio escribe `pedido_pagado` al confirmar un pago, cada uno en la misma
transaccion que el cambio que lo origina. Pero hasta ahora nadie los recogia:
el evento quedaba escrito y el aviso al acudiente no salia. Este proceso cierra
esa deuda.

    python -m tukit_operacion.repartidor        # una pasada
    python -m tukit_operacion.repartidor --seguir   # bucle

Lo que hace, por evento no publicado:

1. Lee la bandeja de origen (Inteligencia, Comercio) con `FOR UPDATE SKIP
   LOCKED` para que dos repartidores no tomen el mismo evento.
2. Resuelve el `usuario_id` destinatario (de `trabajo_pipeline.usuario_id` para
   `kits_publicados`, o de la carga del evento para `pedido_pagado`).
3. Crea `operacion.notificacion` POR IDENTIFICADOR (sin copiar contacto),
   resuelve el contacto contra Identidad EN EL MOMENTO del envio, envia por el
   `Notificador`, y marca la fila de origen como publicada (o sube `intentos`).

**Un evento, un aviso** (H-B-03, ADR 0042). El aviso sale y su `notificacion` se
guarda en la base de Operacion ANTES de que la bandeja de origen marque el
evento y lo publique al broker. Si eso falla (RabbitMQ caido), la bandeja vuelve
atras y la siguiente pasada trae el mismo evento. Por eso la notificacion
guarda de que evento sale, y un evento que ya tiene su aviso `enviada` se da
por entregado sin volver a enviar: la bandeja lo marca y lo publica.

**La unica excepcion a la frontera de bases.** Un servicio no toca la base de
otro; el patron outbox es la excepcion declarada, y esta es la que la ejerce:
el repartidor abre motores de LECTURA a las bases de Inteligencia y Comercio. El
nombre de esas bases NO se escribe aqui: `url_desde_entorno` lo deriva en la
libreria a partir del nombre del servicio, asi que este archivo no contiene el
string de ninguna base ajena (regla 3 de las fronteras).

**Una caida no lo mata** (ADR 0041). El bucle corre sobre `bucle_resiliente`:
si Postgres o RabbitMQ no responden, espera y reintenta la pasada, y cada pasada
abre de nuevo sus motores y su sink. Un error de programacion sigue terminando
el proceso.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import MetaData, Table, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, drenar
from tukit_comun.bd import crear_motor
from tukit_comun.broker import sink_desde_entorno
from tukit_comun.config import url_desde_entorno
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente

from .dominio.reparto import datos_plantilla, destinatario_en_carga, plantilla_para
from .notificador import Contacto, Notificador, notificador_desde_entorno
from .remoto import ClienteIdentidad
from .repositorios import RepoNotificaciones
from .repositorios.notificaciones import NOTIFICACION

# `NOTIFICACION` se reexporta desde el repo: el SQL de la notificacion vive alli
# (ADR 0019), pero las pruebas de caja blanca lo importan de aqui. `__all__` lo
# hace explicito para que no lo pode un linter por "no usado".
__all__ = ["NOTIFICACION", "Repartidor", "correr_una_vez", "main"]


def _trabajo_reflejado() -> Table:
    """La tabla de trabajos de Inteligencia, reflejada para leer el `usuario_id`
    destinatario de un `kits_publicados`. Misma regla: se declara, no se importa."""
    from sqlalchemy import Column, Uuid

    metadatos = MetaData()
    return Table(
        "trabajo_pipeline",
        metadatos,
        Column("id", Uuid(as_uuid=True), primary_key=True),
        Column("usuario_id", Uuid(as_uuid=True)),
    )


@dataclass
class Repartidor:
    """Recoge eventos de una bandeja de origen y entrega su aviso.

    `origen` es el nombre del servicio dueno de la bandeja (`inteligencia`,
    `comercio`). Los motores y el notificador se inyectan para poder probar sin
    Postgres ni red; en produccion salen del entorno.
    """

    origen: str
    motor_operacion: Any
    motor_origen: AsyncEngine
    notificador: Notificador
    identidad: ClienteIdentidad
    sink: Any = None

    async def pasada(self, *, limite: int = 100) -> int:
        """Una pasada: procesa hasta `limite` eventos no publicados. Devuelve
        cuantos entrego con exito.

        El drenar/SKIP LOCKED/marcar-publicado/subir-intentos vive en
        `tukit_comun.bandeja` (ADR 0022); aqui solo se aporta el `manejar` que
        entrega el aviso. La bandeja de origen puede ser una base ajena (la
        excepcion outbox declarada). Si hay `sink` (broker), cada evento
        entregado se publica ademas a RabbitMQ; sin el, solo notifica (hoy)."""
        return await drenar(self.motor_origen, self._entregar, limite=limite, sink=self.sink)

    async def _entregar(self, conexion_origen: Any, fila: Any) -> Resultado:
        plantilla = plantilla_para(fila.tipo)
        if plantilla is None:
            # Un tipo que este repartidor no maneja: OMITIR lo marca publicado
            # para no reprocesarlo en cada pasada. No es un fallo, es "no me toca".
            return Resultado.OMITIR

        if await self._ya_avisado(fila.id):
            # La bandeja reentrega un evento que ya se aviso (la pasada anterior
            # envio y registro, pero no alcanzo a marcarlo ni a publicarlo). HECHO
            # lo marca y lo publica; el acudiente no recibe un segundo aviso.
            return Resultado.HECHO

        usuario_id = await self._destinatario(fila)
        if usuario_id is None:
            return Resultado.REINTENTAR

        datos = datos_plantilla(fila.tipo, fila.agregado_id, fila.carga, base_web=_url_web())
        # Se crea la notificacion POR ID, sin contacto, y se envia resolviendo
        # el contacto al vuelo. Si el envio falla, REINTENTAR sube intentos y se
        # reintenta en la proxima pasada; la notificacion queda como fallida.
        contacto = await self._resolver_contacto(usuario_id)
        envio = await self.notificador.enviar(contacto, plantilla, datos)

        await self._registrar_notificacion(usuario_id, envio.canal, plantilla, datos, envio.exito, fila.id)
        return Resultado.HECHO if envio.exito else Resultado.REINTENTAR

    async def _ya_avisado(self, evento_id: int) -> bool:
        async with self.motor_operacion.sesion() as db:
            return await RepoNotificaciones(await db.connection()).ya_avisado(self.origen, evento_id)

    async def _destinatario(self, fila: Any) -> str | None:
        # Si el tipo trae el usuario en la carga, el dominio lo saca (regla pura).
        en_carga = destinatario_en_carga(fila.tipo, fila.carga)
        if en_carga is not None:
            return en_carga
        # `kits_publicados` no lo trae: hay que ir a trabajo_pipeline (I/O, queda
        # en el worker; el dominio ya devolvio None para este tipo).
        if fila.tipo == "kits_publicados":
            return await self._usuario_del_trabajo(fila.agregado_id)
        return None

    async def _usuario_del_trabajo(self, trabajo_id: uuid.UUID) -> str | None:
        trabajo = _trabajo_reflejado()
        async with self.motor_origen.connect() as conexion:
            usuario = await conexion.scalar(select(trabajo.c.usuario_id).where(trabajo.c.id == trabajo_id))
        return str(usuario) if usuario is not None else None

    async def _resolver_contacto(self, usuario_id: str) -> Contacto:
        datos = await self.identidad.contacto_de(usuario_id)
        if datos is None:
            return Contacto(usuario_id=usuario_id)
        return Contacto(
            usuario_id=usuario_id,
            correo=datos.get("correo"),
            celular=datos.get("celular"),
        )

    async def _registrar_notificacion(
        self,
        usuario_id: str,
        canal: str,
        plantilla: str,
        datos: dict[str, object],
        exito: bool,
        evento_id: int,
    ) -> None:
        ahora = datetime.now(UTC)
        async with self.motor_operacion.sesion() as db:
            await RepoNotificaciones(await db.connection()).registrar(
                usuario_id=usuario_id,
                canal=canal,
                plantilla=plantilla,
                datos=datos,
                exito=exito,
                ahora=ahora,
                evento_origen=self.origen,
                evento_id=evento_id,
            )


def _url_web() -> str:
    """La base de la app del acudiente, para armar el enlace de pre-compra.

    Sale del entorno (`TUKIT_WEB_URL`); por omision el Next.js de desarrollo.
    Se recorta la barra final para no duplicarla al concatenar la ruta.
    """
    return os.environ.get("TUKIT_WEB_URL", "http://localhost:3000").rstrip("/")


def _motor_lectura(servicio: str) -> AsyncEngine:
    """Motor de solo-lectura a la base de un servicio de origen.

    El nombre de la base lo deriva `url_desde_entorno` DENTRO de la libreria a
    partir del nombre del servicio; este archivo nunca escribe `tukit_<otro>`,
    que es lo que mantiene verde la regla 3.
    """
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez() -> dict[str, int]:
    """Una pasada sobre las dos bandejas de origen. Para el cron o el arranque."""
    motor_operacion = crear_motor("operacion")
    notificador = notificador_desde_entorno()
    identidad = ClienteIdentidad()
    # El sink del broker es OPCIONAL (ADR 0022): `None` si no hay `RABBITMQ_URL`,
    # y el repartidor entrega solo por notificador (comportamiento de hoy). Con la
    # URL, cada evento entregado se publica ademas a RabbitMQ para el fan-out.
    sink = sink_desde_entorno()
    resultado: dict[str, int] = {}
    try:
        for origen in ("inteligencia", "comercio"):
            motor_origen = _motor_lectura(origen)
            try:
                repartidor = Repartidor(
                    origen=origen,
                    motor_operacion=motor_operacion,
                    motor_origen=motor_origen,
                    notificador=notificador,
                    identidad=identidad,
                    sink=sink,
                )
                resultado[origen] = await repartidor.pasada()
            finally:
                await motor_origen.dispose()
    finally:
        if sink is not None:
            await sink.cerrar()
        await motor_operacion.cerrar()
    return resultado


async def _bucle(intervalo: float, *, dormir: Callable[[float], Awaitable[None]] | None = None) -> None:
    async def _vuelta() -> None:
        entregas = await correr_una_vez()
        total = sum(entregas.values())
        if total:
            print(f"[repartidor] entregados: {entregas}")

    await bucle_resiliente(
        _vuelta, intervalo=intervalo, proceso="operacion-repartidor", dormir=dormir or asyncio.sleep
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Reparte los eventos de las bandejas de salida.")
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("operacion-repartidor")

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        entregas = asyncio.run(correr_una_vez())
        print(f"[repartidor] entregados: {entregas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
