"""El poller de `colegio_verificado`: un colegio nuevo se vuelve aliado.

Cuando un administrador aprueba la lista que un acudiente subio para un colegio
que AUN NO existia en Tukit —lo eligio del directorio de Bogota o lo escribio a
mano—, el Catalogo NO llama a Identidad: esa arista no existe en el grafo de
dependencias (todo apunta a Identidad, nunca al reves). El Catalogo escribe un
evento `colegio_verificado` en su bandeja de salida, con el `colegio_id` que ya
derivo de forma estable (del DANE o del nombre normalizado) y los datos que el
revisor completo. Este proceso lo drena y hace lo que el Catalogo no puede:
da de alta el colegio en Identidad con ESE MISMO identificador, de modo que la
lista verificada del Catalogo y el colegio de Identidad quedan ligados sin una
llave foranea entre bases.

    python -m tukit_identidad.poller           # una pasada
    python -m tukit_identidad.poller --seguir   # bucle

**La unica excepcion a la frontera de bases**, igual que el repartidor y el
poller de Inteligencia: se abre un motor de LECTURA/marcado a la base del
Catalogo para drenar su bandeja. El nombre de esa base NO se escribe aqui:
`url_desde_entorno` lo deriva DENTRO de la libreria a partir del nombre del
servicio (regla 3). El colegio se da de alta en la base propia de Identidad,
que es lo unico que este servicio escribe.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.config import url_desde_entorno

from .modelos import Colegio, Sede

# El unico tipo de evento que este poller atiende. La bandeja del Catalogo
# lleva otros (`lista_verificada`, que drena Inteligencia); un tipo que no sea
# el suyo simplemente no se selecciona y lo atiende quien corresponda.
_TIPO = "colegio_verificado"

# El nombre de la sede unica que se crea con el colegio. Un colegio recien dado
# de alta desde una lista no declara sedes: se le crea una principal para que
# las matriculas futuras tengan donde colgar (Sede.colegio_id es obligatorio).
_SEDE_PRINCIPAL = "Sede principal"


def _bandeja_reflejada() -> Table:
    """La bandeja del Catalogo, descrita con solo las columnas que se leen.

    No se importa el modelo del Catalogo (regla 1): se declara aqui una tabla
    con la forma comun de bandeja, identica en todos los servicios. `carga` se
    lee como JSON portable; se declara con el tipo generico para no arrastrar el
    `Texto` de un servicio ajeno.
    """
    from sqlalchemy import JSON

    metadatos = MetaData()
    return Table(
        "bandeja_salida",
        metadatos,
        Column("id", BigInteger, primary_key=True),
        Column("tipo", String(128)),
        Column("agregado_tipo", String(64)),
        Column("agregado_id", Uuid(as_uuid=True)),
        Column("carga", JSON),
        Column("publicado_en", DateTime(timezone=True)),
        Column("intentos", Integer),
    )


@dataclass
class Poller:
    """Drena `colegio_verificado` del Catalogo y da de alta el colegio.

    Los motores se inyectan para poder probar sin Postgres; en produccion salen
    del entorno. `motor_identidad` es la base propia (donde se crea el colegio);
    `motor_catalogo` es la ajena (de donde se drena la bandeja, la excepcion
    outbox declarada).
    """

    motor_identidad: MotorServicio
    motor_catalogo: AsyncEngine

    async def pasada(self, *, limite: int = 100) -> int:
        """Una pasada: procesa hasta `limite` eventos no publicados. Devuelve
        cuantos colegios dio de alta o actualizo."""
        bandeja = _bandeja_reflejada()
        aplicados = 0
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
                ok = await self._procesar(fila)
                # El evento se marca publicado pase lo que pase con el upsert:
                # un evento sin `colegio_id` valido no le sirve a nadie y no debe
                # reintentarse en cada pasada. Un upsert que sale bien tampoco.
                await self._marcar_publicado(conexion, bandeja, fila.id)
                if ok:
                    aplicados += 1
        return aplicados

    async def _procesar(self, fila: Any) -> bool:
        """Da de alta (o actualiza) el colegio del evento. Devuelve si aplico."""
        carga = fila.carga or {}
        crudo = carga.get("colegio_id")
        if not crudo:
            return False
        try:
            colegio_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return False
        nombre = (carga.get("nombre") or "").strip()
        if not nombre:
            # Un colegio sin nombre no se puede mostrar en la tarjeta de aliado:
            # el nombre es el unico campo obligatorio del modelo. Sin el, no se
            # da de alta (pero el evento se marca publicado igual, arriba).
            return False

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
                # Un colegio ya dado de alta (otra lista del mismo, o una nueva
                # version) NO se pisa: solo se completan los campos que llegaron
                # y aun estaban vacios. Asi el trabajo del revisor no se borra si
                # una segunda lista del mismo colegio trae menos datos.
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
    motor_identidad = crear_motor("identidad")
    motor_catalogo = _motor_lectura("catalogo")
    try:
        poller = Poller(motor_identidad=motor_identidad, motor_catalogo=motor_catalogo)
        return await poller.pasada()
    finally:
        await motor_catalogo.dispose()
        await motor_identidad.cerrar()


async def _bucle(intervalo: float) -> None:
    while True:
        aplicados = await correr_una_vez()
        if aplicados:
            print(f"[poller-identidad] colegios dados de alta/actualizados: {aplicados}")
        await asyncio.sleep(intervalo)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Drena `colegio_verificado` del Catalogo y da de alta el colegio en Identidad."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        aplicados = asyncio.run(correr_una_vez())
        print(f"[poller-identidad] colegios dados de alta/actualizados: {aplicados}")
    return 0


__all__ = ["Poller", "correr_una_vez", "main"]
