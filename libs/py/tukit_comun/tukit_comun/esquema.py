"""Provision de esquema: materializa las tablas de un servicio en su base real.

Es la contraparte de runtime del `Base.metadata.create_all` que los conftest ya
usan contra SQLite. Aqui corre contra la base Postgres del servicio, leida del
entorno. Cada servicio expone un `__main__` de una linea que llama a
`materializar` con SU `Base`; la libreria no conoce los modelos de nadie.

    # servicios/identidad/tukit_identidad/__main__.py
    from tukit_comun.esquema import materializar
    from tukit_identidad.modelos import Base
    materializar("identidad", Base)

    $ python -m tukit_identidad        # crea el esquema de identidad

Provision, no migracion. Crea lo que falta; no versiona cambios incrementales
ni migra datos. El versionado del esquema (Alembic) es un paso posterior,
anotado como deuda en el README. Para el arranque de desarrollo y la primera
carga, create_all es suficiente y es exactamente lo que las pruebas ya validan.

Antes de las tablas habilita las extensiones de Postgres que falten (ver
`MotorServicio.asegurar_extensiones`). Es la red que cubre a quien ya tenia el
volumen de datos creado cuando la lista de extensiones cambio: el script de init
de `infra/` no vuelve a correr para el, pero esto si.

Lo que NO hace es crear los indices propios de Postgres (HNSW sobre el
embedding, GIN de trigramas sobre el nombre): `create_all` solo sabe de los
indices declarados en los modelos, y esos dos no pueden declararse ahi sin
romper las pruebas que corren en SQLite. Viven en `infra/postgres/indices/` y
los aplica `make bd-indices`, encadenado al final de `make bd-esquema`.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import DeclarativeBase

from .bd import crear_motor


def materializar(servicio: str, base: type[DeclarativeBase]) -> None:
    """Crea el esquema del servicio en su base y reporta cuantas tablas quedaron.

    Sincrono por fuera (se invoca desde un `python -m ...`), async por dentro
    (el motor lo es). Cierra el motor pase lo que pase."""

    async def _correr() -> int:
        motor = crear_motor(servicio)
        try:
            await motor.crear_esquema(base)
            return len(base.metadata.tables)
        finally:
            await motor.cerrar()

    n = asyncio.run(_correr())
    print(f"[{servicio}] esquema materializado: {n} tablas en tukit_{servicio}")
