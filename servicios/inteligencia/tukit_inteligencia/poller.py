"""Poller de `lista_verificada`: arma el kit del acudiente que estaba esperando.

Decisiones:
- Catalogo no llama a Inteligencia, porque esa arista cerraria un ciclo en el grafo de
  dependencias: escribe `lista_verificada` en su bandeja y este proceso crea un trabajo de ruta
  rapida con las preferencias que dejo el acudiente. Al terminar, el pipeline deja `kits_publicados`
  y el repartidor de Operacion envia el aviso.
- Con `RABBITMQ_URL` consume la cola `inteligencia.listas` y no abre ningun motor a la base de
  Catalogo; sin broker la sondea, y es la unica excepcion a la frontera de bases.
- La entrega es al menos una vez: cada evento se anota en `evento_procesado` por origen e id, y para
  `lista_verificada` la marca entra en la misma transaccion que crea el trabajo.

Uso:  python -m tukit_inteligencia.poller [--seguir]
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, drenar
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.broker import url_broker
from tukit_comun.config import url_desde_entorno
from tukit_comun.consumidor import Consumidor, RegistroEnTabla, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente
from tukit_comun.topologia import LISTAS

from . import apodos_subida, trabajos
from .remoto import ClienteCatalogo

_TIPO = "lista_verificada"
_TIPO_CANONICO = "lista_aprobada"


@dataclass
class Poller:
    motor_inteligencia: Any
    motor_catalogo: AsyncEngine | None
    catalogo: ClienteCatalogo

    async def pasada(self, *, limite: int = 100) -> int:
        if self.motor_catalogo is None:
            raise ValueError("sin la bandeja del Catalogo no hay pasada: con RabbitMQ se usa `manejar`")
        arrancados = await drenar(self.motor_catalogo, self._procesar, tipo=_TIPO, limite=limite)
        arrancados += await drenar(
            self.motor_catalogo, self._procesar_canonico, tipo=_TIPO_CANONICO, limite=limite
        )
        return arrancados

    async def manejar(self, evento: Evento) -> Resultado:
        if evento.tipo == _TIPO:
            return await self._procesar(None, evento, evento=(evento.origen, evento.id))
        if evento.tipo == _TIPO_CANONICO:
            return await self._procesar_canonico(None, evento)
        return Resultado.OMITIR

    async def _procesar(
        self, conexion: Any, fila: Any, *, evento: tuple[str, int] | None = None
    ) -> Resultado:
        carga = fila.carga or {}
        colegio_id = carga.get("colegio_id")
        grado = carga.get("grado")
        contacto = carga.get("contacto_referencia")
        if not colegio_id or not grado:
            return Resultado.OMITIR

        usuario_id: uuid.UUID | None = None
        origen = "colegio_grado"
        if contacto:
            try:
                usuario_id = uuid.UUID(str(contacto))
                origen = "lista_verificada"
            except (ValueError, TypeError):
                usuario_id = None
                origen = "colegio_grado"

        anio = carga.get("anio_lectivo")
        referencias = [str(r) for r in carga.get("referencias") or () if r]
        referencia = referencias[0] if referencias else "hijo-1"
        hijo: dict[str, Any] = {"referencia": referencia, "colegio_id": str(colegio_id), "grado": grado}
        if anio is not None:
            hijo["anio_lectivo"] = anio
        hijo["version_id"] = str(fila.agregado_id)
        async with self.motor_inteligencia.engine.begin() as conexion:
            apodos = await apodos_subida.tomar(conexion, str(fila.agregado_id))
        if apodos.get(referencia):
            hijo["apodo"] = apodos[referencia]

        try:
            respuesta = await trabajos.crear(
                self.motor_inteligencia,
                hijos=[hijo],
                preferencias=carga.get("preferencias") or {},
                origen=origen,
                usuario_id=usuario_id,
                en_proceso=True,
                evento=evento,
            )
        except trabajos.EventoRepetido:
            return Resultado.OMITIR
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])

        await trabajos.procesar(self.motor_inteligencia, trabajo_id, catalogo=self.catalogo)
        return Resultado.HECHO

    async def _procesar_canonico(self, conexion: Any, fila: Any) -> Resultado:
        carga = fila.carga or {}
        colegio_id = carga.get("colegio_id")
        grado = carga.get("grado")
        if not colegio_id or not grado:
            return Resultado.OMITIR
        anio = int(carga.get("anio_lectivo") or trabajos.ANIO_LECTIVO_POR_OMISION)
        version = str(fila.agregado_id)

        async with self.motor_inteligencia.engine.begin() as propia:
            ya = await trabajos.version_canonica(propia, str(colegio_id), grado, anio)
        if ya == version:
            return Resultado.OMITIR

        await armar_canonico(self.motor_inteligencia, self.catalogo, str(colegio_id), grado, anio, version)
        return Resultado.HECHO


async def armar_canonico(
    motor_inteligencia: Any,
    catalogo: Any,
    colegio_id: str,
    grado: str,
    anio: int,
    version: str,
    *,
    regenera: bool = False,
) -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor_inteligencia,
        hijos=[
            {
                "referencia": "canonico",
                "colegio_id": colegio_id,
                "grado": grado,
                "anio_lectivo": anio,
                "version_id": version,
                **({"regenera": True} if regenera else {}),
            }
        ],
        preferencias={},
        origen=trabajos.ORIGEN_CANONICO,
        en_proceso=True,
    )
    trabajo_id = uuid.UUID(respuesta["trabajo_id"])
    await trabajos.procesar(motor_inteligencia, trabajo_id, catalogo=catalogo)
    return trabajo_id


async def regenerar_canonicos(motor_inteligencia: Any, catalogo: Any) -> tuple[int, list[str]]:
    from sqlalchemy import select

    async with motor_inteligencia.engine.begin() as conexion:
        filas = list(
            await conexion.execute(
                select(
                    trabajos.KIT_CANONICO.c.colegio_id,
                    trabajos.KIT_CANONICO.c.grado,
                    trabajos.KIT_CANONICO.c.anio_lectivo,
                    trabajos.TRABAJO.c.origen,
                    trabajos.TRABAJO.c.hijos,
                ).select_from(
                    trabajos.KIT_CANONICO.join(
                        trabajos.TRABAJO, trabajos.TRABAJO.c.id == trabajos.KIT_CANONICO.c.trabajo_id
                    )
                )
            )
        )
    rearmados = 0
    saltados: list[str] = []
    fallidos: list[str] = []
    for f in filas:
        hijo = next(iter(f.hijos or ()), {})
        nombre = f"{f.colegio_id[:8]} {f.grado} ({f.origen})"
        if f.origen != trabajos.ORIGEN_CANONICO or hijo.get("basado_en") or not hijo.get("version_id"):
            saltados.append(nombre)
            continue
        async with motor_inteligencia.engine.begin() as conexion:
            version = await trabajos.version_canonica(
                conexion, f.colegio_id, f.grado, int(f.anio_lectivo)
            ) or str(hijo["version_id"])
        trabajo_id = await armar_canonico(
            motor_inteligencia,
            catalogo,
            f.colegio_id,
            f.grado,
            int(f.anio_lectivo),
            str(version),
            regenera=True,
        )
        async with motor_inteligencia.engine.begin() as conexion:
            estado = await conexion.scalar(
                select(trabajos.TRABAJO.c.estado).where(trabajos.TRABAJO.c.id == trabajo_id)
            )
        if estado != "publicado":
            fallidos.append(f"{nombre}: {estado}")
            continue
        rearmados += 1
        print(f"[canonicos] rearmado {nombre}")
    for fallo in fallidos:
        print(f"[canonicos] NO se rearmo {fallo}")
    return rearmados, saltados


def _motor_lectura(servicio: str) -> AsyncEngine:
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez(
    *,
    motor_inteligencia: MotorServicio | None = None,
    motor_catalogo: AsyncEngine | None = None,
    catalogo: Any = None,
) -> int:
    propio_inteligencia = motor_inteligencia is None
    propio_catalogo = motor_catalogo is None
    motor_inteligencia = motor_inteligencia or crear_motor("inteligencia")
    motor_catalogo = motor_catalogo or _motor_lectura("catalogo")
    try:
        poller = Poller(
            motor_inteligencia=motor_inteligencia,
            motor_catalogo=motor_catalogo,
            catalogo=catalogo or ClienteCatalogo(),
        )
        return await poller.pasada()
    finally:
        if propio_catalogo:
            await motor_catalogo.dispose()
        if propio_inteligencia:
            await motor_inteligencia.cerrar()


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    motor_inteligencia = crear_motor("inteligencia")
    poller = Poller(motor_inteligencia=motor_inteligencia, motor_catalogo=None, catalogo=ClienteCatalogo())
    try:
        return await consumir(
            url,
            Consumidor(
                cola=LISTAS, manejar=poller.manejar, registro=RegistroEnTabla(motor_inteligencia.engine)
            ),
            seguir=seguir,
            proceso="inteligencia-poller",
            intervalo=intervalo,
        )
    finally:
        await motor_inteligencia.cerrar()


async def _regenerar() -> tuple[int, list[str]]:
    motor_inteligencia = crear_motor("inteligencia")
    try:
        return await regenerar_canonicos(motor_inteligencia, ClienteCatalogo())
    finally:
        await motor_inteligencia.cerrar()


async def correr_en_bucle(
    intervalo: float, *, dormir: Callable[[float], Awaitable[None]] | None = None, **dependencias: Any
) -> None:

    async def _vuelta() -> None:
        arrancados = await correr_una_vez(**dependencias)
        if arrancados:
            print(f"[poller] kits de ruta rapida arrancados: {arrancados}")

    await bucle_resiliente(
        _vuelta, intervalo=intervalo, proceso="inteligencia-poller", dormir=dormir or asyncio.sleep
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena `lista_verificada` del Catalogo y arma el kit del padre que esperaba."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    analizador.add_argument(
        "--regenerar-canonicos",
        action="store_true",
        help="Rearma los kits canonicos automaticos con la logica actual (salta los editados a mano).",
    )
    argumentos = analizador.parse_args(argv)
    configurar_registro("inteligencia-poller")

    if argumentos.regenerar_canonicos:
        rearmados, saltados = asyncio.run(_regenerar())
        print(f"[canonicos] rearmados: {rearmados}")
        for nombre in saltados:
            print(f"[canonicos] saltado (puede tener lineas elegidas a mano): {nombre}")
        return 0

    url = url_broker()
    if url:
        procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
        if not argumentos.seguir:
            print(f"[poller] mensajes de {LISTAS.nombre}: {procesados}")
        return 0
    if argumentos.seguir:
        asyncio.run(correr_en_bucle(argumentos.intervalo))
    else:
        arrancados = asyncio.run(correr_una_vez())
        print(f"[poller] kits de ruta rapida arrancados: {arrancados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
