"""El trabajador con RabbitMQ: el aviso de cada trabajo llega por su cola (ADR 0046).

`trabajo_pipeline` sigue siendo la cola. Lo que cambia con broker es como se
entera el trabajador de que hay algo: `crear` y `lanzar` dejan `trabajo_encolado`
en la bandeja, en la misma transaccion, y el trabajador reclama la fila del
aviso. Con dobles y sin broker. Se fija:

- Con broker, un trabajo que nace o vuelve a `encolado` deja su aviso; uno que
  nace `procesando` no, y sin broker nunca.
- **Un aviso que llega dos veces** procesa el trabajo una vez.
- **Un aviso perdido lo recoge el barrido**, pasado `_AVISO_PERDIDO`; uno
  reciente se deja a su aviso.
- **Una cancelacion antes de procesar**: el aviso llega, no reclama nada y el
  trabajo sigue cancelado.
- Con `RABBITMQ_URL`, `main` consume `inteligencia.trabajos`.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_comun.bandeja import Resultado
from tukit_comun.consumidor import Consumidor, Decision
from tukit_comun.mensajes import Evento, cuerpo, evento_de_fila
from tukit_inteligencia import trabajador, trabajos
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.trabajos import BANDEJA, TRABAJO

URL = "amqp://guest:guest@broker:5672/"


@pytest.fixture
def con_broker(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", URL)


async def _encolar(motor) -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
    )
    return uuid.UUID(respuesta["trabajo_id"])


async def _avisos(motor) -> list[Evento]:
    async with motor.engine.begin() as conexion:
        filas = list(
            await conexion.execute(
                select(BANDEJA).where(BANDEJA.c.tipo == "trabajo_encolado").order_by(BANDEJA.c.id)
            )
        )
    return [evento_de_fila(fila, origen="inteligencia") for fila in filas]


async def _estado(motor, trabajo_id: uuid.UUID) -> str:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))


async def _pasar_a(motor, trabajo_id: uuid.UUID, estado: str, *, hace: timedelta | None = None) -> None:
    valores: dict[str, Any] = {"estado": estado}
    if estado == EstadoTrabajo.FALLIDO.value:
        valores["error"] = "fallo_de_prueba"
    if hace is not None:
        valores["actualizado_en"] = trabajos.ahora() - hace
    async with motor.engine.begin() as conexion:
        await conexion.execute(update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(**valores))


class _Catalogo:
    """El catalogo verificado, contando cuantas veces se armo un kit."""

    def __init__(self) -> None:
        self.real = _catalogo_verificado()

    @property
    def armados(self) -> int:
        return self.real.llamadas.count("resueltos")

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


class TestElAviso:
    async def test_con_broker_crear_deja_el_aviso_en_la_misma_bandeja(self, motor, con_broker):
        trabajo_id = await _encolar(motor)

        [aviso] = await _avisos(motor)
        assert aviso.agregado_id == trabajo_id
        assert aviso.carga["trabajo_id"] == str(trabajo_id)

    async def test_un_trabajo_que_nace_procesando_no_deja_aviso(self, motor, con_broker):
        await trabajos.crear(motor, hijos=[{"referencia": "h1"}], preferencias={}, en_proceso=True)
        assert await _avisos(motor) == []

    async def test_sin_broker_no_hay_aviso(self, motor):
        trabajo_id = await _encolar(motor)
        await _pasar_a(motor, trabajo_id, EstadoTrabajo.FALLIDO.value)
        await trabajos.lanzar(motor, trabajo_id)
        assert await _avisos(motor) == []

    async def test_lanzar_un_fallido_deja_otro_aviso_y_un_encolado_no(self, motor, con_broker):
        trabajo_id = await _encolar(motor)
        await trabajos.lanzar(motor, trabajo_id)  # ya encolado: el aviso es el de crear
        assert len(await _avisos(motor)) == 1

        await _pasar_a(motor, trabajo_id, EstadoTrabajo.FALLIDO.value)
        await trabajos.lanzar(motor, trabajo_id)  # reintentar

        assert len(await _avisos(motor)) == 2
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ENCOLADO.value


class TestElTrabajadorAtiendeElAviso:
    async def test_un_aviso_procesa_su_trabajo(self, motor, con_broker):
        trabajo_id = await _encolar(motor)
        [aviso] = await _avisos(motor)
        resultado = await trabajador.atender_aviso(motor, aviso, catalogo=_catalogo_verificado())

        assert resultado is Resultado.HECHO
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ESPERA_REVISION.value

    async def test_un_aviso_que_llega_dos_veces_procesa_una_vez(self, motor, con_broker):
        trabajo_id = await _encolar(motor)
        [aviso] = await _avisos(motor)
        catalogo = _Catalogo()
        consumidor = Consumidor(
            cola=trabajador.TRABAJOS,
            manejar=lambda evento: trabajador.atender_aviso(motor, evento, catalogo=catalogo),
        )

        class _Mensaje:
            def __init__(self) -> None:
                self.body = cuerpo(aviso)
                self.headers: dict[str, Any] = {}
                self.acks = 0

            async def ack(self) -> None:
                self.acks += 1

        primero, segundo = _Mensaje(), _Mensaje()
        assert await consumidor.procesar(primero) is Decision.HECHO
        assert await consumidor.procesar(segundo) is Decision.OMITIDO

        assert (primero.acks, segundo.acks) == (1, 1)
        assert catalogo.armados == 1
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ESPERA_REVISION.value

    async def test_un_aviso_perdido_lo_recoge_el_barrido(self, motor, con_broker):
        # El aviso quedo en la bandeja y nunca llego: el publicador no corria o
        # el mensaje se perdio. Pasado `_AVISO_PERDIDO`, el barrido toma el trabajo.
        trabajo_id = await _encolar(motor)
        catalogo = _catalogo_verificado()

        assert await trabajador.barrer(motor, catalogo=catalogo) == 0  # reciente: es del aviso
        await _pasar_a(
            motor,
            trabajo_id,
            EstadoTrabajo.ENCOLADO.value,
            hace=trabajador._AVISO_PERDIDO + timedelta(seconds=5),
        )
        assert await trabajador.barrer(motor, catalogo=catalogo) == 1
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ESPERA_REVISION.value

        # Si el aviso llega tarde, ya no hay nada que reclamar.
        [aviso] = await _avisos(motor)
        assert await trabajador.atender_aviso(motor, aviso, catalogo=catalogo) is Resultado.OMITIR

    async def test_el_barrido_retoma_los_colgados(self, motor, con_broker):
        trabajo_id = await _encolar(motor)
        await _pasar_a(motor, trabajo_id, EstadoTrabajo.PROCESANDO.value, hace=timedelta(hours=1))

        assert await trabajador.barrer(motor, catalogo=_catalogo_verificado()) == 1
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ESPERA_REVISION.value

    async def test_una_cancelacion_antes_de_procesar_no_se_procesa(self, motor, con_broker):
        trabajo_id = await _encolar(motor)
        [aviso] = await _avisos(motor)
        async with motor.engine.begin() as conexion:
            await trabajos._pasar_a(conexion, trabajo_id, EstadoTrabajo.CANCELADO.value)
        catalogo = _Catalogo()

        assert await trabajador.atender_aviso(motor, aviso, catalogo=catalogo) is Resultado.OMITIR
        assert catalogo.armados == 0
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.CANCELADO.value

    async def test_un_aviso_sin_trabajo_legible_se_omite(self, motor):
        aviso = Evento(id=1, origen="inteligencia", tipo="trabajo_encolado", carga={"trabajo_id": "x"})
        assert await trabajador.atender_aviso(motor, aviso) is Resultado.OMITIR


class _MotorFalso:
    def __init__(self) -> None:
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


def test_con_rabbitmq_url_main_atiende_la_cola_y_barre(monkeypatch, con_broker):
    motor_falso = _MotorFalso()
    llamadas: list[dict[str, Any]] = []

    async def consumir(url, consumidor, **opciones):
        llamadas.append({"url": url, "cola": consumidor.cola.nombre, **opciones})
        return 2

    async def barrer(motor, *, catalogo=None):
        assert motor is motor_falso
        return 1

    monkeypatch.setattr("tukit_comun.bd.crear_motor", lambda servicio: motor_falso)
    monkeypatch.setattr(trabajador, "consumir", consumir)
    monkeypatch.setattr(trabajador, "barrer", barrer)
    monkeypatch.setattr(trabajador, "correr_una_vez", None)  # sin broker; no debe llamarse

    assert trabajador.main([]) == 0

    [llamada] = llamadas
    assert (llamada["url"], llamada["cola"], llamada["seguir"]) == (URL, "inteligencia.trabajos", False)
    assert llamada["prefetch"] == 1
    assert motor_falso.cerrado


def test_con_seguir_escucha_la_cola_y_barre_a_la_vez(monkeypatch, con_broker):
    motor_falso = _MotorFalso()
    corrieron: list[str] = []

    async def consumir(url, consumidor, **opciones):
        assert opciones["seguir"] is True
        corrieron.append("cola")
        return 0

    async def bucle(intervalo, *, dormir=None, con_avisos=False):
        assert con_avisos is True
        corrieron.append("barrido")

    monkeypatch.setattr("tukit_comun.bd.crear_motor", lambda servicio: motor_falso)
    monkeypatch.setattr(trabajador, "consumir", consumir)
    monkeypatch.setattr(trabajador, "_bucle", bucle)

    assert trabajador.main(["--seguir"]) == 0
    assert sorted(corrieron) == ["barrido", "cola"]
    assert motor_falso.cerrado
