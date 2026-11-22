"""Poller de `colegio_verificado`: un colegio nuevo se vuelve aliado.

Decisiones:
- Catalogo no llama a Identidad: escribe `colegio_verificado` en su bandeja con el `colegio_id`
  derivado de forma estable, y este proceso da de alta el colegio con ese mismo identificador.
- Con `RABBITMQ_URL` consume la cola `identidad.colegios` y no abre ningun motor a la base de
  Catalogo; sin ella sondea esa bandeja.
- Dar de alta es idempotente: crea si falta y completa solo lo vacio.

Uso:  python -m tukit_identidad.poller [--seguir]
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, drenar
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.broker import url_broker
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.config import url_desde_entorno
from tukit_comun.consumidor import Consumidor, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente
from tukit_comun.topologia import COLEGIOS

from .dominio.matriculas import GRADOS, HijoMatricula
from .modelos import Colegio, Sede, Usuario
from .repositorios import RepoIdentidad

_TIPO = "colegio_verificado"

_SEDE_PRINCIPAL = "Sede principal"


def _dane_de_carga(carga: dict[str, Any]) -> str | None:
    valor = carga.get("dane") or carga.get("nit")
    if isinstance(valor, str) and valor.isdigit() and len(valor) == 12:
        return valor
    return None


@dataclass
class Poller:

    motor_identidad: MotorServicio
    motor_catalogo: AsyncEngine | None
    cifrador: Any = field(default_factory=cifrador_desde_entorno)

    async def pasada(self, *, limite: int = 100) -> int:
        if self.motor_catalogo is None:
            raise ValueError("sin la bandeja del Catalogo no hay pasada: con RabbitMQ se usa `manejar`")
        return await drenar(self.motor_catalogo, self._procesar, tipo=_TIPO, limite=limite)

    async def manejar(self, evento: Evento) -> Resultado:
        if evento.tipo != _TIPO:
            return Resultado.OMITIR
        return await self._procesar(None, evento)

    async def _procesar(self, conexion: Any, fila: Any) -> Resultado:
        carga = fila.carga or {}
        crudo = carga.get("colegio_id")
        if not crudo:
            return Resultado.OMITIR
        try:
            colegio_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Resultado.OMITIR
        nombre = (carga.get("nombre") or "").strip()
        if not nombre:
            return Resultado.OMITIR

        async with self.motor_identidad.sesion() as db:
            existente = (
                await db.execute(select(Colegio).where(Colegio.id == colegio_id))
            ).scalar_one_or_none()
            if existente is None:
                db.add(
                    Colegio(
                        id=colegio_id,
                        nombre=nombre,
                        nit=carga.get("nit"),
                        dane=_dane_de_carga(carga),
                        logo_url=carga.get("logo_url"),
                        sitio_web=carga.get("sitio_web"),
                        contacto_nombre=carga.get("contacto_nombre"),
                        contacto_email=carga.get("contacto_email"),
                        contacto_telefono=carga.get("contacto_telefono"),
                        direccion=carga.get("direccion"),
                    )
                )
                await db.flush()
                db.add(Sede(colegio_id=colegio_id, nombre=_SEDE_PRINCIPAL))
            else:
                for campo in (
                    "nit",
                    "logo_url",
                    "sitio_web",
                    "contacto_nombre",
                    "contacto_email",
                    "contacto_telefono",
                    "direccion",
                ):
                    valor = carga.get(campo)
                    if valor and getattr(existente, campo) is None:
                        setattr(existente, campo, valor)
                dane = _dane_de_carga(carga)
                if dane and existente.dane is None:
                    existente.dane = dane

        await self._matricular_al_hijo_que_esperaba(carga, colegio_id)
        return Resultado.HECHO

    async def _matricular_al_hijo_que_esperaba(self, carga: dict[str, Any], colegio_id: uuid.UUID) -> None:
        referencia = carga.get("contacto_referencia")
        if not referencia:
            return
        try:
            usuario_id = uuid.UUID(str(referencia))
        except (ValueError, TypeError):
            return
        grado = (carga.get("grado") or "").strip()
        if grado not in GRADOS:
            return
        try:
            async with self.motor_identidad.engine.begin() as conexion:
                existe = await conexion.scalar(select(Usuario.id).where(Usuario.id == usuario_id))
                if existe is None:
                    return
                hijo = HijoMatricula(colegio_id=colegio_id, grado=grado)
                repo = RepoIdentidad(conexion)
                await repo.materializar_hijos(usuario_id, [hijo], datetime.now(UTC).year, self.cifrador)
        except Exception as error:  # noqa: BLE001 - best-effort; el colegio ya quedo dado de alta
            print(f"[poller-identidad] no se pudo matricular al hijo de {colegio_id}: {error}")


def _motor_lectura(servicio: str) -> AsyncEngine:
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez() -> int:
    motor_identidad = crear_motor("identidad")
    motor_catalogo = _motor_lectura("catalogo")
    try:
        poller = Poller(motor_identidad=motor_identidad, motor_catalogo=motor_catalogo)
        return await poller.pasada()
    finally:
        await motor_catalogo.dispose()
        await motor_identidad.cerrar()


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    motor_identidad = crear_motor("identidad")
    poller = Poller(motor_identidad=motor_identidad, motor_catalogo=None)
    try:
        return await consumir(
            url,
            Consumidor(cola=COLEGIOS, manejar=poller.manejar),
            seguir=seguir,
            proceso="identidad-poller",
            intervalo=intervalo,
        )
    finally:
        await motor_identidad.cerrar()


async def _bucle(intervalo: float, *, dormir: Callable[[float], Awaitable[None]] | None = None) -> None:
    async def _vuelta() -> None:
        aplicados = await correr_una_vez()
        if aplicados:
            print(f"[poller-identidad] colegios dados de alta/actualizados: {aplicados}")

    await bucle_resiliente(
        _vuelta, intervalo=intervalo, proceso="identidad-poller", dormir=dormir or asyncio.sleep
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena `colegio_verificado` del Catalogo y da de alta el colegio en Identidad."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("identidad-poller")

    url = url_broker()
    if url:
        procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
        if not argumentos.seguir:
            print(f"[poller-identidad] mensajes de {COLEGIOS.nombre}: {procesados}")
        return 0
    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        aplicados = asyncio.run(correr_una_vez())
        print(f"[poller-identidad] colegios dados de alta/actualizados: {aplicados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Poller", "correr_una_vez", "escuchar_cola", "main"]
