"""Fase 6 de QA, NFR-DIS-05: los patrones de resiliencia de `tukit_comun` (ADR 0020).

`test_comun_resiliencia_disyuntor.py` fija el disyuntor llamada a llamada: abre
tras el umbral, rechaza sin tocar el destino, cruza el TTL con el reloj
inyectado y se cierra con un exito. Aqui se prueba lo que solo aparece con
varias llamadas a la vez o con sockets de verdad:

- **Medio abierto.** El docstring del disyuntor promete que, pasado el TTL,
  «deja pasar UNA prueba». Con diez llamadas simultaneas se cuenta cuantas
  llegan al destino (H-A-54).
- **Backoff.** `reintentar_get` insiste ante los errores de transporte que un
  destino caido produce de verdad (timeout, conexion rechazada, 5xx), con
  esperas de 0,2 y 0,4 s: el tope de 2 s nunca se alcanza con tres intentos.
- **Bulkhead.** `crear_pool` acota las conexiones a un destino (20). Con un
  destino colgado de verdad en 127.0.0.1, sus peticiones ocupan como mucho esos
  20 sockets y las de otro destino, con su propio pool, siguen saliendo.
- **Degradacion honesta.** Sin broker ni collector la app arranca y responde.
  Lo que falta es que diga que los apago (H-A-58).

Ningun sleep real: el reloj del disyuntor es falso y las esperas de tenacity se
anotan. Los dos servidores del bulkhead escuchan en 127.0.0.1, en un puerto que
elige el sistema; nada sale de la maquina.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from tukit_comun import resiliencia
from tukit_comun.broker import sink_desde_entorno
from tukit_comun.http import crear_app, crear_pool
from tukit_comun.resiliencia import CircuitoAbierto, Disyuntor, reintentar_get

pytestmark = pytest.mark.nfr("NFR-DIS-05")


class Reloj:
    """Reloj falso: el tiempo solo avanza cuando la prueba lo dice."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture(autouse=True)
def _registro_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resiliencia, "_disyuntores", {})


async def _abrir(disyuntor: Disyuntor) -> None:
    for _ in range(disyuntor.umbral):
        with pytest.raises(ConnectionError):
            async with disyuntor:
                raise ConnectionError("destino caido")
    assert disyuntor.abierto is True


class TestElMedioAbiertoDejaPasarUnaSolaPrueba:
    async def test_en_el_ttl_la_primera_llamada_prueba_y_si_falla_la_siguiente_no_toca(self, record_property):
        """El control en serie: la prueba es una, y si falla el circuito vuelve a rechazar."""
        reloj = Reloj()
        disyuntor = Disyuntor("catalogo", reloj=reloj)
        await _abrir(disyuntor)
        reloj.t = disyuntor.ttl
        toques = 0

        for _ in range(2):
            try:
                async with disyuntor:
                    toques += 1
                    raise ConnectionError("sigue caido")
            except (ConnectionError, CircuitoAbierto):
                pass

        record_property("toques_en_serie_tras_el_ttl", toques)
        assert toques == 1

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-54: el medio abierto no bloquea a los demas llamadores; pasado el TTL, "
        "diez llamadas simultaneas tocan el destino diez veces, no una",
    )
    async def test_diez_llamadas_a_la_vez_tras_el_ttl_tocan_el_destino_una_sola_vez(self, record_property):
        reloj = Reloj()
        disyuntor = Disyuntor("catalogo", reloj=reloj)
        await _abrir(disyuntor)
        reloj.t = disyuntor.ttl
        toques = 0
        respuesta_del_destino = asyncio.Event()

        async def llamada() -> None:
            nonlocal toques
            async with disyuntor:
                toques += 1
                await respuesta_del_destino.wait()
                raise ConnectionError("sigue caido")

        tareas = [asyncio.create_task(llamada()) for _ in range(10)]
        for _ in range(5):  # que cada tarea llegue hasta el destino o hasta el rechazo
            await asyncio.sleep(0)
        en_vuelo = toques
        respuesta_del_destino.set()
        resultados = await asyncio.gather(*tareas, return_exceptions=True)

        record_property("llamadas_simultaneas", len(tareas))
        record_property("toques_en_medio_abierto", en_vuelo)
        record_property("rechazadas_sin_tocar", sum(isinstance(r, CircuitoAbierto) for r in resultados))
        assert en_vuelo == 1, f"{en_vuelo} de {len(tareas)} llamadas llegaron al destino en medio abierto"


class TestElBackoffInsisteAnteFallosDeTransporte:
    @pytest.mark.parametrize(
        "fallo",
        [
            httpx.ReadTimeout("no contesto"),
            httpx.ConnectError("conexion rechazada"),
            httpx.HTTPStatusError(
                "503",
                request=httpx.Request("GET", "http://destino.prueba/x"),
                response=httpx.Response(503, request=httpx.Request("GET", "http://destino.prueba/x")),
            ),
        ],
        ids=["timeout", "conexion-rechazada", "5xx"],
    )
    async def test_tres_intentos_con_esperas_de_0_2_y_0_4_segundos(self, fallo, record_property):
        intentos = 0

        @reintentar_get
        async def lectura() -> None:
            nonlocal intentos
            intentos += 1
            raise fallo

        esperas: list[float] = []

        async def dormir(segundos: float) -> None:
            esperas.append(segundos)

        lectura.retry.sleep = dormir
        with pytest.raises(type(fallo)):
            await lectura()

        record_property("intentos", intentos)
        record_property("esperas_s", " ".join(f"{e:g}" for e in esperas))
        assert intentos == 3
        assert esperas == pytest.approx([0.2, 0.4])
        assert max(esperas) < 2.0  # el tope de `wait_exponential(max=2.0)` no llega a usarse


