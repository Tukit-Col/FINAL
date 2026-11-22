from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import MetaData, insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comun.bandeja import Resultado, bandeja_reflejada
from tukit_comun.broker import sin_clave
from tukit_comun.consumidor import Consumidor, RegistroEnMemoria, escuchar
from tukit_comun.mensajes import Evento, evento_de, evento_de_fila
from tukit_comun.pruebas_colas import (
    Sonda,
    broker_disponible,
    broker_obligatorio,
    topologia_de_prueba,
    url_de_pruebas,
)
from tukit_comun.publicador import PublicadorAmqp, vaciar
from tukit_comun.topologia import CABECERA_INTENTOS, CABECERA_MOTIVO, Topologia, declarar

aio_pika = pytest.importorskip("aio_pika")

pytestmark = pytest.mark.rabbitmq

URL = url_de_pruebas()
AGREGADO = uuid.UUID("11111111-2222-3333-4444-555555555555")


@pytest_asyncio.fixture
async def sonda() -> AsyncIterator[Sonda]:
    if not await broker_disponible(URL):
        if broker_obligatorio():
            pytest.fail(f"no hay RabbitMQ en {sin_clave(URL)} y TUKIT_PRUEBAS_RABBITMQ_OBLIGATORIO lo exige")
        pytest.skip(f"no hay RabbitMQ en {sin_clave(URL)}")
    async with Sonda(URL) as sonda:
        yield sonda


@pytest_asyncio.fixture
async def topologia(sonda: Sonda) -> AsyncIterator[Topologia]:
    topologia = topologia_de_prueba()
    yield topologia
    await sonda.borrar(topologia)


def _evento(id_: int, tipo: str = "pedido_pagado", origen: str = "comercio") -> Evento:
    fila = SimpleNamespace(
        id=id_, tipo=tipo, agregado_tipo="pedido", agregado_id=AGREGADO, carga={"pedido_id": f"p{id_}"}
    )
    return evento_de_fila(fila, origen=origen)


async def _publicar(topologia: Topologia, *eventos: Evento) -> None:
    publicador = PublicadorAmqp(URL, topologia)
    try:
        for evento in eventos:
            await publicador.publicar(evento)
    finally:
        await publicador.cerrar()


async def _esperar(condicion, *, segundos: float = 10.0) -> None:
    limite = asyncio.get_running_loop().time() + segundos
    while not await condicion():
        if asyncio.get_running_loop().time() > limite:
            raise AssertionError("la condicion no se cumplio a tiempo")
        await asyncio.sleep(0.05)


async def test_la_topologia_se_declara_dos_veces_y_cada_tipo_llega_a_su_cola(topologia, sonda):
    canal = await sonda.canal()
    await declarar(canal, topologia)
    await declarar(canal, topologia)

    await _publicar(
        topologia,
        _evento(1, "pedido_pagado"),
        _evento(2, "colegio_verificado", "catalogo"),
        _evento(3, "lista_aprobada", "catalogo"),
        _evento(4, "trabajo_encolado", "inteligencia"),
        _evento(5, "pedido_solicitado", "inteligencia"),
    )

    assert await sonda.cuantos(topologia.cola("operacion.avisos").nombre) == 1
    assert await sonda.cuantos(topologia.cola("identidad.colegios").nombre) == 1
    assert await sonda.cuantos(topologia.cola("inteligencia.listas").nombre) == 1
    assert await sonda.cuantos(topologia.cola("inteligencia.trabajos").nombre) == 1


async def test_lo_que_el_publicador_marca_esta_en_la_cola(topologia, sonda):
    bandeja = bandeja_reflejada(MetaData())
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with motor.begin() as conexion:
            await conexion.run_sync(bandeja.metadata.create_all)
            for i in (1, 2, 3):
                await conexion.execute(
                    insert(bandeja).values(
                        id=i,
                        tipo="pedido_pagado",
                        agregado_tipo="pedido",
                        agregado_id=AGREGADO,
                        carga={"pedido_id": f"p{i}", "correlacion_id": f"c{i}"},
                        intentos=0,
                    )
                )
        publicador = PublicadorAmqp(URL, topologia)
        try:
            assert await vaciar(motor, publicador, origen="comercio") == 3
        finally:
            await publicador.cerrar()
        async with motor.connect() as conexion:
            pendientes = await conexion.scalar(select(bandeja.c.id).where(bandeja.c.publicado_en.is_(None)))
        assert pendientes is None
    finally:
        await motor.dispose()

    mensajes = await sonda.sacar(topologia.cola("operacion.avisos").nombre)
    assert [m.message_id for m in mensajes] == ["comercio:1", "comercio:2", "comercio:3"]
    assert [m.correlation_id for m in mensajes] == ["c1", "c2", "c3"]
    assert all(m.delivery_mode == aio_pika.DeliveryMode.PERSISTENT for m in mensajes)
    assert [evento_de(m.body).carga["pedido_id"] for m in mensajes] == ["p1", "p2", "p3"]


