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
from dataclasses import dataclass, field
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
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.config import url_desde_entorno

# Import intra-servicio: `_materializar_hijos` es la funcion del registro, que su
# propio docstring reserva "y a futuro el poller". Reusarla evita duplicar la
# derivacion idempotente de estudiante + matricula + vinculo. `api.py` no importa
# a `poller.py`, asi que no hay ciclo, y ambos viven en el mismo servicio (la
# frontera solo prohibe importar OTRO servicio).
from .api import GRADOS, HijoRegistro, _materializar_hijos
from .modelos import Colegio, Sede, Usuario

# El unico tipo de evento que este poller atiende. La bandeja del Catalogo
# lleva otros (`lista_verificada`, que drena Inteligencia); un tipo que no sea
# el suyo simplemente no se selecciona y lo atiende quien corresponda.
_TIPO = "colegio_verificado"

# El nombre de la sede unica que se crea con el colegio. Un colegio recien dado
# de alta desde una lista no declara sedes: se le crea una principal para que
# las matriculas futuras tengan donde colgar (Sede.colegio_id es obligatorio).
_SEDE_PRINCIPAL = "Sede principal"


def _dane_de_carga(carga: dict[str, Any]) -> str | None:
    """El codigo DANE que trae el evento, o `None`.

    HALLAZGO para MapaRuiz: el evento `colegio_verificado` NO trae una clave
    `dane`; el emisor de Catalogo pliega el DANE dentro de `nit`
    (`"nit": datos.get("dane") or datos.get("nit")`). Lo ideal seria que emitiera
    un `dane` aparte. Mientras tanto, y sin tocar el emisor, se rescata de `nit`
    SOLO cuando tiene la forma del DANE del DUEB (12 digitos exactos): asi un NIT
    tributario que no es DANE no ensucia la columna nueva. `nit` se sigue
    guardando igual que hoy, reciba o no el DANE."""
    valor = carga.get("dane") or carga.get("nit")
    if isinstance(valor, str) and valor.isdigit() and len(valor) == 12:
        return valor
    return None


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
    # Se resuelve una vez, igual que cada peticion de la API. `cifrador_desde_entorno`
    # nunca levanta (cae a claro), asi que el default es seguro y las pruebas
    # pueden construir el Poller sin pasarlo.
    cifrador: Any = field(default_factory=cifrador_desde_entorno)

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
                # El `dane` no viaja como clave propia (se rescata de `nit`), asi
                # que va aparte del bucle, con la misma regla de solo-si-vacio.
                dane = _dane_de_carga(carga)
                if dane and existente.dane is None:
                    existente.dane = dane

        # El colegio y su "Sede principal" ya quedaron confirmados. Si un padre
        # subio la lista para este colegio y existe en Identidad, se matricula a
        # su hijo; si no, el colegio queda igual.
        await self._matricular_al_hijo_que_esperaba(carga, colegio_id)
        return True

    async def _matricular_al_hijo_que_esperaba(
        self, carga: dict[str, Any], colegio_id: uuid.UUID
    ) -> None:
        """Reusa `_materializar_hijos` (el camino del registro) para que el hijo
        del padre que subio la lista quede matriculado al volverse aliado el
        colegio. Sin esto, el hijo nunca aparece en precarga ni en el padron.

        - `contacto_referencia` es el usuario_id OPACO del padre (nunca su correo);
          solo se matricula si ese usuario YA existe: no se crea cuenta desde aqui.
        - El apodo queda vacio (cadena vacia cifrada): el dato del menor no viaja
          por Catalogo ni Inteligencia.
        - El año es el actual, igual que el registro y `/v1/cuenta/matriculas`, para
          que el id derivado coincida con el de un registro propio y no duplique.
        - Va en su PROPIA transaccion y es best-effort: el colegio ya quedo dado de
          alta; un fallo aqui no debe reprocesar el lote entero (el evento se marca
          publicado igual) y el padre podra inscribirlo desde /empezar (idempotente).
        """
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
                existe = await conexion.scalar(
                    select(Usuario.id).where(Usuario.id == usuario_id)
                )
                if existe is None:
                    return
                hijo = HijoRegistro(colegio_id=colegio_id, grado=grado)  # apodo -> "" cifrado
                await _materializar_hijos(
                    conexion, usuario_id, [hijo], datetime.now(UTC).year, self.cifrador
                )
        except Exception as error:  # noqa: BLE001 - best-effort; el colegio ya quedo dado de alta
            print(f"[poller-identidad] no se pudo matricular al hijo de {colegio_id}: {error}")

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


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Poller", "correr_una_vez", "main"]
