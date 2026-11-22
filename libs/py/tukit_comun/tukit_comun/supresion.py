from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Table, func, insert, select

from .bandeja import con_correlacion

TITULAR_SUPRIMIDO = "titular_suprimido"
SUPRESION_CONFIRMADA = "supresion_confirmada"

MARCA_SUPRIMIDO = "[suprimido por solicitud del titular]"

SUSCRIPTORES_SUPRESION: frozenset[str] = frozenset({"comercio", "operacion", "inteligencia"})


@dataclass(frozen=True)
class Supresion:

    usuario_id: uuid.UUID
    solicitud_id: uuid.UUID


def supresion_de(carga: dict[str, Any] | None) -> Supresion | None:
    carga = carga or {}
    try:
        return Supresion(
            usuario_id=uuid.UUID(str(carga["usuario_id"])),
            solicitud_id=uuid.UUID(str(carga["solicitud_id"])),
        )
    except (KeyError, TypeError, ValueError):
        return None


def confirmacion(supresion: Supresion, servicio: str) -> dict[str, Any]:
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
