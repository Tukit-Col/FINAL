"""El contrato de la supresion del titular entre servicios (Ley 1581, ADR 0048).

Identidad anonimiza su parte y escribe `titular_suprimido` en su bandeja. Cada
servicio que guarda datos del titular (Comercio, Operacion, Inteligencia) lo
consume de su cola, borra o enmascara lo suyo y, EN LA MISMA transaccion,
escribe `supresion_confirmada` en su propia bandeja. Identidad consume esas
confirmaciones y cierra la solicitud solo cuando estan las tres.

Aqui vive lo que los cuatro tienen que decir igual: los tipos, la marca con que
se reemplaza un texto libre, quienes tienen que confirmar y como se lee y se
arma la carga. Ningun servicio importa a otro; todos importan esto.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Table, func, insert, select

from .bandeja import con_correlacion

TITULAR_SUPRIMIDO = "titular_suprimido"
SUPRESION_CONFIRMADA = "supresion_confirmada"

# Lo que queda en un campo de texto libre o de contacto que no puede ser nulo.
MARCA_SUPRIMIDO = "[suprimido por solicitud del titular]"

# Los servicios sin cuya confirmacion la solicitud no esta `completada`.
SUSCRIPTORES_SUPRESION: frozenset[str] = frozenset({"comercio", "operacion", "inteligencia"})


@dataclass(frozen=True)
class Supresion:
    """De quien son los datos y que solicitud se esta atendiendo."""

    usuario_id: uuid.UUID
    solicitud_id: uuid.UUID


def supresion_de(carga: dict[str, Any] | None) -> Supresion | None:
    """La supresion que trae la carga, o `None` si le falta algo o no es un id.

    Un evento asi no le sirve a nadie: reintentarlo no lo arregla."""
    carga = carga or {}
    try:
        return Supresion(
            usuario_id=uuid.UUID(str(carga["usuario_id"])),
            solicitud_id=uuid.UUID(str(carga["solicitud_id"])),
        )
    except (KeyError, TypeError, ValueError):
        return None


def confirmacion(supresion: Supresion, servicio: str) -> dict[str, Any]:
    """Los valores de la fila `supresion_confirmada` para la bandeja de `servicio`.

    Solo identificadores seudonimos: la confirmacion no repite ningun dato."""
    return {
        "tipo": SUPRESION_CONFIRMADA,
        "agregado_tipo": "solicitud_supresion",
        "agregado_id": supresion.solicitud_id,
        "carga": con_correlacion(
            {
                "solicitud_id": str(supresion.solicitud_id),
                "usuario_id": str(supresion.usuario_id),
                "servicio": servicio,
            }
        ),
    }


async def anotar_confirmacion(conexion: Any, bandeja: Table, supresion: Supresion, servicio: str) -> bool:
    """Escribe `supresion_confirmada` en la `bandeja` propia, si no estaba ya.

    Va en la misma transaccion que el borrado: o quedan los dos o ninguno. Un
    `titular_suprimido` repetido no deja una segunda confirmacion (Identidad las
    toleraria igual, pero la bandeja no se llena de copias). Devuelve si escribio."""
    ya = await conexion.scalar(
        select(func.count())
        .select_from(bandeja)
        .where(bandeja.c.tipo == SUPRESION_CONFIRMADA, bandeja.c.agregado_id == supresion.solicitud_id)
    )
    if ya:
        return False
    await conexion.execute(insert(bandeja).values(**confirmacion(supresion, servicio)))
    return True


__all__ = [
    "MARCA_SUPRIMIDO",
    "SUPRESION_CONFIRMADA",
    "SUSCRIPTORES_SUPRESION",
    "TITULAR_SUPRIMIDO",
    "Supresion",
    "anotar_confirmacion",
    "confirmacion",
    "supresion_de",
]
