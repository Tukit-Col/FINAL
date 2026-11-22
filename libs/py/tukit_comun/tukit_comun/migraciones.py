from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from alembic import context
from sqlalchemy.orm import DeclarativeBase

from .bd import EXTENSIONES, crear_motor

_INDICES = Path(__file__).resolve().parents[4] / "infra" / "postgres" / "indices"
_NOMBRE_INDICE = re.compile(r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE)


def indices_de_infraestructura(servicio: str) -> frozenset[str]:
    archivo = _INDICES / f"{servicio}.sql"
    if not archivo.is_file():
        return frozenset()
    return frozenset(_NOMBRE_INDICE.findall(archivo.read_text(encoding="utf-8")))


def _filtro(ajenos: frozenset[str]) -> Any:
    def incluir(objeto: Any, nombre: str | None, tipo: str, reflejado: bool, _comparar: Any) -> bool:
        return not (tipo == "index" and reflejado and nombre in ajenos)

    return incluir


def _configurar(conexion: Any, metadata: Any, servicio: str) -> None:
    context.configure(
        connection=conexion,
        target_metadata=metadata,
        include_object=_filtro(indices_de_infraestructura(servicio)),
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,
    )


def _sincrono(conexion: Any, metadata: Any, servicio: str) -> None:
    _configurar(conexion, metadata, servicio)
    with context.begin_transaction():
        context.run_migrations()


async def _asincrono(servicio: str, metadata: Any) -> None:
    motor = crear_motor(servicio)
    try:
        async with motor.engine.begin() as conexion:
            await motor.asegurar_extensiones()
            await conexion.run_sync(_sincrono, metadata, servicio)
    finally:
        await motor.cerrar()


def correr(servicio: str, base: type[DeclarativeBase]) -> None:
    metadata = base.metadata

    if context.is_offline_mode():
        from .config import url_desde_entorno

        context.configure(
            url=url_desde_entorno(servicio),
            target_metadata=metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
            include_object=_filtro(indices_de_infraestructura(servicio)),
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    asyncio.run(_asincrono(servicio, metadata))


__all__ = ["EXTENSIONES", "correr", "indices_de_infraestructura"]
