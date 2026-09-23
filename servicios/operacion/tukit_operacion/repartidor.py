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

**La unica excepcion a la frontera de bases.** Un servicio no toca la base de
otro; el patron outbox es la excepcion declarada, y esta es la que la ejerce:
el repartidor abre motores de LECTURA a las bases de Inteligencia y Comercio. El
nombre de esas bases NO se escribe aqui: `url_desde_entorno` lo deriva en la
libreria a partir del nombre del servicio, asi que este archivo no contiene el
string de ninguna base ajena (regla 3 de las fronteras).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import MetaData, String, Table, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bd import crear_motor
from tukit_comun.config import url_desde_entorno

from .modelos import Base, Texto
from .notificador import Contacto, Notificador, notificador_desde_entorno
from .remoto import ClienteIdentidad

NOTIFICACION = Base.metadata.tables["notificacion"]

# Que plantilla y de donde sale el destinatario, por tipo de evento.
_TIPOS = {
    "kits_publicados": "kits_publicados",
    "pedido_pagado": "pedido_pagado",
    "incidencia": "incidencia",
}


def _bandeja_reflejada() -> Table:
    """La bandeja de otro servicio, descrita con solo las columnas que se leen.

    No se importa el modelo del otro servicio (regla 1: ningun servicio importa
    codigo de otro): se declara aqui una tabla con la forma comun de bandeja
    (`tipo, agregado_tipo, agregado_id, carga, publicado_en, intentos`), que es
    identica en Inteligencia y en Comercio a proposito. `carga` usa el mismo
    tipo portable que los modelos (JSON en SQLite, JSONB en Postgres).
    """
    from sqlalchemy import BigInteger, Column, DateTime, Integer, Uuid

    metadatos = MetaData()
    return Table(
        "bandeja_salida",
        metadatos,
        Column("id", BigInteger, primary_key=True),
        Column("tipo", String(128)),
        Column("agregado_tipo", String(64)),
        Column("agregado_id", Uuid(as_uuid=True)),
        Column("carga", Texto),
        Column("publicado_en", DateTime(timezone=True)),
        Column("intentos", Integer),
    )


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

    async def pasada(self, *, limite: int = 100) -> int:
        """Una pasada: procesa hasta `limite` eventos no publicados. Devuelve
        cuantos entrego con exito."""
        bandeja = _bandeja_reflejada()
        entregados = 0
        async with self.motor_origen.begin() as conexion_origen:
            pendientes = list(
                await conexion_origen.execute(
                    select(bandeja)
                    .where(bandeja.c.publicado_en.is_(None))
                    .order_by(bandeja.c.id)
                    .limit(limite)
                    .with_for_update(skip_locked=True)
                )
            )
            for fila in pendientes:
                ok = await self._entregar(conexion_origen, bandeja, fila)
                if ok:
                    entregados += 1
        return entregados

    async def _entregar(self, conexion_origen: Any, bandeja: Table, fila: Any) -> bool:
        plantilla = _TIPOS.get(fila.tipo)
        if plantilla is None:
            # Un tipo que este repartidor no maneja: se marca publicado para no
            # reprocesarlo en cada pasada. No es un fallo, es "no me toca".
            await self._marcar_publicado(conexion_origen, bandeja, fila.id)
            return False

        usuario_id = await self._destinatario(fila)
        if usuario_id is None:
            await self._subir_intentos(conexion_origen, bandeja, fila.id)
            return False

        datos = self._datos_plantilla(fila)
        # Se crea la notificacion POR ID, sin contacto, y se envia resolviendo
        # el contacto al vuelo. Si el envio falla, se sube intentos y se
        # reintenta en la proxima pasada; la notificacion queda como fallida.
        contacto = await self._resolver_contacto(usuario_id)
        envio = await self.notificador.enviar(contacto, plantilla, datos)

        await self._registrar_notificacion(usuario_id, envio.canal, plantilla, datos, envio.exito)
        if envio.exito:
            await self._marcar_publicado(conexion_origen, bandeja, fila.id)
            return True
        await self._subir_intentos(conexion_origen, bandeja, fila.id)
        return False

    async def _destinatario(self, fila: Any) -> str | None:
        carga = fila.carga or {}
        # `pedido_pagado` trae el usuario en la carga (lo puso Comercio).
        if fila.tipo in {"pedido_pagado", "incidencia"} and carga.get("usuario_id"):
            return str(carga["usuario_id"])
        # `kits_publicados` no lo trae: se lee de trabajo_pipeline por su id.
        if fila.tipo == "kits_publicados":
            return await self._usuario_del_trabajo(fila.agregado_id)
        return None

    async def _usuario_del_trabajo(self, trabajo_id: uuid.UUID) -> str | None:
        trabajo = _trabajo_reflejado()
        async with self.motor_origen.connect() as conexion:
            usuario = await conexion.scalar(select(trabajo.c.usuario_id).where(trabajo.c.id == trabajo_id))
        return str(usuario) if usuario is not None else None

    def _datos_plantilla(self, fila: Any) -> dict[str, object]:
        carga = fila.carga or {}
        # El turno es un identificador corto y estable del evento; nunca el
        # contacto. Sale del id del agregado.
        turno = str(fila.agregado_id)[:8].upper()
        datos: dict[str, object] = {"turno": turno}
        if carga.get("pedido_id"):
            datos["pedido"] = str(carga["pedido_id"])[:8].upper()
        return datos

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
        self, usuario_id: str, canal: str, plantilla: str, datos: dict[str, object], exito: bool
    ) -> None:
        ahora = datetime.now(UTC)
        async with self.motor_operacion.sesion() as db:
            conexion = await db.connection()
            await conexion.execute(
                insert(NOTIFICACION).values(
                    id=uuid.uuid4(),
                    usuario_id=uuid.UUID(usuario_id),
                    canal=canal,
                    plantilla=plantilla,
                    datos=datos,  # variables de negocio, sin contacto
                    estado="enviada" if exito else "fallida",
                    creado_en=ahora,
                    enviada_en=ahora if exito else None,
                )
            )

    async def _marcar_publicado(self, conexion: Any, bandeja: Table, id_fila: int) -> None:
        await conexion.execute(
            update(bandeja).where(bandeja.c.id == id_fila).values(publicado_en=datetime.now(UTC))
        )

    async def _subir_intentos(self, conexion: Any, bandeja: Table, id_fila: int) -> None:
        await conexion.execute(
            update(bandeja).where(bandeja.c.id == id_fila).values(intentos=bandeja.c.intentos + 1)
        )


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
                )
                resultado[origen] = await repartidor.pasada()
            finally:
                await motor_origen.dispose()
    finally:
        await motor_operacion.cerrar()
    return resultado


async def _bucle(intervalo: float) -> None:
    while True:
        entregas = await correr_una_vez()
        total = sum(entregas.values())
        if total:
            print(f"[repartidor] entregados: {entregas}")
        await asyncio.sleep(intervalo)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Reparte los eventos de las bandejas de salida.")
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        entregas = asyncio.run(correr_una_vez())
        print(f"[repartidor] entregados: {entregas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
