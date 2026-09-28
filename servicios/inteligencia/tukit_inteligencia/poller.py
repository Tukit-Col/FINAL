"""El poller de `lista_verificada`: arma el kit del padre que estaba esperando.

Cuando un administrador aprueba una version que un acudiente habia subido, el
Catalogo NO llama a Inteligencia —esa arista cerraria un ciclo en el grafo de
dependencias (inteligencia->catalogo, nunca al reves)—: escribe un evento
`lista_verificada` en su bandeja de salida. Este proceso lo drena y hace lo que
el Catalogo no puede: crea un trabajo de RUTA RAPIDA para ese padre, con las
preferencias que dejo en el paso 3, y lo procesa. Al terminar, el pipeline deja
`kits_publicados` en la bandeja de Inteligencia y el repartidor de Operacion le
envia el correo con el enlace de pre-compra.

    python -m tukit_inteligencia.poller          # una pasada
    python -m tukit_inteligencia.poller --seguir  # bucle

**La unica excepcion a la frontera de bases**, igual que el repartidor: se abre
un motor de LECTURA/marcado a la base del Catalogo para drenar su bandeja. El
nombre de esa base NO se escribe aqui: `url_desde_entorno` lo deriva DENTRO de
la libreria a partir del nombre del servicio (regla 3). El trabajo se crea en la
base propia de Inteligencia con `trabajos.crear`, que es lo unico que este
servicio escribe.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import MetaData, String, Table, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bd import crear_motor
from tukit_comun.config import url_desde_entorno

from . import trabajos
from .modelos import Texto
from .remoto import ClienteCatalogo

# El unico tipo de evento que este poller atiende. La bandeja del Catalogo
# lleva otros (ninguno hoy), y un tipo desconocido se marca publicado sin
# actuar, para no reprocesarlo en cada pasada.
_TIPO = "lista_verificada"


def _bandeja_reflejada() -> Table:
    """La bandeja del Catalogo, descrita con solo las columnas que se leen.

    No se importa el modelo del Catalogo (regla 1): se declara aqui una tabla
    con la forma comun de bandeja, identica en todos los servicios. `carga` usa
    el mismo tipo portable que los modelos (JSON en SQLite, JSONB en Postgres).
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


