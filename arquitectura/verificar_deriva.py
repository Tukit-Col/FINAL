"""Compara el esquema que dejan las migraciones contra el que declaran los modelos.

Esta es la funcion de aptitud que le faltaba a la base de datos. Las otras
viven en `test_fronteras.py` y miran el codigo; esta mira el motor, porque hay
una clase de fallo que no se ve de ninguna otra forma: el modelo declara una
restriccion, la migracion no la crea, y todo sigue verde.

No es hipotetico. Las dos primeras cosas que encontro, el dia que se escribio:

- `grupo_variante.representante_id` y `producto_canonico.grupo_variante_id` se
  apuntan entre si. SQLAlchemy resuelve el ciclo sacando una llave del CREATE
  TABLE, pero `op.create_table` no emite despues el ALTER que la pondria, asi
  que la migracion producia una tabla SIN esa llave foranea. Un hueco de
  integridad referencial, en silencio, y `create_all` no lo mostraba porque el
  camino de `create_all` si difiere las llaves.

- `concepto_ruta_categoria` declaraba una restriccion unica sobre las mismas
  tres columnas de su llave primaria. Postgres las funde al crear la tabla y la
  superviviente se queda con el nombre de la otra, asi que el esquema real
  dejaba de parecerse al declarado.

Necesita un Postgres vivo, asi que no corre en la suite normal: se invoca con
`make bd-deriva`, despues de `make bd-migrar`.

Los indices de `infra/postgres/indices/` se excluyen a proposito. No los
declara ningun modelo (HNSW y los trigramas no tienen forma en SQLAlchemy) y
que falten es justo lo que comprueba `make bd-verificar`. Sin esta exclusion
esta herramienta pediria borrarlos en cada ejecucion.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
SERVICIOS = ("identidad", "catalogo", "inteligencia")

# Indices que viven en infra/ y no en los modelos. Ver el docstring.
INDICES_DE_INFRA = frozenset({"ix_producto_embedding_hnsw", "ix_producto_nombre_trgm"})


def _preparar_rutas() -> None:
    sys.path.insert(0, str(RAIZ / "libs" / "py" / "tukit_comun"))
    for servicio in SERVICIOS:
        sys.path.insert(0, str(RAIZ / "servicios" / servicio))


def _es_de_infra(diferencia: Any) -> bool:
    """Descarta lo que se refiere a un indice que no pertenece a los modelos."""
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
    from tukit_identidad.modelos import Base as BaseIdentidad
    from tukit_inteligencia.modelos import Base as BaseInteligencia

    bases = {
        "identidad": BaseIdentidad,
        "catalogo": BaseCatalogo,
        "inteligencia": BaseInteligencia,
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
