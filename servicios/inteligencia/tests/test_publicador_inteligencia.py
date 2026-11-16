"""El publicador de la bandeja de Inteligencia (ADR 0046).

El nucleo se prueba en `tukit_comun`. Aqui se fija que lee la bandeja de verdad
de Inteligencia y que `kits_publicados` lleva al acudiente en la carga: con
RabbitMQ el repartidor no lee `trabajo_pipeline`, asi que el destinatario tiene
que viajar en el evento. Y que sin `RABBITMQ_URL` no arranca.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from tukit_comun.publicador import vaciar
from tukit_inteligencia import publicador, supresion, trabajos
from tukit_inteligencia.repositorios.trabajos import RepoTrabajos

COLEGIO = "11111111-1111-1111-1111-111111111111"


class _Destino:
    def __init__(self) -> None:
        self.publicados: list = []

    async def publicar(self, evento) -> None:
        self.publicados.append(evento)


async def _trabajo(motor, usuario_id: uuid.UUID | None) -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        usuario_id=usuario_id,
    )
    return uuid.UUID(respuesta["trabajo_id"])


async def test_kits_publicados_sale_con_el_acudiente_y_su_origen(motor):
    usuario_id = uuid.uuid4()
    trabajo_id = await _trabajo(motor, usuario_id)
    async with motor.engine.begin() as conexion:
        await RepoTrabajos(conexion).emitir_evento(trabajo_id)
    destino = _Destino()

    assert await vaciar(motor.engine, destino, origen="inteligencia") == 1

    [evento] = destino.publicados
    assert (evento.origen, evento.tipo, evento.agregado_id) == ("inteligencia", "kits_publicados", trabajo_id)
    assert evento.carga["usuario_id"] == str(usuario_id)
    assert evento.carga["trabajo_id"] == str(trabajo_id)
    async with motor.engine.connect() as conexion:
        assert await conexion.scalar(select(trabajos.BANDEJA.c.publicado_en)) is not None


async def test_un_trabajo_sin_acudiente_no_inventa_destinatario(motor):
    trabajo_id = await _trabajo(motor, None)
    async with motor.engine.begin() as conexion:
        await RepoTrabajos(conexion).emitir_evento(trabajo_id)

    async with motor.engine.connect() as conexion:
        carga = await conexion.scalar(select(trabajos.BANDEJA.c.carga))
    assert "usuario_id" not in carga


@pytest.mark.parametrize("proceso", [publicador, supresion], ids=["publicador", "supresion"])
def test_sin_rabbitmq_url_no_arranca(monkeypatch, capsys, proceso):
    """Los dos procesos que solo existen sobre el broker se niegan a arrancar sin el."""
    monkeypatch.delenv("RABBITMQ_URL", raising=False)

    assert proceso.main([]) == 2
    assert "falta RABBITMQ_URL" in capsys.readouterr().out
