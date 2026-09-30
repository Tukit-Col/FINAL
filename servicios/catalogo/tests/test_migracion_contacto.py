"""La migracion de `contacto_referencia` va y vuelve en SQLite.

Las pruebas del proyecto corren sobre SQLite en memoria y ahi las columnas
nuevas aparecen solas por `create_all`; esta prueba cubre el otro lado: que la
MIGRACION —la que si toca Postgres en produccion— sea correcta y reversible.

La cadena base tiene una FK circular que solo Postgres admite, asi que no se
puede `create_all` de todo el esquema y correr Alembic encima. En su lugar se
arma el esquema PREVIO a mano (una `tarea_importacion` con todas sus columnas
MENOS la nueva) y se ejerce solo el par upgrade/downgrade de esta revision
contra esa tabla, con `op` atado a la conexion SQLite via `MigrationContext`.
Eso es exactamente lo que el `batch_alter_table` recrea en SQLite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_REVISION = Path(__file__).resolve().parents[1] / (
    "migraciones/versions/20260923_0540_contacto_referencia_en_tarea_.py"
)


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_contacto", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _tarea_previa(metadata: sa.MetaData) -> sa.Table:
    """`tarea_importacion` como estaba ANTES de esta revision (sin la columna)."""
    return sa.Table(
        "tarea_importacion",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("origen", sa.String(32), nullable=False),
        sa.Column("estado", sa.String(24), nullable=False),
        sa.Column("colegio_id", sa.Uuid(), nullable=True),
        sa.Column("grado", sa.String(32), nullable=True),
        sa.Column("anio_lectivo", sa.SmallInteger(), nullable=True),
        sa.Column("documento", sa.LargeBinary(), nullable=True),
    )


def _columnas(conexion: sa.Connection) -> set[str]:
    return {c["name"] for c in sa.inspect(conexion).get_columns("tarea_importacion")}


def test_upgrade_agrega_la_columna_y_downgrade_la_quita():
    revision = _cargar_revision()
    assert revision.revision == "3ac71d5e9b02"
    assert revision.down_revision == "0f882b23c8ad"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        metadata = sa.MetaData()
        _tarea_previa(metadata).create(conexion)
        assert "contacto_referencia" not in _columnas(conexion)

        contexto = MigrationContext.configure(conexion)

        # `Operations.context()` instala unas operaciones atadas a este contexto
        # como el proxy global `alembic.op`, de modo que las funciones de la
        # revision (que llaman a `op.batch_alter_table`) actuen sobre esta
        # conexion SQLite.
        with Operations.context(contexto):
            revision.upgrade()
            assert "contacto_referencia" in _columnas(conexion)

            revision.downgrade()
            assert "contacto_referencia" not in _columnas(conexion)
