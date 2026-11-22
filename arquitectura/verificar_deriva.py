"""Compara el esquema que dejan las migraciones contra el que declaran los modelos.

Decisiones:
- Mira el motor y no el codigo, porque hay un fallo que no se ve de otra forma: el modelo declara
  una restriccion, la migracion no la crea y todo sigue verde. Por ejemplo, las llaves marcadas
  `use_alter` (un ciclo entre dos tablas) las omite `op.create_table`, y la tabla queda sin esa
  llave foranea.
- Necesita un Postgres vivo, asi que no corre con pytest: es `make bd-deriva`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
SERVICIOS = ("identidad", "catalogo", "inteligencia", "comercio", "operacion")

INDICES_DE_INFRA = frozenset({"ix_producto_embedding_hnsw", "ix_producto_nombre_trgm"})


def _preparar_rutas() -> None:
    sys.path.insert(0, str(RAIZ / "libs" / "py" / "tukit_comun"))
    for servicio in SERVICIOS:
        sys.path.insert(0, str(RAIZ / "servicios" / servicio))


def _es_de_infra(diferencia: Any) -> bool:
    if not isinstance(diferencia, tuple) or len(diferencia) < 2:
        return False
    objeto = diferencia[1]
    return getattr(objeto, "name", None) in INDICES_DE_INFRA


async def _diferencias(servicio: str, metadata: Any) -> list[Any]:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from tukit_comun.bd import crear_motor

    motor = crear_motor(servicio)
    try:
        async with motor.engine.begin() as conexion:

            def _comparar(sincrona: Any) -> list[Any]:
                contexto = MigrationContext.configure(
                    sincrona, opts={"compare_type": True, "compare_server_default": True}
                )
                return compare_metadata(contexto, metadata)

            crudas = await conexion.run_sync(_comparar)
    finally:
        await motor.cerrar()

    return [d for d in crudas if not _es_de_infra(d)]


async def _principal() -> int:
    from tukit_catalogo.modelos import Base as BaseCatalogo
    from tukit_comercio.modelos import Base as BaseComercio
    from tukit_identidad.modelos import Base as BaseIdentidad
    from tukit_inteligencia.modelos import Base as BaseInteligencia
    from tukit_operacion.modelos import Base as BaseOperacion

    bases = {
        "identidad": BaseIdentidad,
        "catalogo": BaseCatalogo,
        "inteligencia": BaseInteligencia,
        "comercio": BaseComercio,
        "operacion": BaseOperacion,
    }
    total = 0

    for servicio in SERVICIOS:
        try:
            diferencias = await _diferencias(servicio, bases[servicio].metadata)
        except Exception as error:  # noqa: BLE001
            print(f"  ERROR {servicio}: {error}")
            print("    Falta la base o las migraciones. Corre: make bd-migrar")
            return 2

        if not diferencias:
            print(f"  ok   {servicio}: el esquema migrado coincide con los modelos")
            continue

        total += len(diferencias)
        print(f"  DERIVA {servicio}: {len(diferencias)} diferencia(s)")
        for diferencia in diferencias:
            print(f"      {diferencia}")

    if total:
        print("\nLos modelos y las migraciones no dicen lo mismo.")
        print("Si el modelo es lo correcto: make bd-revision m='...' y revisa lo generado.")
        print("Ojo con las llaves marcadas `use_alter`: el autogenerador las omite y hay")
        print("que agregar el op.create_foreign_key a mano.")
        return 1

    print("\nSin deriva.")
    return 0


if __name__ == "__main__":
    _preparar_rutas()
    raise SystemExit(asyncio.run(_principal()))
