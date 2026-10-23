"""El sondeador de listas con RabbitMQ: consume `inteligencia.listas` (ADR 0046).

Con dobles y sin broker; el viaje por un RabbitMQ de verdad esta en las pruebas
de punta a punta. Lo que se fija:

- Un `lista_verificada` de la cola arma el kit del padre igual que la fila de la
  bandeja, sin abrir la base del Catalogo.
- **Un evento repetido no arma un segundo kit**, ni cuando el consumidor ve la
  marca antes de manejarlo ni cuando dos entregas llegan a `crear`: la marca
  entra en la misma transaccion que el trabajo.
- Si crear el trabajo falla, la marca vuelve atras con el y el evento se puede
  procesar de nuevo.
- Un `lista_aprobada` arma los canonicos; repetido, no vuelve a optimizar.
- Con `RABBITMQ_URL`, `main` consume la cola con el registro en
  `evento_procesado` y no sondea.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_comun.bandeja import Resultado
from tukit_comun.consumidor import Consumidor, Decision, RegistroEnTabla
from tukit_comun.mensajes import Evento, cuerpo
from tukit_inteligencia import poller as modulo
from tukit_inteligencia import trabajos
from tukit_inteligencia.modelos import EstadoTrabajo, EventoProcesado
from tukit_inteligencia.poller import Poller

VERSION = uuid.UUID("22222222-3333-4444-5555-666666666666")


def _evento(id_: int = 1, tipo: str = "lista_verificada", **carga: Any) -> Evento:
    return Evento(
        id=id_,
        origen="catalogo",
        tipo=tipo,
        agregado_tipo="version_lista_oficial",
        agregado_id=VERSION,
        carga={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026, **carga},
    )


class _Mensaje:
    def __init__(self, evento: Evento) -> None:
        self.body = cuerpo(evento)
        self.headers: dict[str, Any] = {}
        self.acks = 0

    async def ack(self) -> None:
        self.acks += 1


async def _cuantos(motor, tabla) -> int:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(select(func.count()).select_from(tabla))


def _poller(motor, catalogo=None) -> Poller:
    return Poller(motor_inteligencia=motor, motor_catalogo=None, catalogo=catalogo or _catalogo_verificado())


async def test_un_evento_de_la_cola_arma_el_kit_del_padre(motor):
    contacto = str(uuid.uuid4())

    assert await _poller(motor).manejar(_evento(contacto_referencia=contacto)) is Resultado.HECHO

    async with motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(trabajos.TRABAJO.c.usuario_id, trabajos.TRABAJO.c.estado, trabajos.TRABAJO.c.hijos)
            )
        ).one()
        avisos = await conexion.scalar(
            select(func.count()).where(trabajos.BANDEJA.c.tipo == "kits_publicados")
        )
    assert str(fila.usuario_id) == contacto
    assert fila.estado == EstadoTrabajo.PUBLICADO.value
    assert fila.hijos[0]["version_id"] == str(VERSION)
    assert avisos == 1
    assert await _cuantos(motor, EventoProcesado) == 1


async def test_un_evento_repetido_no_arma_un_segundo_kit(motor):
    consumidor = Consumidor(
        cola=modulo.LISTAS, manejar=_poller(motor).manejar, registro=RegistroEnTabla(motor.engine)
    )
    evento = _evento(5, contacto_referencia=str(uuid.uuid4()))
    primero, segundo = _Mensaje(evento), _Mensaje(evento)

    assert await consumidor.procesar(primero) is Decision.HECHO
    assert await consumidor.procesar(segundo) is Decision.DUPLICADO

    assert (primero.acks, segundo.acks) == (1, 1)
    assert await _cuantos(motor, trabajos.TRABAJO) == 1
    assert await _cuantos(motor, EventoProcesado) == 1


async def test_dos_entregas_que_llegan_a_crear_arman_un_solo_kit(motor):
    # El proceso cayo despues de crear el trabajo y antes de confirmar: la
    # segunda entrega no paso por el registro del consumidor, pero `crear` ve la
    # marca que dejo la primera en su misma transaccion.
    poller = _poller(motor)
    evento = _evento(6, contacto_referencia=str(uuid.uuid4()))

    assert await poller.manejar(evento) is Resultado.HECHO
    assert await poller.manejar(evento) is Resultado.OMITIR

    assert await _cuantos(motor, trabajos.TRABAJO) == 1


async def test_si_crear_falla_la_marca_vuelve_atras(motor, monkeypatch):
    poller = _poller(motor)
    evento = _evento(8, contacto_referencia=str(uuid.uuid4()))
    etapas = trabajos.ETAPAS
    # Una etapa sin nombre viola el NOT NULL despues de la marca y del trabajo.
    monkeypatch.setattr(trabajos, "ETAPAS", (None,))

    with pytest.raises(Exception, match="NOT NULL"):
        await poller.manejar(evento)
    assert await _cuantos(motor, EventoProcesado) == 0
    assert await _cuantos(motor, trabajos.TRABAJO) == 0

    monkeypatch.setattr(trabajos, "ETAPAS", etapas)
    assert await poller.manejar(evento) is Resultado.HECHO
    assert await _cuantos(motor, trabajos.TRABAJO) == 1


async def test_un_lista_aprobada_arma_los_canonicos_y_repetido_no_reoptimiza(motor):
    poller = _poller(motor)
    evento = _evento(9, tipo="lista_aprobada")

    assert await poller.manejar(evento) is Resultado.HECHO
    async with motor.engine.begin() as conexion:
        origen = await conexion.scalar(select(trabajos.TRABAJO.c.origen))
    assert origen == trabajos.ORIGEN_CANONICO

    catalogo = _catalogo_verificado()
    assert await _poller(motor, catalogo).manejar(evento) is Resultado.OMITIR
    assert "resueltos" not in catalogo.llamadas
    assert await _cuantos(motor, trabajos.TRABAJO) == 1


async def test_otro_tipo_se_omite(motor):
    assert await _poller(motor).manejar(_evento(10, tipo="colegio_verificado")) is Resultado.OMITIR
    assert await _cuantos(motor, trabajos.TRABAJO) == 0


async def test_sin_la_bandeja_del_catalogo_no_hay_pasada(motor):
    with pytest.raises(ValueError):
        await _poller(motor).pasada()


async def test_sin_broker_crear_no_anota_nada(motor):
    await trabajos.crear(motor, hijos=[{"referencia": "hijo-1"}], origen="colegio_grado", en_proceso=True)
    assert await _cuantos(motor, EventoProcesado) == 0


class _MotorFalso:
    engine = object()

    def __init__(self) -> None:
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


def test_con_rabbitmq_url_main_consume_la_cola_y_no_abre_el_catalogo(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@broker:5672/")
    motor_falso = _MotorFalso()
    llamadas: list[dict[str, Any]] = []

    async def consumir(url, consumidor, **opciones):
        llamadas.append({"url": url, "consumidor": consumidor, **opciones})
        return 0

    def _sin_catalogo(servicio):  # pragma: no cover - no debe llamarse
        raise AssertionError(f"abrio la base de {servicio}")

    monkeypatch.setattr(modulo, "crear_motor", lambda servicio: motor_falso)
    monkeypatch.setattr(modulo, "_motor_lectura", _sin_catalogo)
    monkeypatch.setattr(modulo, "consumir", consumir)

    assert modulo.main([]) == 0

    [llamada] = llamadas
    consumidor = llamada["consumidor"]
    assert (consumidor.cola.nombre, llamada["seguir"]) == ("inteligencia.listas", False)
    assert isinstance(consumidor.registro, RegistroEnTabla)
    assert consumidor.registro.motor is motor_falso.engine
    assert llamada["proceso"] == "inteligencia-poller"
    assert motor_falso.cerrado
