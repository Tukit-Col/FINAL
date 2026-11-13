"""La migracion de `referencias` en `tarea_importacion` va y vuelve en SQLite.

Mismo patron que `test_migracion_clave_idempotencia`: se arma a mano la tabla
previa y se ejerce solo el par upgrade/downgrade de esta revision.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_REVISION = Path(__file__).resolve().parents[1] / (
    "migraciones/versions/20261112_1200_referencias_en_tarea_.py"
)


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_referencias", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _columnas(conexion: sa.Connection) -> set[str]:
    return {c["name"] for c in sa.inspect(conexion).get_columns("tarea_importacion")}


def test_upgrade_agrega_la_columna_y_downgrade_la_quita():
    revision = _cargar_revision()
    assert revision.down_revision == "5c1d8e2f7a90"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        sa.Table(
            "tarea_importacion",
            sa.MetaData(),
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("origen", sa.String(32), nullable=False),
        ).create(conexion)
        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()
            assert "referencias" in _columnas(conexion)
            revision.downgrade()
            assert "referencias" not in _columnas(conexion)
