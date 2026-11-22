from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_VERSIONES = Path(__file__).resolve().parents[1] / "migraciones" / "versions"


def _cargar_revision(archivo: str):
    spec = importlib.util.spec_from_file_location(f"revision_{archivo}", _VERSIONES / archivo)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _columnas(conexion: sa.Connection) -> set[str]:
    return {c["name"] for c in sa.inspect(conexion).get_columns("tarea_importacion")}


def _tarea(*columnas: sa.Column) -> sa.Table:
    return sa.Table(
        "tarea_importacion",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("origen", sa.String(32), nullable=False),
        *columnas,
    )


def test_contacto_referencia_upgrade_agrega_la_columna_y_downgrade_la_quita():
    revision = _cargar_revision("20260923_0540_contacto_referencia_en_tarea_.py")
    assert revision.revision == "3ac71d5e9b02"
    assert revision.down_revision == "0f882b23c8ad"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        _tarea(
            sa.Column("estado", sa.String(24), nullable=False),
            sa.Column("colegio_id", sa.Uuid(), nullable=True),
            sa.Column("grado", sa.String(32), nullable=True),
            sa.Column("anio_lectivo", sa.SmallInteger(), nullable=True),
            sa.Column("documento", sa.LargeBinary(), nullable=True),
        ).create(conexion)
        assert "contacto_referencia" not in _columnas(conexion)

        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()
            assert "contacto_referencia" in _columnas(conexion)

            revision.downgrade()
            assert "contacto_referencia" not in _columnas(conexion)


def _tarea_antes_de_la_clave(*extra: sa.Column) -> sa.Table:
    return _tarea(
        sa.Column("estado", sa.String(24), nullable=False),
        sa.Column("contacto_referencia", sa.Uuid(), nullable=True),
        *extra,
    )


def test_clave_idempotencia_upgrade_agrega_la_columna_unica_y_downgrade_la_quita():
    revision = _cargar_revision("20261019_1200_clave_idempotencia_en_tarea_.py")
    assert revision.down_revision == "9f3c8d5b1a24"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        tarea = _tarea_antes_de_la_clave()
        tarea.create(conexion)
        conexion.execute(tarea.insert().values(id=uuid.uuid4(), origen="onboarding", estado="completada"))
        conexion.execute(tarea.insert().values(id=uuid.uuid4(), origen="onboarding", estado="completada"))

        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()
            assert "clave_idempotencia" in _columnas(conexion)
            indices = {i["name"]: i for i in sa.inspect(conexion).get_indexes("tarea_importacion")}
            assert indices["uq_tarea_clave_idempotencia"]["unique"]

            nueva = _tarea_antes_de_la_clave(sa.Column("clave_idempotencia", sa.Uuid(), nullable=True))
            clave = uuid.uuid4()
            fila = {"origen": "sugerencia_padre", "estado": "completada", "clave_idempotencia": clave}
            conexion.execute(nueva.insert().values(id=uuid.uuid4(), **fila))
            with pytest.raises(sa.exc.IntegrityError), conexion.begin_nested():
                conexion.execute(nueva.insert().values(id=uuid.uuid4(), **fila))

            revision.downgrade()
            assert "clave_idempotencia" not in _columnas(conexion)


def test_referencias_upgrade_agrega_la_columna_y_downgrade_la_quita():
    revision = _cargar_revision("20261112_1200_referencias_en_tarea_.py")
    assert revision.down_revision == "5c1d8e2f7a90"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        _tarea().create(conexion)
        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()
            assert "referencias" in _columnas(conexion)
            revision.downgrade()
            assert "referencias" not in _columnas(conexion)
