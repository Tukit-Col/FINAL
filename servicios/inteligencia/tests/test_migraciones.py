from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tukit_inteligencia.modelos import Base

_VERSIONES = Path(__file__).resolve().parents[1] / "migraciones/versions"
_REVISION_CANONICO = _VERSIONES / "20261025_1200_canonico_de_lista.py"

COLEGIO = "4c06f0e5-cb44-5865-93e5-ea7b2f115d49"
OTRO = "2030c794-3ff4-5b1a-a2ec-5c5d383de3f1"


def _cargar_revision_canonico():
    spec = importlib.util.spec_from_file_location("revision_canonico_de_lista", _REVISION_CANONICO)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def _trabajo(conexion, *, origen: str, estado: str, colegio: str, grado: str, hace_dias: int) -> uuid.UUID:
    tabla = Base.metadata.tables["trabajo_pipeline"]
    trabajo_id = uuid.uuid4()
    terminado = datetime.now(UTC) - timedelta(days=hace_dias)
    conexion.execute(
        sa.insert(tabla).values(
            id=trabajo_id,
            estado=estado,
            origen=origen,
            hijos=[{"referencia": "h", "colegio_id": colegio, "grado": grado, "anio_lectivo": 2026}],
            estimado_segundos=180,
            degradaciones=[],
            cambios={},
            creado_en=terminado,
            actualizado_en=terminado,
            terminado_en=terminado,
        )
    )
    return trabajo_id


def _apuntar(conexion, *, colegio: str, grado: str, trabajo_id: uuid.UUID) -> None:
    conexion.execute(
        sa.insert(Base.metadata.tables["kit_canonico"]).values(
            id=uuid.uuid4(), colegio_id=colegio, grado=grado, anio_lectivo=2026, trabajo_id=trabajo_id
        )
    )


def _puntero(conexion, colegio: str, grado: str) -> uuid.UUID:
    tabla = Base.metadata.tables["kit_canonico"]
    return conexion.scalar(
        sa.select(tabla.c.trabajo_id).where(tabla.c.colegio_id == colegio, tabla.c.grado == grado)
    )


def test_el_grado_vuelve_al_ultimo_canonico_de_su_lista():
    revision = _cargar_revision_canonico()
    assert revision.down_revision == "3c7d9e1f5a28"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        Base.metadata.create_all(conexion)
        viejo = _trabajo(
            conexion,
            origen="canonico_lista",
            estado="publicado",
            colegio=COLEGIO,
            grado="Primero",
            hace_dias=9,
        )
        nuevo = _trabajo(
            conexion,
            origen="canonico_lista",
            estado="publicado",
            colegio=COLEGIO,
            grado="Primero",
            hace_dias=3,
        )
        _trabajo(
            conexion,
            origen="canonico_lista",
            estado="espera_revision",
            colegio=COLEGIO,
            grado="Primero",
            hace_dias=1,
        )
        _trabajo(
            conexion,
            origen="canonico_lista",
            estado="publicado",
            colegio=COLEGIO,
            grado="Segundo",
            hace_dias=0,
        )
        del_papa = _trabajo(
            conexion,
            origen="colegio_grado",
            estado="publicado",
            colegio=COLEGIO,
            grado="Primero",
            hace_dias=2,
        )
        _apuntar(conexion, colegio=COLEGIO, grado="Primero", trabajo_id=del_papa)

        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()

        assert _puntero(conexion, COLEGIO, "Primero") == nuevo
        assert viejo != nuevo


def test_sin_canonico_de_lista_el_puntero_se_queda():
    revision = _cargar_revision_canonico()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        Base.metadata.create_all(conexion)
        del_papa = _trabajo(
            conexion, origen="colegio_grado", estado="publicado", colegio=OTRO, grado="Noveno", hace_dias=2
        )
        _apuntar(conexion, colegio=OTRO, grado="Noveno", trabajo_id=del_papa)

        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()

        assert _puntero(conexion, OTRO, "Noveno") == del_papa


def test_un_canonico_de_lista_no_se_toca():
    revision = _cargar_revision_canonico()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conexion:
        Base.metadata.create_all(conexion)
        actual = _trabajo(
            conexion,
            origen="canonico_lista",
            estado="publicado",
            colegio=COLEGIO,
            grado="Primero",
            hace_dias=5,
        )
        _trabajo(
            conexion,
            origen="canonico_lista",
            estado="publicado",
            colegio=COLEGIO,
            grado="Primero",
            hace_dias=1,
        )
        _apuntar(conexion, colegio=COLEGIO, grado="Primero", trabajo_id=actual)

        with Operations.context(MigrationContext.configure(conexion)):
            revision.upgrade()

        assert _puntero(conexion, COLEGIO, "Primero") == actual


_REVISION_IMPORTACION = _VERSIONES / "20261019_1200_importacion_lista.py"


def _cargar_revision_importacion():
    spec = importlib.util.spec_from_file_location("revision_importacion_lista", _REVISION_IMPORTACION)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def test_upgrade_crea_la_tabla_del_modelo_y_downgrade_la_quita():
    revision = _cargar_revision_importacion()
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
