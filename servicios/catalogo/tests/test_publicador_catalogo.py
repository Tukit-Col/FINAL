from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_catalogo import publicador
from tukit_catalogo.modelos import Base
from tukit_catalogo.repositorios.admin import BANDEJA
from tukit_comun.publicador import vaciar


class _Destino:
    def __init__(self) -> None:
        self.publicados: list = []

    async def publicar(self, evento) -> None:
        self.publicados.append(evento)


async def test_publica_los_eventos_de_catalogo_en_orden_y_los_marca():
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with motor.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)
            for tipo, agregado in (
                ("colegio_verificado", "colegio"),
                ("lista_verificada", "version_lista_oficial"),
            ):
                await conexion.execute(
                    insert(BANDEJA).values(
                        tipo=tipo, agregado_tipo=agregado, agregado_id=uuid.uuid4(), carga={"grado": "Cuarto"}
                    )
                )
        destino = _Destino()

        assert await vaciar(motor, destino, origen="catalogo") == 2

        assert [(e.origen, e.tipo) for e in destino.publicados] == [
            ("catalogo", "colegio_verificado"),
            ("catalogo", "lista_verificada"),
        ]
        assert destino.publicados[1].carga == {"grado": "Cuarto"}
        async with motor.connect() as conexion:
            pendientes = await conexion.scalar(select(BANDEJA.c.id).where(BANDEJA.c.publicado_en.is_(None)))
        assert pendientes is None
    finally:
        await motor.dispose()


def test_sin_rabbitmq_url_no_arranca(monkeypatch, capsys):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)

    assert publicador.main([]) == 2
    assert "falta RABBITMQ_URL" in capsys.readouterr().out
