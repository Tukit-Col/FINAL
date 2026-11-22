from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy import Integer, String, insert, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tukit_comun.bd import sesion_de_prueba
from tukit_comun.dependencias import repo_dep


class Base(DeclarativeBase):
    pass


class Nota(Base):
    __tablename__ = "nota"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    texto: Mapped[str] = mapped_column(String(64))


class RepoNotas:
    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def guardar(self, texto: str) -> None:
        await self.conexion.execute(insert(Nota).values(texto=texto))

    async def contar(self) -> int:
        filas = await self.conexion.execute(select(Nota.id))
        return len(filas.fetchall())


def _app(motor: Any) -> FastAPI:
    app = FastAPI()
    dep = repo_dep(motor, RepoNotas)

    @app.post("/guardar")
    async def guardar(texto: str, repo: RepoNotas = Depends(dep)) -> dict[str, str]:
        await repo.guardar(texto)
        return {"estado": "ok"}

    @app.post("/guardar-y-fallar")
    async def guardar_y_fallar(texto: str, repo: RepoNotas = Depends(dep)) -> dict[str, str]:
        await repo.guardar(texto)
        raise RuntimeError("boom despues de escribir")

    @app.get("/contar")
    async def contar(repo: RepoNotas = Depends(dep)) -> dict[str, int]:
        return {"n": await repo.contar()}

    return app


@pytest_asyncio.fixture
async def entorno() -> AsyncIterator[tuple[httpx.AsyncClient, Any]]:
    motor = sesion_de_prueba(Base)
    await motor.crear_esquema(Base)
    app = _app(motor)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor
    await motor.cerrar()


async def test_el_handler_recibe_el_repo_y_persiste_al_terminar_bien(entorno):
    http, _ = entorno
    assert (await http.post("/guardar", params={"texto": "hola"})).status_code == 200
    assert (await http.get("/contar")).json()["n"] == 1


async def test_una_excepcion_en_el_handler_hace_rollback(entorno):
    http, _ = entorno
    with contextlib.suppress(RuntimeError):
        await http.post("/guardar-y-fallar", params={"texto": "fantasma"})
    assert (await http.get("/contar")).json()["n"] == 0
