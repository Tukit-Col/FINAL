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
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, drenar
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
        cuantos colegios dio de alta o actualizo.

        El drenar/SKIP LOCKED/marcar-publicado vive en `tukit_comun.bandeja`
        (ADR 0022); aqui solo se aporta el `manejar` de `colegio_verificado`."""
        return await drenar(self.motor_catalogo, self._procesar, tipo=_TIPO, limite=limite)

    async def _procesar(self, conexion: Any, fila: Any) -> Resultado:
        """Da de alta (o actualiza) el colegio del evento.

        `OMITIR` (marca publicado, no cuenta) para un evento que no le sirve a
        nadie —sin `colegio_id` valido o sin nombre—: reintentarlo cada pasada no
        cambiaria nada. `HECHO` cuando el colegio se dio de alta o actualizo."""
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
            # Un colegio sin nombre no se puede mostrar en la tarjeta de aliado:
            # el nombre es el unico campo obligatorio del modelo. Sin el, no se
            # da de alta (pero el evento se marca publicado igual: OMITIR).
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
        return Resultado.HECHO


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


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Poller", "correr_una_vez", "main"]
