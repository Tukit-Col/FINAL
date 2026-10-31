"""La migracion de `importacion_lista` va y vuelve en SQLite (ADR 0040).

La suite crea las tablas con `create_all`, asi que la tabla nueva aparece sola
en las demas pruebas; esta cubre el otro lado: que la MIGRACION, la que corre
contra Postgres, cree la tabla que el modelo declara y que el downgrade la
quite. La tabla no tiene llaves foraneas, asi que basta una base vacia.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tukit_inteligencia.modelos import Base

_REVISION = Path(__file__).resolve().parents[1] / "migraciones/versions/20261019_1200_importacion_lista.py"


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_importacion_lista", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def test_upgrade_crea_la_tabla_del_modelo_y_downgrade_la_quita():
    revision = _cargar_revision()
    assert revision.down_revision == "9e3a5f7b2c41"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        contexto = MigrationContext.configure(conexion)
        with Operations.context(contexto):
            revision.upgrade()
            inspector = sa.inspect(conexion)
            columnas = {c["name"] for c in inspector.get_columns("importacion_lista")}
            assert columnas == {c.name for c in Base.metadata.tables["importacion_lista"].columns}
            indices = {i["name"]: i for i in inspector.get_indexes("importacion_lista")}
            assert {"ix_importacion_pendiente", "ix_importacion_contacto"} <= set(indices)
            unicas = {u["name"] for u in inspector.get_unique_constraints("importacion_lista")}
            assert "uq_importacion_clave" in unicas

            revision.downgrade()
            assert "importacion_lista" not in sa.inspect(conexion).get_table_names()
