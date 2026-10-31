"""El repartidor con RabbitMQ: consume la cola `operacion.avisos` (ADR 0046).

Con dobles y sin broker; el viaje por un RabbitMQ de verdad esta en las pruebas
de punta a punta. Lo que se fija:

- **El mismo aviso.** Un evento de la cola da la notificacion que daba la fila de
  la bandeja, con el origen que trae el sobre.
- **Ninguna base ajena.** El destinatario de `kits_publicados` sale de la carga y
  no de `trabajo_pipeline`; con broker, el repartidor no abre motores de lectura.
- **Un evento, un aviso** (ADR 0042), tambien si el broker lo entrega dos veces;
  y el mismo id desde otro origen es otro evento.
- **Lo que no tiene destinatario** pide reintentar, y el consumidor lo lleva a
  descartados tras los intentos.
- **La cola recibe justo los tipos que tienen plantilla.**
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_repartidor import USUARIO, IdentidadContacto
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio
from tukit_comun.consumidor import Consumidor, Decision
from tukit_comun.mensajes import Evento, cuerpo
from tukit_comun.topologia import AVISOS
from tukit_operacion import repartidor
from tukit_operacion.dominio.reparto import _PLANTILLAS
from tukit_operacion.modelos import Base
from tukit_operacion.notificador import Envio, NotificadorFalso
from tukit_operacion.repartidor import NOTIFICACION, Repartidor

TRABAJO = uuid.UUID("33333333-3333-4333-8333-333333333333")


@pytest_asyncio.fixture
async def motor_operacion() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="operacion", engine=engine, _fabrica=fabrica)
    await engine.dispose()


def _de_la_cola(motor_operacion: MotorServicio, notificador: Any = None) -> Repartidor:
    return Repartidor(
        origen=None,
        motor_operacion=motor_operacion,
        motor_origen=None,
        notificador=notificador or NotificadorFalso(),
        identidad=IdentidadContacto(),
    )


def _kits(id_: int = 7, *, origen: str = "inteligencia", usuario: uuid.UUID | None = USUARIO) -> Evento:
    carga: dict[str, Any] = {"trabajo_id": str(TRABAJO)}
    if usuario is not None:
        carga["usuario_id"] = str(usuario)
    return Evento(
        id=id_,
        origen=origen,
        tipo="kits_publicados",
        agregado_tipo="trabajo_pipeline",
        agregado_id=TRABAJO,
        carga=carga,
    )


async def _notificaciones(motor_operacion: MotorServicio) -> list:
    async with motor_operacion.engine.connect() as conexion:
        return list(await conexion.execute(select(NOTIFICACION).order_by(NOTIFICACION.c.creado_en)))


async def test_un_evento_de_la_cola_da_el_aviso_con_el_destinatario_de_la_carga(motor_operacion):
    notificador = NotificadorFalso()
    reparto = _de_la_cola(motor_operacion, notificador)

    assert await reparto.manejar(_kits()) is Resultado.HECHO

    [fila] = await _notificaciones(motor_operacion)
    assert fila.usuario_id == USUARIO
    assert (fila.evento_origen, fila.evento_id) == ("inteligencia", 7)
    assert fila.plantilla == "kits_publicados"
    assert len(notificador.enviados) == 1


async def test_el_mismo_evento_dos_veces_da_un_solo_aviso(motor_operacion):
    notificador = NotificadorFalso()
    reparto = _de_la_cola(motor_operacion, notificador)

    assert await reparto.manejar(_kits()) is Resultado.HECHO
    # El broker lo entrega otra vez (un ack perdido, una publicacion repetida).
    assert await reparto.manejar(_kits()) is Resultado.HECHO

    assert len(await _notificaciones(motor_operacion)) == 1
    assert len(notificador.enviados) == 1


async def test_el_mismo_id_desde_otro_origen_es_otro_evento(motor_operacion):
    reparto = _de_la_cola(motor_operacion)
    pagado = Evento(
        id=7,
        origen="comercio",
        tipo="pedido_pagado",
        agregado_tipo="pedido",
        agregado_id=uuid.uuid4(),
        carga={"pedido_id": "p-1", "usuario_id": str(USUARIO)},
    )

    assert await reparto.manejar(_kits(7)) is Resultado.HECHO
    assert await reparto.manejar(pagado) is Resultado.HECHO

    filas = await _notificaciones(motor_operacion)
    assert sorted(f.evento_origen for f in filas) == ["comercio", "inteligencia"]


async def test_un_kits_publicados_sin_usuario_pide_reintentar(motor_operacion):
    notificador = NotificadorFalso()
    reparto = _de_la_cola(motor_operacion, notificador)

    assert await reparto.manejar(_kits(usuario=None)) is Resultado.REINTENTAR
    assert notificador.enviados == []
    assert await _notificaciones(motor_operacion) == []


async def test_un_envio_fallido_pide_reintentar_y_luego_sale(motor_operacion):
    class _Falla(NotificadorFalso):
        def __init__(self) -> None:
            super().__init__()
            self.fallar = True

        async def enviar(self, contacto, plantilla, datos) -> Envio:
            if self.fallar:
                self.fallar = False
                return Envio(canal="correo", exito=False)
            return await super().enviar(contacto, plantilla, datos)

    notificador = _Falla()
    reparto = _de_la_cola(motor_operacion, notificador)

    assert await reparto.manejar(_kits()) is Resultado.REINTENTAR
    assert await reparto.manejar(_kits()) is Resultado.HECHO
    assert [f.estado for f in await _notificaciones(motor_operacion)] == ["fallida", "enviada"]


async def test_un_tipo_sin_plantilla_se_omite(motor_operacion):
    reparto = _de_la_cola(motor_operacion)
    solicitado = Evento(id=1, origen="inteligencia", tipo="pedido_solicitado", carga={})

    assert await reparto.manejar(solicitado) is Resultado.OMITIR


async def test_sin_bandeja_de_origen_no_hay_pasada(motor_operacion):
    with pytest.raises(ValueError):
        await _de_la_cola(motor_operacion).pasada()


async def test_por_el_consumidor_confirma_el_mensaje(motor_operacion):
    class _Mensaje:
        headers: dict[str, Any] = {}

        def __init__(self, evento: Evento) -> None:
            self.body = cuerpo(evento)
            self.acks = 0

        async def ack(self) -> None:
            self.acks += 1

    consumidor = Consumidor(cola=AVISOS, manejar=_de_la_cola(motor_operacion).manejar)
    mensaje = _Mensaje(_kits())

    assert await consumidor.procesar(mensaje) is Decision.HECHO
    assert mensaje.acks == 1


def test_la_cola_recibe_justo_los_tipos_con_plantilla():
    assert set(AVISOS.claves) == set(_PLANTILLAS)


class _MotorFalso:
    def __init__(self) -> None:
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


def test_con_rabbitmq_url_main_consume_la_cola_y_no_abre_bases_ajenas(monkeypatch, capsys):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@broker:5672/")
    motor = _MotorFalso()
    llamadas: list[dict[str, Any]] = []

    async def consumir(url, consumidor, **opciones):
        llamadas.append({"url": url, "cola": consumidor.cola.nombre, **opciones})
        return 3

    def _sin_bases_ajenas(origen):  # pragma: no cover - no debe llamarse
        raise AssertionError(f"abrio la base de {origen}")

    monkeypatch.setattr(repartidor, "crear_motor", lambda servicio: motor)
    monkeypatch.setattr(repartidor, "_motor_lectura", _sin_bases_ajenas)
    monkeypatch.setattr(repartidor, "consumir", consumir)
    monkeypatch.setattr(repartidor, "notificador_desde_entorno", NotificadorFalso)
    monkeypatch.setattr(repartidor, "ClienteIdentidad", IdentidadContacto)

    assert repartidor.main([]) == 0

    [llamada] = llamadas
    assert llamada["url"] == "amqp://guest:guest@broker:5672/"
    assert llamada["cola"] == "operacion.avisos"
    assert llamada["seguir"] is False
    assert llamada["proceso"] == "operacion-repartidor"
    assert motor.cerrado
    assert "operacion.avisos: 3" in capsys.readouterr().out
