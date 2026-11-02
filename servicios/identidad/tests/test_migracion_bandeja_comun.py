"""La revision que alinea la bandeja de Identidad va y vuelve en SQLite (ADR 0048).

La suite crea las tablas con `create_all`; esta prueba ejerce el par
upgrade/downgrade sobre la `bandeja_salida` PREVIA, con una fila de antes, y
fija que el id de usuario de `clave_agregado` sobrevive en `agregado_id`.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_REVISION = (
    Path(__file__).resolve().parents[1] / "migraciones/versions/20261101_1200_bandeja_con_la_forma_comun.py"
)


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_bandeja_comun", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _columnas(conexion: sa.Connection) -> set[str]:
    return {c["name"] for c in sa.inspect(conexion).get_columns("bandeja_salida")}


def test_upgrade_alinea_la_bandeja_y_downgrade_la_devuelve():
    revision = _cargar_revision()
    assert revision.down_revision == "6e2f9a4c1d83"
    usuario = uuid.uuid4()

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        previa = sa.Table(
            "bandeja_salida",
            sa.MetaData(),
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tipo_evento", sa.String(128), nullable=False),
            sa.Column("clave_agregado", sa.String(128), nullable=False),
            sa.Column("carga", sa.JSON(), nullable=False),
            sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        )
        previa.create(conexion)
        conexion.execute(
            previa.insert().values(tipo_evento="titular_suprimido", clave_agregado=str(usuario), carga={})
        )

        revision.op = Operations(MigrationContext.configure(conexion))
        revision.upgrade()

        assert {"tipo", "agregado_tipo", "agregado_id"} <= _columnas(conexion)
        assert not {"tipo_evento", "clave_agregado"} & _columnas(conexion)
        nueva = sa.Table(
            "bandeja_salida",
            sa.MetaData(),
            sa.Column("tipo", sa.String()),
            sa.Column("agregado_tipo", sa.String()),
            sa.Column("agregado_id", sa.Uuid()),
        )
        fila = conexion.execute(sa.select(nueva)).one()
        assert (fila.tipo, fila.agregado_tipo, fila.agregado_id) == ("titular_suprimido", "usuario", usuario)

        revision.downgrade()

        assert {"tipo_evento", "clave_agregado"} <= _columnas(conexion)
        assert not {"tipo", "agregado_tipo", "agregado_id"} & _columnas(conexion)
        assert conexion.execute(sa.text("SELECT clave_agregado FROM bandeja_salida")).scalar_one() == str(
            usuario
        )