@dataclass
class Poller:
    """Drena la bandeja del Catalogo y crea el kit de ruta rapida del padre.

    Los motores y el catalogo se inyectan para poder probar sin Postgres ni
    red; en produccion salen del entorno. `motor_inteligencia` es la base
    propia (donde se crea el trabajo); `motor_catalogo` es la ajena (de donde
    se drena la bandeja, la excepcion outbox declarada).
    """

    motor_inteligencia: Any
    motor_catalogo: AsyncEngine
    catalogo: ClienteCatalogo

    async def pasada(self, *, limite: int = 100) -> int:
        """Una pasada: procesa hasta `limite` eventos no publicados. Devuelve
        cuantos kits arranco con exito."""
        bandeja = _bandeja_reflejada()
        arrancados = 0
        async with self.motor_catalogo.begin() as conexion:
            pendientes = list(
                await conexion.execute(
                    select(bandeja)
                    .where(bandeja.c.publicado_en.is_(None), bandeja.c.tipo == _TIPO)
                    .order_by(bandeja.c.id)
                    .limit(limite)
                    .with_for_update(skip_locked=True)
                )
            )
            for fila in pendientes:
                ok = await self._procesar(conexion, bandeja, fila)
                if ok:
                    arrancados += 1
        return arrancados

    async def _procesar(self, conexion: Any, bandeja: Table, fila: Any) -> bool:
        carga = fila.carga or {}
        colegio_id = carga.get("colegio_id")
        grado = carga.get("grado")
        contacto = carga.get("contacto_referencia")
        # Un evento sin destino o sin padre no puede armar un kit dirigido: se
        # marca publicado para no reintentarlo en vano (no es un fallo del
        # poller, es un evento que no le sirve a nadie).
        if not colegio_id or not grado or not contacto:
            await self._marcar_publicado(conexion, bandeja, fila.id)
            return False

        try:
            usuario_id = uuid.UUID(str(contacto))
        except (ValueError, TypeError):
            await self._marcar_publicado(conexion, bandeja, fila.id)
            return False

        anio = carga.get("anio_lectivo")
        hijo: dict[str, Any] = {"referencia": "hijo-1", "colegio_id": str(colegio_id), "grado": grado}
        if anio is not None:
            hijo["anio_lectivo"] = anio
        # El `version_id` (el agregado del evento) queda en el trabajo para poder
        # volver de una lista subida al trabajo que engendro: es lo que deja
        # "Mis solicitudes" unir la lista aprobada con su trabajo en una sola
        # fila, en vez de mostrar dos. La carga no lo trae; el agregado si.
        hijo["version_id"] = str(fila.agregado_id)

        # El trabajo se crea para el padre YA identificado —su `usuario_id`
        # vive en la tarea desde que subio la lista—, sin volver a llamar a
        # Identidad. Las preferencias son las del paso 3 que el Catalogo
        # guardo y reenvio en la carga del evento.
        respuesta = await trabajos.crear(
            self.motor_inteligencia,
            hijos=[hijo],
            preferencias=carga.get("preferencias") or {},
            origen="lista_verificada",
            usuario_id=usuario_id,
        )
        trabajo_id = uuid.UUID(respuesta["trabajo_id"])

        # Se marca el evento publicado ANTES de procesar: el trabajo ya es
        # durable en `encolado`. Si el proceso muere durante el pipeline, el
        # trabajo queda reintentable (`POST /v1/trabajos/{id}/reintentar`) y el
        # evento no se reprocesa —no se arma un segundo kit para el mismo padre—.
        await self._marcar_publicado(conexion, bandeja, fila.id)

        # La lista esta revisada: `procesar` toma la ruta rapida (sin Gemini) y
        # al terminar deja `kits_publicados` en la bandeja propia, que el
        # repartidor recogera para avisarle al padre con el enlace.
        await trabajos.procesar(self.motor_inteligencia, trabajo_id, catalogo=self.catalogo)
        return True

    async def _marcar_publicado(self, conexion: Any, bandeja: Table, id_fila: int) -> None:
        await conexion.execute(
            update(bandeja).where(bandeja.c.id == id_fila).values(publicado_en=datetime.now(UTC))
        )


def _motor_lectura(servicio: str) -> AsyncEngine:
    """Motor a la base de un servicio ajeno (aqui, el Catalogo).

    El nombre de la base lo deriva `url_desde_entorno` DENTRO de la libreria a
    partir del nombre del servicio; este archivo nunca escribe el nombre de la
    base ajena, que es lo que mantiene verde la regla 3.
    """
    return create_async_engine(url_desde_entorno(servicio), pool_pre_ping=True)


async def correr_una_vez() -> int:
    """Una pasada sobre la bandeja del Catalogo. Para el cron o el arranque."""
    motor_inteligencia = crear_motor("inteligencia")
    motor_catalogo = _motor_lectura("catalogo")
    catalogo = ClienteCatalogo()
    try:
        poller = Poller(
            motor_inteligencia=motor_inteligencia,
            motor_catalogo=motor_catalogo,
            catalogo=catalogo,
        )
        return await poller.pasada()
    finally:
        await motor_catalogo.dispose()
        await motor_inteligencia.cerrar()


async def _bucle(intervalo: float) -> None:
    while True:
        arrancados = await correr_una_vez()
        if arrancados:
            print(f"[poller] kits de ruta rapida arrancados: {arrancados}")
        await asyncio.sleep(intervalo)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena `lista_verificada` del Catalogo y arma el kit del padre que esperaba."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        arrancados = asyncio.run(correr_una_vez())
        print(f"[poller] kits de ruta rapida arrancados: {arrancados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
