"""El sondeador de colegios con RabbitMQ: consume `identidad.colegios` (ADR 0046).

Con dobles y sin broker; el viaje por un RabbitMQ de verdad esta en las pruebas
de punta a punta. Lo que se fija:

- Un `colegio_verificado` de la cola da de alta el colegio igual que la fila de
  la bandeja, sin abrir la base del Catalogo.
- **Un evento repetido deja la base igual**: un colegio, una sede, un estudiante,
  una matricula y un vinculo. Por eso este consumidor no guarda que eventos
  proceso.
- Con `RABBITMQ_URL`, `main` consume la cola y no sondea.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio
from tukit_comun.consumidor import Consumidor, Decision
from tukit_comun.mensajes import Evento, cuerpo
from tukit_identidad import poller as modulo
from tukit_identidad.modelos import Base, Colegio, Sede
from tukit_identidad.poller import Poller

from .test_poller import COLEGIO, USUARIO_ID, _carga, _contar, _sembrar_usuario


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    """Solo la base propia de Identidad: con broker no hay motor del Catalogo."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="identidad", engine=engine, _fabrica=fabrica)
    await engine.dispose()


def _evento(id_: int = 1, **extra: Any) -> Evento:
    return Evento(
        id=id_,
        origen="catalogo",
        tipo="colegio_verificado",
        agregado_tipo="colegio",
        agregado_id=uuid.UUID(COLEGIO),
        carga=_carga(contacto_referencia=USUARIO_ID, **extra),
    )


async def _cuantos(motor, modelo) -> int:
    async with motor.sesion() as db:
        return await db.scalar(select(func.count()).select_from(modelo))


async def test_un_evento_de_la_cola_da_de_alta_el_colegio(motor):
    await _sembrar_usuario(motor)
    poller = Poller(motor_identidad=motor, motor_catalogo=None)

    assert await poller.manejar(_evento()) is Resultado.HECHO

    async with motor.sesion() as db:
        colegio = (await db.execute(select(Colegio))).scalar_one()
    assert str(colegio.id) == COLEGIO
    assert colegio.nombre == "ACADEMIA CENTRAL DE SISTEMAS"
    assert await _contar(motor) == (1, 1, 1)


async def test_un_evento_repetido_deja_la_base_igual(motor):
    await _sembrar_usuario(motor)
    poller = Poller(motor_identidad=motor, motor_catalogo=None)
    consumidor = Consumidor(cola=modulo.COLEGIOS, manejar=poller.manejar)

    class _Mensaje:
        headers: dict[str, Any] = {}

        def __init__(self) -> None:
            self.body = cuerpo(_evento(7))
            self.acks = 0

        async def ack(self) -> None:
            self.acks += 1

    primero, segundo = _Mensaje(), _Mensaje()
    assert await consumidor.procesar(primero) is Decision.HECHO
    assert await consumidor.procesar(segundo) is Decision.HECHO

    assert (primero.acks, segundo.acks) == (1, 1)
    assert await _cuantos(motor, Colegio) == 1
    assert await _cuantos(motor, Sede) == 1
    assert await _contar(motor) == (1, 1, 1)


async def test_otro_tipo_se_omite(motor):
    poller = Poller(motor_identidad=motor, motor_catalogo=None)
    lista = Evento(id=2, origen="catalogo", tipo="lista_verificada", carga=_carga())

    assert await poller.manejar(lista) is Resultado.OMITIR
    assert await _cuantos(motor, Colegio) == 0


async def test_sin_la_bandeja_del_catalogo_no_hay_pasada(motor):
    with pytest.raises(ValueError):
        await Poller(motor_identidad=motor, motor_catalogo=None).pasada()


class _MotorFalso:
    def __init__(self) -> None:
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


def test_con_rabbitmq_url_main_consume_la_cola_y_no_abre_el_catalogo(monkeypatch, capsys):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@broker:5672/")
    motor_falso = _MotorFalso()
    llamadas: list[dict[str, Any]] = []

    async def consumir(url, consumidor, **opciones):
        llamadas.append({"url": url, "cola": consumidor.cola.nombre, **opciones})
        return 2

    def _sin_catalogo(servicio):  # pragma: no cover - no debe llamarse
        raise AssertionError(f"abrio la base de {servicio}")

    monkeypatch.setattr(modulo, "crear_motor", lambda servicio: motor_falso)
    monkeypatch.setattr(modulo, "_motor_lectura", _sin_catalogo)
    monkeypatch.setattr(modulo, "consumir", consumir)

    assert modulo.main(["--seguir", "--intervalo", "2"]) == 0

    [llamada] = llamadas
    assert (llamada["cola"], llamada["seguir"], llamada["intervalo"]) == ("identidad.colegios", True, 2.0)
    assert llamada["proceso"] == "identidad-poller"
    assert motor_falso.cerrado
