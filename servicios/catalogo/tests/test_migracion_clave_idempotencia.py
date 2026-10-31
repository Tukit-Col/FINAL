"""La migracion de `clave_idempotencia` va y vuelve en SQLite (ADR 0040).

Mismo patron que `test_migracion_contacto`: la cadena base tiene una FK
circular que solo Postgres admite, asi que se arma a mano la
`tarea_importacion` PREVIA (sin la columna) y se ejerce solo el par
upgrade/downgrade de esta revision contra esa tabla.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_REVISION = Path(__file__).resolve().parents[1] / (
    "migraciones/versions/20261019_1200_clave_idempotencia_en_tarea_.py"
)


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_clave_idempotencia", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _tarea(*extra: sa.Column) -> sa.Table:
    """`tarea_importacion` como estaba ANTES de esta revision, mas `extra`."""
    return sa.Table(
        "tarea_importacion",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("origen", sa.String(32), nullable=False),
        sa.Column("estado", sa.String(24), nullable=False),
        sa.Column("contacto_referencia", sa.Uuid(), nullable=True),
        *extra,
    )


def _columnas(conexion: sa.Connection) -> set[str]:
    return {c["name"] for c in sa.inspect(conexion).get_columns("tarea_importacion")}


def test_upgrade_agrega_la_columna_unica_y_downgrade_la_quita():
    revision = _cargar_revision()
    assert revision.down_revision == "9f3c8d5b1a24"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        tarea = _tarea()
        tarea.create(conexion)
        # Las tareas que ya existian no tienen clave y tienen que seguir valiendo.
        conexion.execute(tarea.insert().values(id=uuid.uuid4(), origen="onboarding", estado="completada"))
        conexion.execute(tarea.insert().values(id=uuid.uuid4(), origen="onboarding", estado="completada"))

        contexto = MigrationContext.configure(conexion)
        with Operations.context(contexto):
            revision.upgrade()
            assert "clave_idempotencia" in _columnas(conexion)
            indices = {i["name"]: i for i in sa.inspect(conexion).get_indexes("tarea_importacion")}
            assert indices["uq_tarea_clave_idempotencia"]["unique"]

            nueva = _tarea(sa.Column("clave_idempotencia", sa.Uuid(), nullable=True))
            clave = uuid.uuid4()
            fila = {"origen": "sugerencia_padre", "estado": "completada", "clave_idempotencia": clave}
            conexion.execute(nueva.insert().values(id=uuid.uuid4(), **fila))
            with pytest.raises(sa.exc.IntegrityError), conexion.begin_nested():
                conexion.execute(nueva.insert().values(id=uuid.uuid4(), **fila))

            revision.downgrade()
            assert "clave_idempotencia" not in _columnas(conexion)
