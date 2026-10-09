"""NFR-MAN-01: el motor compartido de base de datos y su sesion por unidad de trabajo (`bd.py`).

`test_bd_extensiones.py` fija que las listas de extensiones coinciden y que
`crear_esquema` no rompe SQLite. Aqui se caracteriza el resto del contrato:
`sesion()` confirma lo que sale bien y DESHACE lo que revienta (sin esto, un
fallo a mitad de una saga deja medio pedido escrito), `crear_motor` lee la URL
del entorno y arma el motor con `pool_pre_ping`, las sesiones no expiran los
objetos al confirmar, y en Postgres las extensiones se aseguran ANTES de las
tablas y en su propia transaccion (un `Vector(1024)` no se puede emitir sin la
extension). Postgres no esta en la CI: el dialecto se simula con un motor de
mentira que anota las sentencias.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tukit_comun import bd
from tukit_comun.bd import EXTENSIONES, MotorServicio, crear_motor, sesion_de_prueba

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class Base(DeclarativeBase):
    pass


class Cosa(Base):
    __tablename__ = "cosa_motor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(32))


@pytest.fixture
async def motor():
    motor = sesion_de_prueba(Base)
    await motor.crear_esquema(Base)
    yield motor
    await motor.cerrar()


async def _nombres(motor: MotorServicio) -> list[str]:
    async with motor.sesion() as db:
        return [c.nombre for c in (await db.execute(select(Cosa).order_by(Cosa.id))).scalars()]


class TestLaSesionEsUnaUnidadDeTrabajo:
    async def test_lo_que_sale_bien_se_confirma(self, motor):
        async with motor.sesion() as db:
            db.add(Cosa(id=1, nombre="Cosa Ficticia Uno"))

        assert await _nombres(motor) == ["Cosa Ficticia Uno"]

    async def test_lo_que_revienta_se_deshace_y_la_excepcion_sale(self, motor):
        with pytest.raises(RuntimeError, match="a mitad de la saga"):
            async with motor.sesion() as db:
                db.add(Cosa(id=1, nombre="Cosa Ficticia Uno"))
                await db.flush()  # ya esta escrito en la transaccion...
                raise RuntimeError("a mitad de la saga")

        assert await _nombres(motor) == []  # ...y el rollback lo borra

    async def test_un_fallo_no_contamina_la_siguiente_unidad_de_trabajo(self, motor):
        with pytest.raises(ValueError):
            async with motor.sesion() as db:
                db.add(Cosa(id=1, nombre="Cosa Ficticia Uno"))
                raise ValueError("se descarta")

        async with motor.sesion() as db:
            db.add(Cosa(id=2, nombre="Cosa Ficticia Dos"))

        assert await _nombres(motor) == ["Cosa Ficticia Dos"]

    async def test_los_objetos_siguen_legibles_despues_de_confirmar(self, motor):
        """`expire_on_commit=False`: el handler puede devolver lo que acaba de
        guardar sin que SQLAlchemy intente recargarlo fuera de la sesion."""
        async with motor.sesion() as db:
            cosa = Cosa(id=1, nombre="Cosa Ficticia Uno")
            db.add(cosa)

        assert (cosa.id, cosa.nombre) == (1, "Cosa Ficticia Uno")


class TestCrearMotorLeeElEntorno:
    async def test_arma_el_motor_con_la_url_del_servicio_y_pre_ping(self, monkeypatch):
        monkeypatch.setenv("TUKIT_PRUEBA_DB_URL", "sqlite+aiosqlite:///:memory:")
        recibido: dict[str, Any] = {}
        real = create_async_engine

        def espia(url: str, **kwargs: Any):
            recibido.update(url=url, **kwargs)
            return real(url)

        monkeypatch.setattr(bd, "create_async_engine", espia)

        motor = crear_motor("prueba")
        try:
            assert motor.servicio == "prueba"
            assert recibido == {"url": "sqlite+aiosqlite:///:memory:", "echo": False, "pool_pre_ping": True}
        finally:
            await motor.cerrar()

    async def test_echo_se_propaga(self, monkeypatch):
        monkeypatch.setenv("TUKIT_PRUEBA_DB_URL", "sqlite+aiosqlite:///:memory:")

        motor = crear_motor("prueba", echo=True)
        try:
            assert motor.engine.echo is True
        finally:
            await motor.cerrar()

    async def test_el_motor_creado_funciona_de_punta_a_punta(self, monkeypatch):
        monkeypatch.setenv("TUKIT_PRUEBA_DB_URL", "sqlite+aiosqlite:///:memory:")
        motor = crear_motor("prueba")
        try:
            await motor.crear_esquema(Base)
            async with motor.sesion() as db:
                db.add(Cosa(id=7, nombre="Cosa Ficticia Siete"))

            assert await _nombres(motor) == ["Cosa Ficticia Siete"]
        finally:
            await motor.cerrar()


class _ConexionFalsa:
    def __init__(self, eventos: list[Any]) -> None:
        self._eventos = eventos

    async def execute(self, sentencia: Any) -> None:
        self._eventos.append(("sql", str(sentencia)))

    async def run_sync(self, funcion: Any, *args: Any) -> None:
        self._eventos.append(("run_sync", funcion))


def _motor_de(dialecto: str) -> tuple[MotorServicio, list[Any]]:
    """Un `MotorServicio` cuyo engine solo anota lo que se le pide, con el dialecto dado."""
    eventos: list[Any] = []

    @asynccontextmanager
    async def begin():
        eventos.append("begin")
        yield _ConexionFalsa(eventos)
        eventos.append("commit")

    engine = SimpleNamespace(dialect=SimpleNamespace(name=dialecto), begin=begin)
    return MotorServicio(servicio="prueba", engine=engine, _fabrica=None), eventos  # type: ignore[arg-type]


class TestExtensionesDePostgres:
    async def test_en_postgres_habilita_cada_extension_en_una_sola_transaccion(self):
        motor, eventos = _motor_de("postgresql")

        await motor.asegurar_extensiones()

        assert eventos == [
            "begin",
            *[("sql", f'CREATE EXTENSION IF NOT EXISTS "{ext}"') for ext in EXTENSIONES],
            "commit",
        ]
        assert set(EXTENSIONES) == {"vector", "pg_trgm"}

    @pytest.mark.parametrize("dialecto", ["sqlite", "mysql"])
    async def test_fuera_de_postgres_no_emite_nada(self, dialecto):
        motor, eventos = _motor_de(dialecto)

        await motor.asegurar_extensiones()

        assert eventos == []

    async def test_crear_esquema_asegura_las_extensiones_antes_y_aparte_de_las_tablas(self):
        """Dos transacciones, en este orden: la primera confirma las extensiones y
        solo despues se emiten las tablas con sus columnas `vector`."""
        motor, eventos = _motor_de("postgresql")

        await motor.crear_esquema(Base)

        sql = [("sql", f'CREATE EXTENSION IF NOT EXISTS "{ext}"') for ext in EXTENSIONES]
        assert eventos == [
            "begin",
            *sql,
            "commit",  # las extensiones quedan confirmadas...
            "begin",
            ("run_sync", Base.metadata.create_all),  # ...antes de abrir la de las tablas
            "commit",
        ]
