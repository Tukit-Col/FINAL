from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import Integer, String, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tukit_comun.bd import EXTENSIONES, sesion_de_prueba

RAIZ = Path(__file__).resolve().parents[4]
INIT_SQL = RAIZ / "infra" / "postgres" / "init" / "01-crear-bases.sql"
INDICES = RAIZ / "infra" / "postgres" / "indices"


class Base(DeclarativeBase):
    pass


class Cosa(Base):
    __tablename__ = "cosa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(32))


async def test_crear_esquema_sigue_funcionando_en_sqlite():
    motor = sesion_de_prueba(Base)
    try:
        await motor.asegurar_extensiones()
        await motor.crear_esquema(Base)

        async with motor.engine.connect() as conexion:
            tablas = await conexion.run_sync(lambda c: inspect(c).get_table_names())
    finally:
        await motor.cerrar()

    assert "cosa" in tablas


def test_el_init_de_postgres_habilita_las_mismas_extensiones_que_la_libreria():
    sql = INIT_SQL.read_text(encoding="utf-8")

    bases = re.findall(r"^CREATE DATABASE (\w+);", sql, flags=re.MULTILINE)
    assert len(bases) == 5, f"Se esperaban las cinco bases del manifiesto, hay {len(bases)}: {bases}"

    bloques = {
        nombre: cuerpo for nombre, cuerpo in re.findall(r"\\connect (\w+)\n(.*?)(?=\\connect |\Z)", sql, re.S)
    }

    faltantes = [
        f"  {base}: falta `{ext}`"
        for base in bases
        for ext in EXTENSIONES
        if f"CREATE EXTENSION IF NOT EXISTS {ext};" not in bloques.get(base, "")
    ]
    assert not faltantes, (
        "El init de Postgres no habilita todas las extensiones que la libreria asegura:\n"
        + "\n".join(faltantes)
        + "\n\nAgregala en 01-crear-bases.sql para las bases nuevas, o quitala de "
        "`tukit_comun.bd.EXTENSIONES` si ya no hace falta."
    )


def test_los_indices_de_postgres_son_idempotentes():
    archivos = sorted(INDICES.glob("*.sql"))
    assert archivos, f"No hay archivos de indices en {INDICES.relative_to(RAIZ)}"

    sin_guardia = [
        f"  {ruta.relative_to(RAIZ)}: {sentencia}"
        for ruta in archivos
        for sentencia in re.findall(r"^CREATE (?:UNIQUE )?INDEX.*$", ruta.read_text(encoding="utf-8"), re.M)
        if "IF NOT EXISTS" not in sentencia
    ]
    assert not sin_guardia, "Hay indices que no se pueden volver a aplicar:\n" + "\n".join(sin_guardia)


def test_cada_archivo_de_indices_nombra_un_servicio_con_base_propia():
    bases = set(re.findall(r"^CREATE DATABASE (\w+);", INIT_SQL.read_text(encoding="utf-8"), re.M))

    huerfanos = [
        f"  {ruta.name} -> tukit_{ruta.stem} no existe"
        for ruta in sorted(INDICES.glob("*.sql"))
        if f"tukit_{ruta.stem}" not in bases
    ]
    assert not huerfanos, "Archivos de indices sin base a la que aplicarse:\n" + "\n".join(huerfanos)
