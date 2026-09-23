"""Entorno de Alembic compartido por los servicios.

Cada servicio tiene su PROPIA historia de migraciones, porque cada uno tiene su
propia base y se despliega solo. Lo que se comparte es el arranque, no las
revisiones: sin esto, el `env.py` de los cinco servicios seria el mismo archivo
copiado cinco veces, y la copia numero tres se quedaria atras el dia que
cambie la forma de leer la URL. Es la misma razon por la que el nombre de la
base se deriva en `tukit_comun.config` y no se escribe en cada servicio.

El `env.py` de un servicio queda en tres lineas:

    from tukit_comun.migraciones import correr
    from tukit_catalogo.modelos import Base
    correr("catalogo", Base)

Migraciones y provision son cosas distintas y conviven a proposito.
`tukit_comun.esquema.materializar` crea el esquema de cero con `create_all` y
sirve para levantar un entorno de desarrollo en un comando; Alembic versiona el
cambio incremental, que es lo unico que sirve cuando la base ya tiene datos que
no se pueden perder. La prueba de que no se han separado esta en
`test_migraciones.py`: compara el esquema que dejan las migraciones contra el
que declaran los modelos y falla si divergen.
"""

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
    """Los indices que aplica `infra/postgres/indices`, no los modelos.

    Un indice HNSW o GIN no se puede declarar en SQLAlchemy sin ataduras al
    dialecto, asi que vive en SQL aparte. Alembic entonces lo ve en la base,
    no lo encuentra en el metadata y propone borrarlo en cada autogenerate.
    Aceptar esa propuesta deja la busqueda hibrida recorriendo la tabla
    entera, y ninguna prueba se queja porque el resultado es el mismo: solo
    tarda.

    Los nombres se leen del SQL en vez de listarse aqui para que las dos
    fuentes concuerden por construccion. Una lista a mano se desactualiza el
    dia que se agregue un indice, y el modo de fallar seria este mismo otra
    vez. Y a diferencia de una convencion por sufijo, esto no silencia un
    indice que un modelo declare y que de casualidad se llame parecido.
    """
    archivo = _INDICES / f"{servicio}.sql"
    if not archivo.is_file():
        return frozenset()
    return frozenset(_NOMBRE_INDICE.findall(archivo.read_text(encoding="utf-8")))


def _filtro(ajenos: frozenset[str]) -> Any:
    def incluir(objeto: Any, nombre: str | None, tipo: str, reflejado: bool, _comparar: Any) -> bool:
        # Solo se excluye lo REFLEJADO: si mañana alguien declara uno de estos
        # indices en un modelo, la diferencia vuelve a aparecer en vez de
        # quedar escondida para siempre.
        return not (tipo == "index" and reflejado and nombre in ajenos)

    return incluir


def _configurar(conexion: Any, metadata: Any, servicio: str) -> None:
    context.configure(
        connection=conexion,
        target_metadata=metadata,
        include_object=_filtro(indices_de_infraestructura(servicio)),
        # Sin esto, cambiar `String(64)` a `String(128)` no genera migracion:
        # Alembic compara nombres de columna y no sus tipos. El resultado es
        # un modelo que promete un limite y una base que impone otro.
        compare_type=True,
        # Lo mismo con los valores por omision que vienen del servidor.
        compare_server_default=True,
        # Las restricciones sin nombre son el motivo clasico de que una
        # migracion no se pueda revertir: no hay forma de referirse a algo que
        # no se llama de ninguna manera. La convencion las nombra a todas.
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
            # Las extensiones van ANTES de la primera migracion y no dentro de
            # ella. La primera revision crea columnas `vector`, y un tipo no se
            # puede usar en el mismo paso en que se instala el tipo.
            await motor.asegurar_extensiones()
            await conexion.run_sync(_sincrono, metadata, servicio)
    finally:
        await motor.cerrar()


def correr(servicio: str, base: type[DeclarativeBase]) -> None:
    """Punto de entrada del `env.py` de un servicio.

    En modo fuera de linea genera el SQL sin conectarse, que es como se revisa
    una migracion antes de dejarla tocar una base de produccion.
    """
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
