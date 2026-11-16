"""La migracion del evento en `notificacion` va y vuelve en SQLite (ADR 0042).

La suite crea las tablas con `create_all`, asi que las columnas nuevas aparecen
solas en las demas pruebas; esta cubre el otro lado: que la MIGRACION, la que
corre contra Postgres, agregue lo que el modelo declara y que el downgrade lo
quite. Se arma a mano la `notificacion` PREVIA (sin las columnas), con una fila
de antes, y se ejerce solo el par upgrade/downgrade de esta revision.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tukit_operacion.modelos import Base

_REVISION = (
    Path(__file__).resolve().parents[1] / "migraciones/versions/20261019_1200_evento_en_notificacion.py"
)


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_evento_notificacion", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _notificacion(*extra: sa.Column) -> sa.Table:
    """`notificacion` como estaba ANTES de esta revision, mas `extra`."""
    return sa.Table(
        "notificacion",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("canal", sa.String(16), nullable=False),
        sa.Column("plantilla", sa.String(64), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("estado", sa.String(16), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("enviada_en", sa.DateTime(timezone=True), nullable=True),
        *extra,
    )


def _columnas(conexion: sa.Connection) -> set[str]:
    return {c["name"] for c in sa.inspect(conexion).get_columns("notificacion")}


def _aviso(estado: str, evento_origen: str | None = "comercio", evento_id: int | None = 1) -> dict:
    return {
        "id": uuid.uuid4(),
        "usuario_id": uuid.uuid4(),
        "canal": "correo",
        "plantilla": "pedido_pagado",
        "datos": {},
        "estado": estado,
        "evento_origen": evento_origen,
        "evento_id": evento_id,
    }


def test_upgrade_agrega_el_evento_con_su_indice_parcial_y_downgrade_lo_quita():
    revision = _cargar_revision()
    assert revision.down_revision == "d0bf03671b97"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        previa = _notificacion()
        previa.create(conexion)
        # Las notificaciones que ya existian no tienen evento y tienen que seguir valiendo.
        aviso_de_antes = {k: v for k, v in _aviso("enviada").items() if not k.startswith("evento_")}
        conexion.execute(previa.insert().values(**aviso_de_antes))

        contexto = MigrationContext.configure(conexion)
        with Operations.context(contexto):
            revision.upgrade()
            # Las columnas de revisiones posteriores (asunto, detalle, destino_dominio) no son de esta.
            posteriores = {"asunto", "detalle", "destino_dominio"}
            assert _columnas(conexion) == {
                c.name for c in Base.metadata.tables["notificacion"].columns
            } - posteriores
            indices = {i["name"]: i for i in sa.inspect(conexion).get_indexes("notificacion")}
            indice = indices["uq_notificacion_evento_enviada"]
            assert indice["unique"]
            assert indice["column_names"] == ["evento_origen", "evento_id"]

            nueva = _notificacion(
                sa.Column("evento_origen", sa.String(32), nullable=True),
                sa.Column("evento_id", sa.BigInteger(), nullable=True),
            )
            # Varios intentos fallidos del mismo evento y uno enviado conviven...
            conexion.execute(nueva.insert().values(**_aviso("fallida")))
            conexion.execute(nueva.insert().values(**_aviso("fallida")))
            conexion.execute(nueva.insert().values(**_aviso("enviada")))
            # ...pero no dos enviados del mismo evento.
            with pytest.raises(sa.exc.IntegrityError), conexion.begin_nested():
                conexion.execute(nueva.insert().values(**_aviso("enviada")))
            # El mismo id en otra bandeja es otro evento.
            conexion.execute(nueva.insert().values(**_aviso("enviada", evento_origen="inteligencia")))

            revision.downgrade()
            assert "evento_origen" not in _columnas(conexion)
            assert "evento_id" not in _columnas(conexion)
            assert "uq_notificacion_evento_enviada" not in {
                i["name"] for i in sa.inspect(conexion).get_indexes("notificacion")
            }
            assert conexion.scalar(sa.select(sa.func.count()).select_from(previa)) == 5
