"""Las colas en RabbitMQ, con dobles y sin broker (ADR 0046).

Se fija aqui:

- **La topologia.** Cada consumidor tiene su cola principal, la de reintentos
  (que devuelve a la principal cuando vence su espera) y la de descartados; las
  tres clasicas y durables, y la principal atada por cada tipo que le toca.
- **El sobre.** Lo que sale de una fila de bandeja llega igual al consumidor, con
  su origen; un cuerpo que no es un sobre se reconoce.
- **El publicador.** Marca publicado solo lo que el broker confirmo; si falla a
  mitad, guarda lo confirmado y el error sube.
- **El consumidor.** Confirma tras procesar, reintenta con la cuenta en la
  cabecera, descarta al llegar al tope, devuelve sin gastar intento ante una
  caida y salta lo que ya proceso.

Las pruebas contra un RabbitMQ de verdad estan en `test_colas_rabbitmq.py`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import MetaData, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tukit_comun.bandeja import Resultado, bandeja_reflejada
from tukit_comun.consumidor import (
    Consumidor,
    Decision,
    RegistroEnMemoria,
    RegistroEnTabla,
    eventos_procesados_reflejada,
    marcar_procesado,
)
from tukit_comun.http import id_de_correlacion
from tukit_comun.mensajes import Evento, MensajeInvalido, cuerpo, evento_de, evento_de_fila
from tukit_comun.publicador import correr, main_publicador, publicar_pendientes, vaciar
from tukit_comun.topologia import (
    AVISOS,
    CABECERA_INTENTOS,
    CABECERA_MOTIVO,
    TOPOLOGIA,
    Cola,
    declarar,
)

AGREGADO = uuid.UUID("11111111-2222-3333-4444-555555555555")


# --- topologia ---------------------------------------------------------------


def test_cada_cola_tiene_reintentos_y_descartados():
    cola = Cola("operacion.avisos", ("pedido_pagado",), espera_reintento_ms=2_000)

    assert cola.reintentos == "operacion.avisos.reintentos"
    assert cola.descartados == "operacion.avisos.descartados"
    # Lo que la principal rechaza va a descartados por el exchange por omision.
    assert cola.argumentos() == {
        "x-queue-type": "classic",
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "operacion.avisos.descartados",
    }
    # Los reintentos esperan su TTL y vuelven a la principal.
    assert cola.argumentos_reintentos() == {
        "x-queue-type": "classic",
        "x-message-ttl": 2_000,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "operacion.avisos",
    }
    assert cola.argumentos_descartados() == {"x-queue-type": "classic"}


def test_la_topologia_tiene_una_cola_por_consumidor():
    assert [cola.nombre for cola in TOPOLOGIA.colas] == [
        "operacion.avisos",
        "identidad.colegios",
        "inteligencia.listas",
        "inteligencia.trabajos",
    ]
    assert TOPOLOGIA.exchange == "tukit.eventos"
    assert TOPOLOGIA.cola("inteligencia.trabajos").claves == ("trabajo_encolado",)


def test_con_prefijo_renombra_exchange_y_colas():
    prueba = TOPOLOGIA.con_prefijo("prueba-1", espera_reintento_ms=50)

    assert prueba.exchange == "prueba-1.tukit.eventos"
    avisos = prueba.cola("operacion.avisos")
    assert avisos.nombre == "prueba-1.operacion.avisos"
    assert avisos.claves == AVISOS.claves
    assert avisos.argumentos_reintentos()["x-message-ttl"] == 50
    # La topologia de verdad no cambia.
    assert TOPOLOGIA.cola("operacion.avisos").nombre == "operacion.avisos"


class _ColaFalsa:
    def __init__(self, nombre: str, canal: _CanalFalso) -> None:
        self.nombre = nombre
        self.canal = canal

    async def bind(self, exchange: Any, routing_key: str) -> None:
        self.canal.llamadas.append(("bind", self.nombre, exchange, routing_key))


class _CanalFalso:
    def __init__(self) -> None:
        self.llamadas: list[tuple[Any, ...]] = []

    async def declare_exchange(self, nombre: str, tipo: Any, *, durable: bool) -> str:
        self.llamadas.append(("exchange", nombre, str(tipo.value), durable))
        return nombre

    async def declare_queue(self, nombre: str, *, durable: bool, arguments: dict[str, Any]) -> _ColaFalsa:
        self.llamadas.append(("cola", nombre, durable, arguments))
        return _ColaFalsa(nombre, self)


async def test_declarar_crea_exchange_colas_y_bindings():
    canal = _CanalFalso()
    topologia = TOPOLOGIA.con_prefijo("p")

    exchange, colas = await declarar(canal, topologia)

    assert exchange == "p.tukit.eventos"
    assert canal.llamadas[0] == ("exchange", "p.tukit.eventos", "topic", True)
    declaradas = [llamada for llamada in canal.llamadas if llamada[0] == "cola"]
    # Tres colas por consumidor, todas durables.
    assert len(declaradas) == 3 * len(topologia.colas)
    assert all(llamada[2] is True for llamada in declaradas)
    # La principal se declara despues de su descartados y su reintentos.
    nombres = [llamada[1] for llamada in declaradas]
    assert nombres[:3] == [
        "p.operacion.avisos.descartados",
        "p.operacion.avisos.reintentos",
        "p.operacion.avisos",
    ]
    bindings = {(llamada[1], llamada[3]) for llamada in canal.llamadas if llamada[0] == "bind"}
    assert ("p.operacion.avisos", "pedido_pagado") in bindings
    assert ("p.inteligencia.trabajos", "trabajo_encolado") in bindings
    assert len(bindings) == sum(len(cola.claves) for cola in topologia.colas)
    assert set(colas) == {cola.nombre for cola in topologia.colas}


# --- el sobre ----------------------------------------------------------------


def _fila(id_: int = 7, tipo: str = "pedido_pagado", carga: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        id=id_,
        tipo=tipo,
        agregado_tipo="pedido",
        agregado_id=AGREGADO,
        carga={"pedido_id": "p1", "correlacion_id": "c-1"} if carga is None else carga,
        intentos=0,
    )


def test_el_sobre_viaja_completo():
    evento = evento_de_fila(_fila(), origen="comercio")
    llegado = evento_de(cuerpo(evento), intentos=2)

    assert llegado == Evento(
        id=7,
        origen="comercio",
        tipo="pedido_pagado",
        agregado_tipo="pedido",
        agregado_id=AGREGADO,
        carga={"pedido_id": "p1", "correlacion_id": "c-1"},
        correlacion_id="c-1",
        intentos=2,
    )
    assert llegado.message_id == "comercio:7"


def test_el_sobre_lleva_origen_id_tipo_carga_y_correlacion():
    sobre = json.loads(cuerpo(evento_de_fila(_fila(), origen="comercio")))

    assert sobre == {
        "evento_id": 7,
        "origen": "comercio",
        "tipo": "pedido_pagado",
        "agregado_tipo": "pedido",
        "agregado_id": str(AGREGADO),
        "carga": {"pedido_id": "p1", "correlacion_id": "c-1"},
        "correlacion_id": "c-1",
    }


@pytest.mark.parametrize(
    "datos",
    [
        b"no es json",
        b"\xff\xfe",
        b"[1, 2]",
        json.dumps({"origen": "comercio", "tipo": "x"}).encode(),
        json.dumps({"evento_id": 1, "tipo": "x"}).encode(),
        json.dumps({"evento_id": "uno", "origen": "comercio", "tipo": "x"}).encode(),
        json.dumps({"evento_id": 1, "origen": "comercio", "tipo": "x", "carga": [1]}).encode(),
        json.dumps({"evento_id": 1, "origen": "comercio", "tipo": "x", "agregado_id": "no-uuid"}).encode(),
    ],
)
def test_un_cuerpo_que_no_es_sobre_se_reconoce(datos):
    with pytest.raises(MensajeInvalido):
        evento_de(datos)


# --- el publicador -----------------------------------------------------------

BANDEJA = bandeja_reflejada(MetaData())


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA.metadata.create_all)
        await conexion.run_sync(eventos_procesados_reflejada(MetaData()).create)
    yield engine
    await engine.dispose()


async def _sembrar(motor: AsyncEngine, cantidad: int, *, publicados: int = 0) -> None:
    async with motor.begin() as conexion:
        for i in range(1, cantidad + 1):
            await conexion.execute(
                insert(BANDEJA).values(
                    id=i,
                    tipo="pedido_pagado",
                    agregado_tipo="pedido",
                    agregado_id=AGREGADO,
                    carga={"pedido_id": f"p{i}"},
                    intentos=0,
                    publicado_en=None if i > publicados else datetime(2000, 1, 1, tzinfo=UTC),
                )
            )


async def _pendientes(motor: AsyncEngine) -> list[int]:
    async with motor.connect() as conexion:
        filas = await conexion.execute(
            select(BANDEJA.c.id).where(BANDEJA.c.publicado_en.is_(None)).order_by(BANDEJA.c.id)
        )
        return [fila.id for fila in filas]


class _Destino:
    """Un broker falso: confirma todo, salvo la publicacion numero `falla_en`."""

    def __init__(self, *, falla_en: int | None = None, error: Exception | None = None) -> None:
        self.publicados: list[Evento] = []
        self.falla_en = falla_en
        self.error = error or ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5672)")
        self.intentos = 0
        self.cerrado = 0

    async def publicar(self, evento: Evento) -> None:
        self.intentos += 1
        if self.falla_en is not None and self.intentos == self.falla_en:
            raise self.error
        self.publicados.append(evento)

    async def cerrar(self) -> None:
        self.cerrado += 1


async def test_publica_en_orden_y_marca_lo_confirmado(motor):
    await _sembrar(motor, 3, publicados=1)
    destino = _Destino()

    publicados = await publicar_pendientes(motor, destino, origen="comercio")

    assert publicados == 2
    assert [(e.origen, e.id, e.carga["pedido_id"]) for e in destino.publicados] == [
        ("comercio", 2, "p2"),
        ("comercio", 3, "p3"),
    ]
    assert await _pendientes(motor) == []


async def test_si_la_publicacion_falla_guarda_lo_confirmado_y_el_error_sube(motor):
    await _sembrar(motor, 4)
    destino = _Destino(falla_en=3)

    with pytest.raises(ConnectionRefusedError):
        await publicar_pendientes(motor, destino, origen="comercio")

    # Los dos confirmados quedaron marcados; el que fallo y el siguiente, no.
    assert [e.id for e in destino.publicados] == [1, 2]
    assert await _pendientes(motor) == [3, 4]

    # La pasada siguiente sigue donde iba, sin repetir lo confirmado.
    await publicar_pendientes(motor, destino, origen="comercio")
    assert [e.id for e in destino.publicados] == [1, 2, 3, 4]
    assert await _pendientes(motor) == []


async def test_vaciar_sigue_hasta_que_no_quedan_pendientes(motor):
    await _sembrar(motor, 5)
    destino = _Destino()

    assert await vaciar(motor, destino, origen="catalogo", limite=2) == 5
    assert await _pendientes(motor) == []


class _Corte(Exception):
    """Para salir del bucle infinito en la prueba."""


async def test_el_bucle_cierra_la_conexion_tras_una_caida_y_sigue(motor):
    await _sembrar(motor, 2)
    destino = _Destino(falla_en=1)
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if len(esperas) >= 2:
            raise _Corte

    with pytest.raises(_Corte):
        await correr("comercio", motor, destino, seguir=True, intervalo=1.0, dormir=dormir)

    # La caida cerro la conexion y espero 1 s; la vuelta siguiente publico todo.
    assert destino.cerrado == 1
    assert esperas == [1.0, 1.0]
    assert [e.id for e in destino.publicados] == [1, 2]
    assert await _pendientes(motor) == []


async def test_un_error_que_no_es_caida_termina_el_bucle(motor):
    await _sembrar(motor, 1)
    destino = _Destino(falla_en=1, error=ValueError("bug"))

    async def dormir(segundos: float) -> None:  # pragma: no cover - no debe esperar
        raise AssertionError("no espera ante un bug")

    with pytest.raises(ValueError):
        await correr("comercio", motor, destino, seguir=True, dormir=dormir)
    assert await _pendientes(motor) == [1]


def test_sin_rabbitmq_url_el_publicador_no_arranca(monkeypatch, capsys):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)

    assert main_publicador("catalogo", []) == 2
    assert "falta RABBITMQ_URL" in capsys.readouterr().out


# --- el consumidor -----------------------------------------------------------


class _Mensaje:
    """Un mensaje entrante falso, con lo que el consumidor usa de aio-pika."""

    def __init__(self, datos: bytes, *, cabeceras: dict[str, Any] | None = None) -> None:
        self.body = datos
        self.headers = cabeceras or {}
        self.message_id = "comercio:7"
        self.acks = 0
        self.nacks: list[bool] = []

    async def ack(self) -> None:
        self.acks += 1

    async def nack(self, *, requeue: bool) -> None:
        self.nacks.append(requeue)


class _Reenvio:
    def __init__(self) -> None:
        self.enviados: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, mensaje: Any, *, cola: str, cabeceras: dict[str, Any]) -> None:
        self.enviados.append((cola, cabeceras))


def _mensaje(intentos: int | None = None, **extra: Any) -> _Mensaje:
    cabeceras = {CABECERA_INTENTOS: intentos} if intentos is not None else {}
    return _Mensaje(cuerpo(evento_de_fila(_fila(), origen="comercio")), cabeceras={**cabeceras, **extra})


def _consumidor(manejar: Any, **extra: Any) -> tuple[Consumidor, _Reenvio]:
    reenvio = _Reenvio()
    return Consumidor(cola=AVISOS, manejar=manejar, reenviar=reenvio, **extra), reenvio


async def test_hecho_confirma_y_anota_el_evento():
    vistos: list[Evento] = []

    async def manejar(evento: Evento) -> Resultado:
        vistos.append(evento)
        return Resultado.HECHO

    registro = RegistroEnMemoria()
    consumidor, reenvio = _consumidor(manejar, registro=registro)
    mensaje = _mensaje()

    assert await consumidor.procesar(mensaje) is Decision.HECHO
    assert mensaje.acks == 1
    assert reenvio.enviados == []
    assert [(e.origen, e.id, e.tipo) for e in vistos] == [("comercio", 7, "pedido_pagado")]
    assert registro.vistos == {("comercio", 7)}


async def test_omitir_tambien_confirma():
    async def manejar(evento: Evento) -> Resultado:
        return Resultado.OMITIR

    consumidor, _ = _consumidor(manejar)
    mensaje = _mensaje()

    assert await consumidor.procesar(mensaje) is Decision.OMITIDO
    assert mensaje.acks == 1


async def test_un_evento_repetido_no_se_vuelve_a_manejar():
    llamadas = 0

    async def manejar(evento: Evento) -> Resultado:
        nonlocal llamadas
        llamadas += 1
        return Resultado.HECHO

    consumidor, _ = _consumidor(manejar, registro=RegistroEnMemoria())
    primero, segundo = _mensaje(), _mensaje()

    assert await consumidor.procesar(primero) is Decision.HECHO
    assert await consumidor.procesar(segundo) is Decision.DUPLICADO
    assert llamadas == 1
    assert segundo.acks == 1


async def test_reintentar_va_a_reintentos_con_la_cuenta_en_la_cabecera():
    async def manejar(evento: Evento) -> Resultado:
        return Resultado.REINTENTAR

    registro = RegistroEnMemoria()
    consumidor, reenvio = _consumidor(manejar, registro=registro)
    mensaje = _mensaje(intentos=1, **{"x-death": [{"count": 1}], "tukit-otra": "se conserva"})

    assert await consumidor.procesar(mensaje) is Decision.REINTENTO
    assert reenvio.enviados == [
        ("operacion.avisos.reintentos", {CABECERA_INTENTOS: 2, "tukit-otra": "se conserva"})
    ]
    # Se confirma el original: la copia en reintentos es la que sigue.
    assert mensaje.acks == 1
    # Lo que no se proceso no queda anotado.
    assert registro.vistos == set()


async def test_un_error_del_manejador_tambien_reintenta():
    async def manejar(evento: Evento) -> Resultado:
        raise KeyError("usuario_id")

    consumidor, reenvio = _consumidor(manejar)

    assert await consumidor.procesar(_mensaje()) is Decision.REINTENTO
    assert reenvio.enviados == [("operacion.avisos.reintentos", {CABECERA_INTENTOS: 1})]


async def test_al_llegar_al_tope_va_a_descartados_con_su_motivo(caplog):
    async def manejar(evento: Evento) -> Resultado:
        raise KeyError("usuario_id")

    consumidor, reenvio = _consumidor(manejar, max_intentos=5)
    mensaje = _mensaje(intentos=4)

    assert await consumidor.procesar(mensaje) is Decision.DESCARTADO
    [(cola, cabeceras)] = reenvio.enviados
    assert cola == "operacion.avisos.descartados"
    assert cabeceras[CABECERA_INTENTOS] == 5
    assert cabeceras[CABECERA_MOTIVO] == "KeyError: 'usuario_id'"
    assert mensaje.acks == 1
    assert any(
        registro.levelname == "ERROR" and "descartado" in registro.message for registro in caplog.records
    )


async def test_un_cuerpo_invalido_va_directo_a_descartados():
    async def manejar(evento: Evento) -> Resultado:  # pragma: no cover - no se llama
        raise AssertionError

    consumidor, reenvio = _consumidor(manejar)
    mensaje = _Mensaje(b"no es un sobre")

    assert await consumidor.procesar(mensaje) is Decision.DESCARTADO
    [(cola, cabeceras)] = reenvio.enviados
    assert cola == "operacion.avisos.descartados"
    assert cabeceras[CABECERA_MOTIVO].startswith("mensaje invalido")


async def test_una_caida_devuelve_el_mensaje_sin_gastar_intento():
    async def manejar(evento: Evento) -> Resultado:
        raise ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)")

    consumidor, reenvio = _consumidor(manejar)
    mensaje = _mensaje(intentos=2)

    with pytest.raises(ConnectionRefusedError):
        await consumidor.procesar(mensaje)
    assert mensaje.nacks == [True]
    assert mensaje.acks == 0
    assert reenvio.enviados == []


async def test_el_manejador_ve_la_correlacion_del_evento():
    vista: list[str | None] = []

    async def manejar(evento: Evento) -> Resultado:
        vista.append(id_de_correlacion())
        return Resultado.HECHO

    consumidor, _ = _consumidor(manejar)
    await consumidor.procesar(_mensaje())

    assert vista == ["c-1"]
    assert id_de_correlacion() is None


async def test_el_registro_en_tabla_anota_una_sola_vez(motor):
    registro = RegistroEnTabla(motor)

    assert await registro.ya_procesado("catalogo", 3) is False
    await registro.marcar("catalogo", 3)
    await registro.marcar("catalogo", 3)
    assert await registro.ya_procesado("catalogo", 3) is True
    # El id es por origen: el 3 de Comercio es otro evento.
    assert await registro.ya_procesado("comercio", 3) is False

    async with motor.begin() as conexion:
        assert await marcar_procesado(conexion, "catalogo", 3) is False
        assert await marcar_procesado(conexion, "catalogo", 4) is True
