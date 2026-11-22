"""Repartidor: la mitad de entrega de los eventos que avisan al acudiente.

Decisiones:
- Inteligencia (`kits_publicados`) y Comercio (`pedido_pagado`) escriben su evento en su bandeja en
  la misma transaccion que el cambio; este proceso lo convierte en un aviso.
- Con `RABBITMQ_URL` consume la cola `operacion.avisos` y no abre ningun motor a otra base; sin
  broker lee las bandejas con `FOR UPDATE SKIP LOCKED`, para que dos repartidores no tomen el mismo
  evento.
- Un solo `notificacion` por evento garantiza una entrega unica aunque el broker lo traiga dos veces.

Uso:  python -m tukit_operacion.repartidor [--seguir]
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
from tukit_comun.broker import sink_desde_entorno, url_broker
from tukit_comun.config import url_desde_entorno
from tukit_comun.consumidor import Consumidor, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente
from tukit_comun.topologia import AVISOS

from .dominio.reparto import datos_plantilla, destinatario_de_la_cola, destinatario_en_carga, plantilla_para
from .notificador import Contacto, Envio, Notificador, notificador_desde_entorno
from .remoto import ClienteIdentidad
from .repositorios import RepoNotificaciones
from .repositorios.notificaciones import NOTIFICACION

__all__ = ["NOTIFICACION", "Repartidor", "correr_una_vez", "escuchar_cola", "main"]


def _trabajo_reflejado() -> Table:
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

    origen: str | None
    motor_operacion: Any
    motor_origen: AsyncEngine | None
    notificador: Notificador
    identidad: ClienteIdentidad
    sink: Any = None

    async def pasada(self, *, limite: int = 100) -> int:
        if self.origen is None or self.motor_origen is None:
            raise ValueError("sin bandeja de origen no hay pasada: con RabbitMQ se usa `manejar`")
        return await drenar(self.motor_origen, self._entregar, limite=limite, sink=self.sink)

    async def _entregar(self, conexion_origen: Any, fila: Any) -> Resultado:
        assert self.origen is not None
        return await self._avisar(self.origen, fila)

    async def manejar(self, evento: Evento) -> Resultado:
        return await self._avisar(evento.origen, evento)

    async def _avisar(self, origen: str, fila: Any) -> Resultado:
        plantilla = plantilla_para(fila.tipo)
        if plantilla is None:
            return Resultado.OMITIR

        if await self._ya_avisado(origen, fila.id):
            return Resultado.HECHO

        usuario_id = await self._destinatario(fila)
        if usuario_id is None:
            return Resultado.REINTENTAR

        colegios: dict[str, str | None] = {}
        if fila.tipo == "kits_publicados":
            carga = fila.carga or {}
            ids = [
                str(li.get("colegio_id") or "") for li in carga.get("listas") or () if isinstance(li, dict)
            ]
            ids.append(str(carga.get("colegio_id") or ""))
            for colegio_id in dict.fromkeys(i for i in ids if i):
                colegios[colegio_id] = await self.identidad.nombre_colegio(colegio_id)
        datos = datos_plantilla(
            fila.tipo, fila.agregado_id, fila.carga, base_web=_url_web(), colegios=colegios
        )
        contacto = await self._resolver_contacto(usuario_id)
        envio = await self.notificador.enviar(contacto, plantilla, datos)

        await self._registrar_notificacion(
            usuario_id, envio.canal, plantilla, datos, envio.exito, origen, fila.id, envio
        )
        return Resultado.HECHO if envio.exito or envio.omitido else Resultado.REINTENTAR

    async def _ya_avisado(self, origen: str, evento_id: int) -> bool:
        async with self.motor_operacion.sesion() as db:
            return await RepoNotificaciones(await db.connection()).ya_avisado(origen, evento_id)

    async def _destinatario(self, fila: Any) -> str | None:
        if self.motor_origen is None:
            return destinatario_de_la_cola(fila.tipo, fila.carga)
        en_carga = destinatario_en_carga(fila.tipo, fila.carga)
        if en_carga is not None:
            return en_carga
        if fila.tipo == "kits_publicados":
            return await self._usuario_del_trabajo(fila.agregado_id)
        return None

    async def _usuario_del_trabajo(self, trabajo_id: uuid.UUID) -> str | None:
        assert self.motor_origen is not None
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
        evento_origen: str,
        evento_id: int,
        envio: Envio | None = None,
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
                evento_origen=evento_origen,
                evento_id=evento_id,
                asunto=envio.asunto if envio else None,
                detalle=envio.detalle if envio else None,
                destino_dominio=envio.destino_dominio if envio else None,
                omitida=bool(envio and envio.omitido),
            )


def _url_web() -> str:
    return os.environ.get("TUKIT_WEB_URL", "http://localhost:3000").rstrip("/")


def _motor_lectura(servicio: str) -> AsyncEngine:
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez() -> dict[str, int]:
    motor_operacion = crear_motor("operacion")
    notificador = notificador_desde_entorno()
    identidad = ClienteIdentidad()
    sink = sink_desde_entorno()
    resultado: dict[str, int] = {}
    try:
        for origen in ("inteligencia", "comercio", "operacion"):
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


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    motor_operacion = crear_motor("operacion")
    repartidor = Repartidor(
        origen=None,
        motor_operacion=motor_operacion,
        motor_origen=None,
        notificador=notificador_desde_entorno(),
        identidad=ClienteIdentidad(),
    )
    try:
        return await consumir(
            url,
            Consumidor(cola=AVISOS, manejar=repartidor.manejar),
            seguir=seguir,
            proceso="operacion-repartidor",
            intervalo=intervalo,
        )
    finally:
        await motor_operacion.cerrar()


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

    url = url_broker()
    if url:
        avisos = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
        if not argumentos.seguir:
            print(f"[repartidor] mensajes de {AVISOS.nombre}: {avisos}")
        return 0
    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        entregas = asyncio.run(correr_una_vez())
        print(f"[repartidor] entregados: {entregas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