async def test_un_evento_que_siempre_falla_termina_en_descartados(topologia, sonda):
    cola = topologia.cola("operacion.avisos")
    intentos: list[int] = []

    async def manejar(evento: Evento) -> Resultado:
        intentos.append(evento.intentos)
        return Resultado.REINTENTAR

    consumidor = Consumidor(cola=cola, manejar=manejar, max_intentos=3)
    # El consumidor publica en descartados y DESPUES confirma el mensaje. Ver la
    # copia en descartados no basta: si se cancela antes del ack, el broker
    # devuelve el original a la cola. Se espera a que `procesar` termine.
    procesado = asyncio.Event()
    procesar = consumidor.procesar

    async def procesar_y_avisar(mensaje):
        decision = await procesar(mensaje)
        if len(intentos) >= 3:
            procesado.set()
        return decision

    consumidor.procesar = procesar_y_avisar
    escucha = asyncio.create_task(escuchar(URL, consumidor, topologia=topologia, prefetch=1))
    try:
        await _publicar(topologia, _evento(9))
        await asyncio.wait_for(procesado.wait(), timeout=10)
        await _esperar(lambda: _hay(sonda, cola.descartados))
    finally:
        escucha.cancel()
        await asyncio.gather(escucha, return_exceptions=True)

    assert intentos == [0, 1, 2]
    [descartado] = await sonda.sacar(cola.descartados)
    assert descartado.message_id == "comercio:9"
    assert descartado.headers[CABECERA_INTENTOS] == 3
    assert descartado.headers[CABECERA_MOTIVO] == "el manejador pidio reintentar"
    assert await sonda.cuantos(cola.nombre) == 0
    assert await sonda.cuantos(cola.reintentos) == 0


async def _hay(sonda: Sonda, cola: str) -> bool:
    return await sonda.cuantos(cola) > 0


async def test_un_evento_publicado_dos_veces_se_maneja_una_vez(topologia, sonda):
    cola = topologia.cola("operacion.avisos")
    manejados: list[str] = []

    async def manejar(evento: Evento) -> Resultado:
        manejados.append(evento.message_id)
        return Resultado.HECHO

    await _publicar(topologia, _evento(4), _evento(4), _evento(5))
    consumidor = Consumidor(cola=cola, manejar=manejar, registro=RegistroEnMemoria())

    assert await escuchar(URL, consumidor, topologia=topologia, hasta_vaciar=True) == 3
    assert manejados == ["comercio:4", "comercio:5"]
    assert await sonda.cuantos(cola.nombre) == 0


async def test_una_caida_en_mitad_del_manejo_devuelve_el_mensaje(topologia, sonda):
    cola = topologia.cola("operacion.avisos")
    llamadas = 0

    async def manejar(evento: Evento) -> Resultado:
        nonlocal llamadas
        llamadas += 1
        if llamadas == 1:
            raise ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)")
        return Resultado.HECHO

    await _publicar(topologia, _evento(6))
    consumidor = Consumidor(cola=cola, manejar=manejar)

    with pytest.raises(ConnectionRefusedError):
        await escuchar(URL, consumidor, topologia=topologia, hasta_vaciar=True)
    await _esperar(lambda: _hay(sonda, cola.nombre))
    assert await sonda.cuantos(cola.nombre) == 1
    assert await sonda.cuantos(cola.reintentos) == 0

    assert await escuchar(URL, consumidor, topologia=topologia, hasta_vaciar=True) == 1
    assert llamadas == 2
    assert await sonda.cuantos(cola.nombre) == 0


async def test_el_broker_informa_su_version(sonda):
    version = sonda.version
    assert version
    print(f"RabbitMQ {version!r}")
