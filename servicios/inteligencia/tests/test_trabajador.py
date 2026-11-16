"""El trabajador durable del pipeline (ADR 0024).

`lanzar` ya no arranca una `asyncio.Task` efimera: solo deja el trabajo
`encolado` (lo hace `crear`). Un trabajador drena la cola con `SELECT … FOR
UPDATE SKIP LOCKED` —el mismo mecanismo del outbox—, mueve la fila a
`procesando` y ejecuta `procesar`. Si el proceso muere a mitad, la fila sigue
`procesando`/`encolado` y otro worker (o el reinicio) la retoma; no queda
trabajo perdido, que es el gap que la ADR cierra.

Se fija aqui:

- Una pasada toma un trabajo `encolado`, lo procesa y lo deja publicado.
- `SKIP LOCKED`: dos pasadas concurrentes no procesan el mismo trabajo dos veces.
- Un trabajo que quedo `procesando` (crash a mitad) se retoma en la pasada.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Any

import pytest
from _ayudas_inteligencia import (
    COLEGIO,
    INTERVALO_BUCLE,
    CorteDelBucle,
    EngineIntermitente,
    MotorDePrueba,
    caidas_de_postgres,
    catalogo_verificado,
    dormir_que_corta,
    encolar,
)
from sqlalchemy import select, update
from tukit_comun.bandeja import Resultado
from tukit_comun.consumidor import Consumidor, Decision
from tukit_comun.mensajes import Evento, cuerpo, evento_de_fila
from tukit_inteligencia import poller, trabajador, trabajos
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.trabajos import BANDEJA, TRABAJO


async def test_una_pasada_procesa_un_encolado(motor):
    trabajo_id = await encolar(motor)
    catalogo = catalogo_verificado()

    n = await trabajador.pasada(motor, catalogo=catalogo)

    assert n == 1
    async with motor.engine.begin() as conexion:
        estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    # Sin contacto/origen, `crear` da un trabajo `colegio_grado`: la ruta rapida
    # lo deja en revision (kit canonico del grado), no publicado directo.
    assert estado == EstadoTrabajo.ESPERA_REVISION.value


async def test_sin_encolados_no_hace_nada(motor):
    assert await trabajador.pasada(motor, catalogo=catalogo_verificado()) == 0


async def test_el_claim_saca_el_trabajo_de_la_cola(motor):
    # El claim mueve la fila a `procesando` en la MISMA transaccion del SELECT,
    # asi que una segunda pasada (normal, solo mira `encolado`) ya no lo ve: es
    # lo que en Postgres el SKIP LOCKED convierte en "dos workers no lo toman a la
    # vez". Aqui se verifica el efecto observable (la fila sale de la cola) sin
    # depender del SKIP LOCKED real, que SQLite no implementa.
    await encolar(motor)
    catalogo = catalogo_verificado()

    assert await trabajador.pasada(motor, catalogo=catalogo) == 1
    assert await trabajador.pasada(motor, catalogo=catalogo) == 0  # ya no esta encolado


async def test_no_reclama_lo_que_otro_proceso_va_a_procesar(motor):
    # El poller y el preview crean el trabajo y lo procesan en el acto. Si
    # naciera `encolado`, el trabajador podria tomarlo entre el INSERT y ese
    # `procesar`, y los dos armarian los kits a la vez.
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
        en_proceso=True,
    )
    assert await trabajador.pasada(motor, catalogo=catalogo_verificado()) == 0

    estado = await trabajos.procesar(
        motor, uuid.UUID(respuesta["trabajo_id"]), catalogo=catalogo_verificado()
    )
    assert estado == EstadoTrabajo.ESPERA_REVISION.value


async def test_retoma_un_procesando_colgado(motor):
    # Simula un crash: el trabajo quedo `procesando` sin nadie ejecutandolo, y
    # hace rato (un `procesando` reciente es de alguien que lo esta armando).
    trabajo_id = await encolar(motor)
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(TRABAJO)
            .where(TRABAJO.c.id == trabajo_id)
            .values(
                estado=EstadoTrabajo.PROCESANDO.value, actualizado_en=trabajos.ahora() - timedelta(hours=1)
            )
        )

    n = await trabajador.pasada(motor, catalogo=catalogo_verificado(), retomar_colgados=True)

    assert n == 1
    async with motor.engine.begin() as conexion:
        estado = await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))
    # Sin contacto/origen, `crear` da un trabajo `colegio_grado`: la ruta rapida
    # lo deja en revision (kit canonico del grado), no publicado directo.
    assert estado == EstadoTrabajo.ESPERA_REVISION.value


async def test_no_le_roba_el_trabajo_a_quien_lo_esta_armando(motor):
    # El poller crea el canonico ya `procesando` y lo arma en su propio
    # proceso. Retomar colgados cada minuto lo tomaba tambien, los dos lo
    # armaban a la vez y uno terminaba en "no se puede pasar de fallido a
    # publicado": asi se perdio el rearmado de Octavo dos veces.
    await trabajos.crear(
        motor,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
        en_proceso=True,
    )
    assert await trabajador.pasada(motor, catalogo=catalogo_verificado(), retomar_colgados=True) == 0


# --- Con RabbitMQ: el aviso de cada trabajo llega por su cola (ADR 0046) --------------------------


URL = "amqp://guest:guest@broker:5672/"


@pytest.fixture
def con_broker(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", URL)


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
        self.real = catalogo_verificado()

    @property
    def armados(self) -> int:
        return self.real.llamadas.count("resueltos")

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


class TestElAviso:
    async def test_con_broker_crear_deja_el_aviso_en_la_misma_bandeja(self, motor, con_broker):
        trabajo_id = await encolar(motor)

        [aviso] = await _avisos(motor)
        assert aviso.agregado_id == trabajo_id
        assert aviso.carga["trabajo_id"] == str(trabajo_id)

    async def test_un_trabajo_que_nace_procesando_no_deja_aviso(self, motor, con_broker):
        await trabajos.crear(motor, hijos=[{"referencia": "h1"}], preferencias={}, en_proceso=True)
        assert await _avisos(motor) == []

    async def test_sin_broker_no_hay_aviso(self, motor):
        trabajo_id = await encolar(motor)
        await _pasar_a(motor, trabajo_id, EstadoTrabajo.FALLIDO.value)
        await trabajos.lanzar(motor, trabajo_id)
        assert await _avisos(motor) == []

    async def test_lanzar_un_fallido_deja_otro_aviso_y_un_encolado_no(self, motor, con_broker):
        trabajo_id = await encolar(motor)
        await trabajos.lanzar(motor, trabajo_id)  # ya encolado: el aviso es el de crear
        assert len(await _avisos(motor)) == 1

        await _pasar_a(motor, trabajo_id, EstadoTrabajo.FALLIDO.value)
        await trabajos.lanzar(motor, trabajo_id)  # reintentar

        assert len(await _avisos(motor)) == 2
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ENCOLADO.value


class TestElTrabajadorAtiendeElAviso:
    async def test_un_aviso_procesa_su_trabajo(self, motor, con_broker):
        trabajo_id = await encolar(motor)
        [aviso] = await _avisos(motor)
        resultado = await trabajador.atender_aviso(motor, aviso, catalogo=catalogo_verificado())

        assert resultado is Resultado.HECHO
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ESPERA_REVISION.value

    async def test_un_aviso_que_llega_dos_veces_procesa_una_vez(self, motor, con_broker):
        trabajo_id = await encolar(motor)
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
        trabajo_id = await encolar(motor)
        catalogo = catalogo_verificado()

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
        trabajo_id = await encolar(motor)
        await _pasar_a(motor, trabajo_id, EstadoTrabajo.PROCESANDO.value, hace=timedelta(hours=1))

        assert await trabajador.barrer(motor, catalogo=catalogo_verificado()) == 1
        assert await _estado(motor, trabajo_id) == EstadoTrabajo.ESPERA_REVISION.value

    async def test_una_cancelacion_antes_de_procesar_no_se_procesa(self, motor, con_broker):
        trabajo_id = await encolar(motor)
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
    monkeypatch.setattr(trabajador, "correr_en_bucle", bucle)

    assert trabajador.main(["--seguir"]) == 0
    assert sorted(corrieron) == ["barrido", "cola"]
    assert motor_falso.cerrado


# --- Los dos procesos de fondo vuelven solos tras una caida de Postgres (H-B-02, ADR 0041) --------


class TestElTrabajadorVuelve:
    async def test_tras_una_caida_de_postgres_procesa_el_trabajo(self, motor):
        trabajo_id = await encolar(motor)
        # El trabajador abre su motor una sola vez: el mismo engine falla tres
        # veces y despues responde, como un pool con `pool_pre_ping` que reconecta.
        intermitente = MotorDePrueba(motor, EngineIntermitente(motor.engine, *caidas_de_postgres()))
        esperas: list[float] = []

        with pytest.raises(CorteDelBucle):
            await trabajador.correr_en_bucle(
                INTERVALO_BUCLE,
                dormir=dormir_que_corta(esperas),
                motor=intermitente,
                catalogo=catalogo_verificado(),
            )

        assert esperas == [1.0, 2.0, 4.0, INTERVALO_BUCLE]
        async with motor.engine.begin() as conexion:
            estado = await conexion.scalar(
                select(trabajos.TRABAJO.c.estado).where(trabajos.TRABAJO.c.id == trabajo_id)
            )
        assert estado == EstadoTrabajo.ESPERA_REVISION.value

    async def test_un_error_de_programacion_lo_sigue_terminando(self, motor):
        intermitente = MotorDePrueba(motor, EngineIntermitente(motor.engine, ValueError("bug")))
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await trabajador.correr_en_bucle(
                INTERVALO_BUCLE,
                dormir=dormir_que_corta(esperas),
                motor=intermitente,
                catalogo=catalogo_verificado(),
            )

        assert esperas == []


async def _nada(*_a, **_kw) -> int:
    return 0


@pytest.mark.parametrize(
    ("modulo", "titulo"),
    [(poller, "inteligencia-poller"), (trabajador, "inteligencia-trabajador")],
    ids=["poller", "trabajador"],
)
def test_configura_el_log_al_arrancar(monkeypatch, modulo, titulo):
    titulos: list[str] = []
    monkeypatch.setattr(modulo, "configurar_registro", titulos.append)
    monkeypatch.setattr(modulo, "correr_una_vez", _nada)

    assert modulo.main([]) == 0
    assert titulos == [titulo]


@pytest.mark.parametrize("modulo", [poller, trabajador], ids=["poller", "trabajador"])
async def test_el_bucle_duerme_con_el_asyncio_sleep_de_cuando_corre(motor, monkeypatch, modulo):
    """Sin `dormir`, el bucle usa el `asyncio.sleep` que hay al correr, no el de
    cuando se definio: es lo que deja a una prueba sustituir el sueno."""
    vueltas: list[int] = []

    async def _una_vuelta(*_a, **_kw) -> int:
        # Si el bucle durmiera con el `asyncio.sleep` de verdad, la segunda vuelta corta.
        vueltas.append(1)
        if len(vueltas) > 1:
            raise CorteDelBucle
        return 0

    esperas: list[float] = []
    if modulo is poller:
        monkeypatch.setattr(poller, "correr_una_vez", _una_vuelta)
        dependencias: dict[str, Any] = {}
    else:
        monkeypatch.setattr(trabajador, "pasada", _una_vuelta)
        dependencias = {"motor": motor, "catalogo": catalogo_verificado()}
    monkeypatch.setattr(asyncio, "sleep", dormir_que_corta(esperas))

    with pytest.raises(CorteDelBucle):
        await modulo.correr_en_bucle(INTERVALO_BUCLE, **dependencias)

    assert esperas == [INTERVALO_BUCLE]
