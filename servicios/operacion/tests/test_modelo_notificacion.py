from __future__ import annotations

import importlib.util
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_operacion.modelos import Base, Notificacion, PreferenciaNotificacion

NOTIFICACION = Base.metadata.tables["notificacion"]
PROHIBIDAS = {"correo", "email", "celular", "telefono", "phone"}
_REVISION = (
    Path(__file__).resolve().parents[1] / "migraciones/versions/20261019_1200_evento_en_notificacion.py"
)


def _aviso(estado: str, evento_origen: str | None = "comercio", evento_id: int | None = 7) -> dict:
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


@pytest.mark.parametrize("modelo", [Notificacion, PreferenciaNotificacion], ids=lambda m: m.__tablename__)
def test_referencia_al_usuario_por_id_y_no_guarda_contacto(modelo):
    columnas = {c.name for c in modelo.__table__.columns}
    assert PROHIBIDAS.isdisjoint(columnas)
    assert "usuario_id" in columnas


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def test_no_admite_dos_avisos_enviados_del_mismo_evento(engine):
    async with engine.connect() as conexion:
        await conexion.execute(sa.insert(NOTIFICACION).values(**_aviso("enviada")))
        with pytest.raises(sa.exc.IntegrityError):
            async with conexion.begin_nested():
                await conexion.execute(sa.insert(NOTIFICACION).values(**_aviso("enviada")))


async def test_admite_varios_fallidos_y_avisos_sin_evento(engine):
    filas = [
        _aviso("fallida"),
        _aviso("fallida"),
        _aviso("enviada"),
        _aviso("enviada", evento_origen="inteligencia"),
        _aviso("enviada", evento_origen=None, evento_id=None),
        _aviso("enviada", evento_origen=None, evento_id=None),
    ]
    async with engine.begin() as conexion:
        for fila in filas:
            await conexion.execute(sa.insert(NOTIFICACION).values(**fila))
        total = await conexion.scalar(sa.select(sa.func.count()).select_from(NOTIFICACION))

    assert total == len(filas)


def _cargar_revision():
    spec = importlib.util.spec_from_file_location("revision_evento_notificacion", _REVISION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _notificacion_previa(*extra: sa.Column) -> sa.Table:
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


def test_la_migracion_agrega_el_evento_con_su_indice_parcial_y_el_downgrade_lo_quita():
    revision = _cargar_revision()
    assert revision.down_revision == "d0bf03671b97"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        previa = _notificacion_previa()
        previa.create(conexion)
        aviso_de_antes = {k: v for k, v in _aviso("enviada").items() if not k.startswith("evento_")}
        conexion.execute(previa.insert().values(**aviso_de_antes))

        contexto = MigrationContext.configure(conexion)
        with Operations.context(contexto):
            revision.upgrade()
            posteriores = {"asunto", "detalle", "destino_dominio"}
            assert _columnas(conexion) == {c.name for c in NOTIFICACION.columns} - posteriores
            indices = {i["name"]: i for i in sa.inspect(conexion).get_indexes("notificacion")}
            indice = indices["uq_notificacion_evento_enviada"]
            assert indice["unique"]
            assert indice["column_names"] == ["evento_origen", "evento_id"]

            nueva = _notificacion_previa(
                sa.Column("evento_origen", sa.String(32), nullable=True),
                sa.Column("evento_id", sa.BigInteger(), nullable=True),
            )
            conexion.execute(nueva.insert().values(**_aviso("fallida")))
            conexion.execute(nueva.insert().values(**_aviso("fallida")))
            conexion.execute(nueva.insert().values(**_aviso("enviada")))
            with pytest.raises(sa.exc.IntegrityError), conexion.begin_nested():
                conexion.execute(nueva.insert().values(**_aviso("enviada")))
            conexion.execute(nueva.insert().values(**_aviso("enviada", evento_origen="inteligencia")))

            revision.downgrade()
            assert "evento_origen" not in _columnas(conexion)
            assert "evento_id" not in _columnas(conexion)
            assert "uq_notificacion_evento_enviada" not in {
                i["name"] for i in sa.inspect(conexion).get_indexes("notificacion")
            }
            assert conexion.scalar(sa.select(sa.func.count()).select_from(previa)) == 5
