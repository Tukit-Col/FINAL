from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, insert, select
from tukit_comun.cifrado import cifrador_desde_entorno

from .modelos import Base

APODO = Base.metadata.tables["apodo_subida"]


def _filas(version_id: str, contacto: str | None, apodos: dict[str, str]) -> list[dict[str, Any]]:
    cifrador = cifrador_desde_entorno()
    return [
        {
            "version_id": str(version_id),
            "referencia": referencia,
            "contacto_referencia": contacto,
            "apodo_cifrado": cifrador.cifrar(apodo.encode("utf-8")),
        }
        for referencia, apodo in apodos.items()
        if apodo and apodo.strip()
    ]


async def guardar(motor: Any, version_id: str, contacto: str | None, apodos: dict[str, str]) -> None:
    filas = _filas(version_id, contacto, apodos)
    if not filas:
        return
    async with motor.engine.begin() as conexion:
        await guardar_en(conexion, filas)


async def guardar_en(conexion: Any, filas: list[dict[str, Any]]) -> None:
    import uuid

    await conexion.execute(insert(APODO), [{"id": uuid.uuid4(), **f} for f in filas])


def _descifrar(filas: Any) -> dict[str, str]:
    cifrador = cifrador_desde_entorno()
    salida: dict[str, str] = {}
    for f in filas:
        try:
            salida[f.referencia] = cifrador.descifrar(f.apodo_cifrado).decode("utf-8", errors="replace")
        except Exception:
            continue
    return salida


async def apodos_de(motor: Any, version_id: str) -> dict[str, str]:
    async with motor.engine.connect() as conexion:
        filas = await conexion.execute(select(APODO).where(APODO.c.version_id == str(version_id)))
        return _descifrar(filas)


async def tomar(conexion: Any, version_id: str) -> dict[str, str]:
    filas = list(await conexion.execute(select(APODO).where(APODO.c.version_id == str(version_id))))
    if filas:
        await conexion.execute(delete(APODO).where(APODO.c.version_id == str(version_id)))
    return _descifrar(filas)


async def cuantos_de(motor: Any, contacto: str) -> int:
    async with motor.engine.connect() as conexion:
        return int(
            await conexion.scalar(
                select(func.count()).select_from(APODO).where(APODO.c.contacto_referencia == str(contacto))
            )
            or 0
        )
