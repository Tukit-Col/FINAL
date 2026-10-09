"""NFR-MAN-01: `materializar` crea el esquema del servicio y siempre cierra el motor (`esquema.py`).

Es el `__main__` de una linea de cada servicio (`python -m tukit_<servicio>`):
sincrono por fuera, async por dentro. Se prueba contra un archivo SQLite
temporal (la URL llega por `TUKIT_<SERVICIO>_DB_URL`, como en un compose) y se
verifica en el archivo, con un cliente independiente, que las tablas
quedaron de verdad. La rama de fallo importa tanto como la feliz: si crear el
esquema revienta, el motor se cierra igual y el error llega al operador en vez
de un proceso colgado con conexiones abiertas.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tukit_comun import esquema
from tukit_comun.esquema import materializar

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class Base(DeclarativeBase):
    pass


class Cosa(Base):
    __tablename__ = "cosa_esquema"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(32))


class OtraCosa(Base):
    __tablename__ = "otra_cosa_esquema"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


def _tablas(archivo: Path) -> set[str]:
    with sqlite3.connect(archivo) as conexion:
        filas = conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {nombre for (nombre,) in filas}


def test_crea_las_tablas_del_servicio_en_su_base_y_reporta_cuantas(tmp_path, monkeypatch, capsys):
    archivo = tmp_path / "prueba.db"
    monkeypatch.setenv("TUKIT_PRUEBA_DB_URL", f"sqlite+aiosqlite:///{archivo}")

    materializar("prueba", Base)

    assert _tablas(archivo) == {"cosa_esquema", "otra_cosa_esquema"}
    assert capsys.readouterr().out == "[prueba] esquema materializado: 2 tablas en tukit_prueba\n"


def test_es_idempotente_correrlo_dos_veces_no_falla_ni_duplica(tmp_path, monkeypatch, capsys):
    """Provision, no migracion: crea lo que falta y no toca lo que ya hay."""
    archivo = tmp_path / "prueba.db"
    monkeypatch.setenv("TUKIT_PRUEBA_DB_URL", f"sqlite+aiosqlite:///{archivo}")
    materializar("prueba", Base)
    with sqlite3.connect(archivo) as conexion:
        conexion.execute("INSERT INTO cosa_esquema (id, nombre) VALUES (1, 'Cosa Ficticia Uno')")

    materializar("prueba", Base)

    with sqlite3.connect(archivo) as conexion:
        assert conexion.execute("SELECT nombre FROM cosa_esquema").fetchall() == [("Cosa Ficticia Uno",)]
    assert _tablas(archivo) == {"cosa_esquema", "otra_cosa_esquema"}
    assert capsys.readouterr().out.count("esquema materializado") == 2


def test_el_motor_se_cierra_aunque_crear_el_esquema_falle(monkeypatch, capsys):
    pasos: list[str] = []

    class MotorQueFalla:
        async def crear_esquema(self, base: type[DeclarativeBase]) -> None:
            pasos.append("crear_esquema")
            raise ConnectionError("la base no responde")

        async def cerrar(self) -> None:
            pasos.append("cerrar")

    monkeypatch.setattr(esquema, "crear_motor", lambda servicio: MotorQueFalla())

    with pytest.raises(ConnectionError, match="la base no responde"):
        materializar("prueba", Base)

    assert pasos == ["crear_esquema", "cerrar"]
    assert capsys.readouterr().out == ""  # no anuncia un exito que no hubo


def test_pide_el_motor_del_servicio_que_se_le_nombra(monkeypatch, capsys):
    pedidos: list[str] = []

    def crear_motor(servicio: str):
        pedidos.append(servicio)

        async def crear_esquema(base: type[DeclarativeBase]) -> None:
            pedidos.append(f"esquema:{len(base.metadata.tables)}")

        async def cerrar() -> None:
            pedidos.append("cerrado")

        return SimpleNamespace(crear_esquema=crear_esquema, cerrar=cerrar)

    monkeypatch.setattr(esquema, "crear_motor", crear_motor)

    materializar("comercio", Base)

    assert pedidos == ["comercio", "esquema:2", "cerrado"]
    assert "[comercio] esquema materializado: 2 tablas en tukit_comercio" in capsys.readouterr().out