class Servidor:
    """Un destino HTTP/1.1 de verdad en 127.0.0.1 que cuenta sus conexiones abiertas a la vez."""

    def __init__(self, *, colgado: bool) -> None:
        self.colgado = colgado
        self.soltar = asyncio.Event()
        self.abiertas = 0
        self.max_abiertas = 0
        self.atendidas = 0
        self._servidor: asyncio.base_events.Server | None = None

    async def __aenter__(self) -> Servidor:
        self._servidor = await asyncio.start_server(self._atender, "127.0.0.1", 0)
        return self

    async def __aexit__(self, *_: object) -> None:
        self.soltar.set()
        assert self._servidor is not None
        self._servidor.close()
        await self._servidor.wait_closed()

    @property
    def url(self) -> str:
        assert self._servidor is not None
        return f"http://127.0.0.1:{self._servidor.sockets[0].getsockname()[1]}/"

    async def _atender(self, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        self.abiertas += 1
        self.max_abiertas = max(self.max_abiertas, self.abiertas)
        try:
            while True:
                await lector.readuntil(b"\r\n\r\n")
                if self.colgado:
                    await self.soltar.wait()
                self.atendidas += 1
                escritor.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
                )
                await escritor.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self.abiertas -= 1
            escritor.close()


class TestElBulkheadDeCrearPool:
    async def test_un_destino_colgado_no_pasa_de_sus_veinte_conexiones_ni_frena_a_otro(self, record_property):
        async with Servidor(colgado=True) as catalogo, Servidor(colgado=False) as identidad:
            pool_catalogo = crear_pool(espera=60.0)
            pool_identidad = crear_pool(espera=60.0)
            try:
                colgadas = [asyncio.create_task(pool_catalogo.get(catalogo.url)) for _ in range(30)]
                for _ in range(200):
                    if catalogo.abiertas >= 20:
                        break
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.05)  # una conexion de mas tendria tiempo de abrirse

                respuestas = await asyncio.wait_for(
                    asyncio.gather(*(pool_identidad.get(identidad.url) for _ in range(10))), timeout=5.0
                )
                en_vuelo_catalogo = catalogo.max_abiertas
                pendientes = sum(not t.done() for t in colgadas)

                catalogo.soltar.set()
                atendidas_al_final = await asyncio.wait_for(asyncio.gather(*colgadas), timeout=5.0)
            finally:
                await pool_catalogo.aclose()
                await pool_identidad.aclose()

        record_property("peticiones_al_destino_colgado", 30)
        record_property("conexiones_al_destino_colgado", en_vuelo_catalogo)
        record_property("pendientes_del_destino_colgado", pendientes)
        record_property("respuestas_del_otro_destino", sum(r.status_code == 200 for r in respuestas))
        assert en_vuelo_catalogo == 20
        assert pendientes == 30
        assert [r.status_code for r in respuestas] == [200] * 10
        assert [r.status_code for r in atendidas_al_final] == [200] * 30


@pytest.fixture
def _sin_broker_ni_collector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)


def _dicho(caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str], *palabras: str) -> list[str]:
    """Lo que el arranque dejo en el registro o en la consola y nombra alguna de las palabras."""
    salida = capsys.readouterr()
    lineas = [r.getMessage() for r in caplog.records] + (salida.out + salida.err).splitlines()
    return [linea for linea in lineas if any(p.lower() in linea.lower() for p in palabras)]


@pytest.mark.usefixtures("_sin_broker_ni_collector")
class TestLaDegradacionHonesta:
    async def test_sin_broker_ni_collector_la_app_arranca_y_responde(self):
        app = crear_app(titulo="Servicio ficticio QA", descripcion="Fase 6 de QA")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            vivo = await http.get("/health/live")
            listo = await http.get("/health/ready")

        assert sink_desde_entorno() is None
        assert vivo.status_code == 200
        assert listo.json() == {"estado": "listo", "servicio": "Servicio ficticio QA"}

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-58: sin OTEL_EXPORTER_OTLP_ENDPOINT la app arranca sin trazas ni metricas y no lo "
        "dice en el registro ni en la consola",
    )
    def test_al_arrancar_sin_collector_dice_que_no_hay_trazas(self, caplog, capsys, record_property):
        with caplog.at_level(logging.DEBUG):
            crear_app(titulo="Servicio ficticio QA", descripcion="Fase 6 de QA")

        dicho = _dicho(caplog, capsys, "OTEL", "traza", "telemetr", "collector")
        record_property("lineas_sobre_trazas", len(dicho))
        assert dicho, "el arranque no dice que las trazas quedaron apagadas"

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-58: sin RABBITMQ_URL el sink del broker es None y nadie dice que el fan-out "
        "a RabbitMQ quedo apagado",
    )
    def test_sin_url_del_broker_dice_que_no_hay_fan_out(self, caplog, capsys, record_property):
        with caplog.at_level(logging.DEBUG):
            sink = sink_desde_entorno()

        dicho = _dicho(caplog, capsys, "RABBITMQ", "broker")
        record_property("lineas_sobre_el_broker", len(dicho))
        assert sink is None
        assert dicho, "nadie dice que los eventos no salen a RabbitMQ"
