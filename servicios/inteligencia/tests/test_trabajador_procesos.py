"""NFR-MAN-01: El trabajador durable: reclamo acotado, metrica de dominio, bucle y linea de comandos.

`test_trabajador.py` fija el corazon del ADR 0024 (una pasada toma un `encolado`,
lo procesa, no lo toma dos veces, retoma un `procesando` colgado). Aqui se fijan
los bordes que lo vuelven operable y que alli no se miran:

- el `limite` de la pasada acota el reclamo: lo que no cabe sigue `encolado`;
- sin `retomar_colgados` un `procesando` NO se toca (podria ser el trabajo vivo
  de otro worker); con el, se retoma;
- la metrica de trabajos publicados cuenta solo lo que termino bien, y el
  fallo de un trabajo no tumba la pasada ni se cuenta como exito;
- `correr_una_vez` y el bucle abren el motor propio, retoman colgados (el bucle
  cada 12 vueltas) y SIEMPRE lo cierran, incluso si la pasada revienta;
- la linea de comandos elige entre una pasada y el bucle, con su intervalo.

Ni la base ni el catalogo son reales: el motor es el SQLite de la fixture
(`crear_motor` se sustituye por un prestamo que anota el cierre), el catalogo
un doble en memoria y el `asyncio.sleep` del bucle se sustituye por uno que
corta a la vuelta que la prueba decide. Ninguna prueba duerme.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Any

import pytest
from conftest import CatalogoFalso
from sqlalchemy import select, update
from test_fastroute import COLEGIO, _catalogo_verificado
from tukit_comun import bd
from tukit_inteligencia import trabajador, trabajos
from tukit_inteligencia.modelos import EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido
from tukit_inteligencia.trabajos import TRABAJO

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class MotorPrestado:
    """El motor SQLite de la fixture, con `cerrar` anotado en vez de ejecutado.

    `correr_una_vez` y el bucle crean su propio motor y lo cierran al terminar;
    si cerraran el de la fixture se perderia la base en memoria antes de que la
    prueba pueda leer el resultado. El resto de la API se delega al motor real.
    """

    def __init__(self, motor: Any) -> None:
        self._motor = motor
        self.cierres = 0

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._motor, nombre)

    async def cerrar(self) -> None:
        self.cierres += 1


class _Basta(Exception):  # noqa: N818  (senal de prueba para romper un bucle infinito)
    """Corta el bucle `while True` del trabajador cuando la prueba ya vio lo que queria."""


async def _encolar(motor, referencia: str = "h1") -> uuid.UUID:
    respuesta = await trabajos.crear(
        motor,
        hijos=[{"referencia": referencia, "colegio_id": COLEGIO, "grado": "Cuarto"}],
        preferencias={},
    )
    return uuid.UUID(respuesta["trabajo_id"])


async def _estado(motor, trabajo_id: uuid.UUID) -> str:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(select(TRABAJO.c.estado).where(TRABAJO.c.id == trabajo_id))


async def _marcar(
    motor, trabajo_id: uuid.UUID, estado: EstadoTrabajo, *, sin_cambiar: timedelta | None = None
) -> None:
    # Un `fallido` sin diagnostico viola el CHECK de la tabla: se le pone uno.
    diagnostico = {"error": "dependencia_caida"} if estado is EstadoTrabajo.FALLIDO else {}
    # `sin_cambiar`: cuanto lleva el trabajo sin tocarse. Desde 4b58080 un `procesando`
    # solo es colgado si lleva 15 minutos asi (`trabajador._COLGADO_DESDE`).
    if sin_cambiar is not None:
        diagnostico["actualizado_en"] = trabajos.ahora() - sin_cambiar
    async with motor.engine.begin() as conexion:
        await conexion.execute(
            update(TRABAJO).where(TRABAJO.c.id == trabajo_id).values(estado=estado.value, **diagnostico)
        )


@pytest.fixture()
def prestamo(motor, monkeypatch):
    """Sustituye `crear_motor` por el prestamo y anota el servicio que se pidio."""
    prestado = MotorPrestado(motor)
    pedidos: list[str] = []

    def _crear_motor(servicio: str, **_kw: Any) -> MotorPrestado:
        pedidos.append(servicio)
        return prestado

    monkeypatch.setattr(bd, "crear_motor", _crear_motor)
    prestado.pedidos = pedidos
    return prestado


@pytest.fixture()
def exitos(monkeypatch):
    """Cuenta las llamadas a la metrica de trabajos publicados."""
    cuenta = {"n": 0}

    def _contar() -> None:
        cuenta["n"] += 1

    monkeypatch.setattr(trabajador, "contar_trabajo_publicado", _contar)
    return cuenta


class TestReclamoAcotado:
    async def test_el_limite_de_la_pasada_deja_lo_demas_encolado(self, motor):
        """Una pasada de `limite=2` procesa dos y deja el tercero para la siguiente.

        El tope evita que un worker se lleve una cola entera de golpe y la deje
        `procesando` si el proceso muere: lo no reclamado sigue siendo de todos.
        """
        ids = [await _encolar(motor, f"h{i}") for i in range(3)]

        procesados = await trabajador.pasada(motor, catalogo=_catalogo_verificado(), limite=2)

        estados = [await _estado(motor, i) for i in ids]
        assert procesados == 2
        assert sorted(estados) == sorted(
            [EstadoTrabajo.ESPERA_REVISION.value] * 2 + [EstadoTrabajo.ENCOLADO.value]
        )
        assert await trabajador.pasada(motor, catalogo=_catalogo_verificado()) == 1

    async def test_sin_retomar_un_procesando_no_se_toca(self, motor):
        """Un `procesando` puede ser el trabajo vivo de otro worker: la pasada normal lo respeta."""
        trabajo_id = await _encolar(motor)
        await _marcar(motor, trabajo_id, EstadoTrabajo.PROCESANDO)
        catalogo = _catalogo_verificado()

        assert await trabajador.pasada(motor, catalogo=catalogo) == 0

        assert await _estado(motor, trabajo_id) == EstadoTrabajo.PROCESANDO.value
        assert catalogo.llamadas == []  # ni siquiera se consulto al catalogo

    async def test_la_pasada_no_toca_lo_que_ya_termino(self, motor):
        """Un trabajo `publicado` o `fallido` no vuelve a la cola por pasar el trabajador."""
        terminado = await _encolar(motor, "h-fin")
        fallido = await _encolar(motor, "h-fallo")
        await _marcar(motor, terminado, EstadoTrabajo.PUBLICADO)
        await _marcar(motor, fallido, EstadoTrabajo.FALLIDO)

        procesados = await trabajador.pasada(motor, catalogo=_catalogo_verificado(), retomar_colgados=True)

        assert procesados == 0
        assert await _estado(motor, terminado) == EstadoTrabajo.PUBLICADO.value
        assert await _estado(motor, fallido) == EstadoTrabajo.FALLIDO.value


class TestMetricaDeTrabajosPublicados:
    async def test_un_trabajo_que_termina_bien_se_cuenta_una_vez(self, motor, exitos):
        await _encolar(motor)

        assert await trabajador.pasada(motor, catalogo=_catalogo_verificado()) == 1

        assert exitos["n"] == 1

    async def test_un_trabajo_fallido_no_se_cuenta_y_no_tumba_la_pasada(self, motor, exitos):
        """El catalogo cae para el primer trabajo y se recupera para el segundo.

        La pasada sigue (el fallo queda en el estado del trabajo, reintentable) y
        la metrica cuenta solo el trabajo que si llego a revision: contar el
        fallido inflaria el indicador de negocio.
        """
        bueno = _catalogo_verificado()

        class CaeUnaVez:
            def __init__(self) -> None:
                self.llamadas = 0

            def __getattr__(self, nombre: str) -> Any:
                return getattr(bueno, nombre)

            async def listas(self, **kw: Any) -> Any:
                self.llamadas += 1
                if self.llamadas == 1:
                    raise RemotoCaido("catalogo", "conexion rechazada")
                return await bueno.listas(**kw)

        primero = await _encolar(motor, "h-1")
        segundo = await _encolar(motor, "h-2")

        procesados = await trabajador.pasada(motor, catalogo=CaeUnaVez())

        estados = {await _estado(motor, primero), await _estado(motor, segundo)}
        assert procesados == 2
        assert estados == {EstadoTrabajo.FALLIDO.value, EstadoTrabajo.ESPERA_REVISION.value}
        assert exitos["n"] == 1

    async def test_si_nadie_puede_con_el_catalogo_no_se_cuenta_nada(self, motor, exitos):
        class Caido(CatalogoFalso):
            async def listas(self, **kw: Any) -> Any:
                raise RemotoCaido("catalogo", "conexion rechazada")

        trabajo_id = await _encolar(motor)

        assert await trabajador.pasada(motor, catalogo=Caido()) == 1

        assert await _estado(motor, trabajo_id) == EstadoTrabajo.FALLIDO.value
        assert exitos["n"] == 0


class TestCorrerUnaVez:
    async def test_abre_el_motor_de_inteligencia_retoma_colgados_y_lo_cierra(
        self, motor, prestamo, monkeypatch
    ):
        """`--retomar-colgados` es la unica pasada de linea de comandos: arranque tras un crash."""
        catalogo = _catalogo_verificado()
        monkeypatch.setattr(trabajador, "ClienteCatalogo", lambda: catalogo)
        nuevo = await _encolar(motor, "h-nuevo")
        colgado = await _encolar(motor, "h-colgado")
        await _marcar(motor, colgado, EstadoTrabajo.PROCESANDO, sin_cambiar=timedelta(hours=1))

        procesados = await trabajador.correr_una_vez()

        assert procesados == 2
        assert prestamo.pedidos == ["inteligencia"]
        assert await _estado(motor, nuevo) == EstadoTrabajo.ESPERA_REVISION.value
        assert await _estado(motor, colgado) == EstadoTrabajo.ESPERA_REVISION.value
        assert prestamo.cierres == 1

    async def test_cierra_el_motor_aunque_la_pasada_reviente(self, prestamo, monkeypatch):
        async def _revienta(*_a: Any, **_k: Any) -> int:
            raise RuntimeError("base caida")

        monkeypatch.setattr(trabajador, "pasada", _revienta)
        monkeypatch.setattr(trabajador, "ClienteCatalogo", lambda: _catalogo_verificado())

        with pytest.raises(RuntimeError, match="base caida"):
            await trabajador.correr_una_vez()

        assert prestamo.cierres == 1


class TestBucle:
    @pytest.fixture()
    def vueltas(self, monkeypatch):
        """Un bucle de `n` vueltas: el `sleep` anota el intervalo y corta a la vuelta pedida."""
        registro: dict[str, Any] = {"retomar": [], "duermen": [], "corta_en": 13}

        async def _pasada(_motor, *, catalogo=None, retomar_colgados=False, **_kw) -> int:
            registro["retomar"].append(retomar_colgados)
            return 2 if len(registro["retomar"]) == 1 else 0

        async def _dormir(segundos: float, *_a: Any, **_k: Any) -> None:
            registro["duermen"].append(segundos)
            if len(registro["duermen"]) >= registro["corta_en"]:
                raise _Basta

        monkeypatch.setattr(trabajador, "pasada", _pasada)
        monkeypatch.setattr(trabajador, "ClienteCatalogo", lambda: _catalogo_verificado())
        monkeypatch.setattr(asyncio, "sleep", _dormir)
        return registro

    async def test_amplia_el_claim_a_colgados_cada_doce_vueltas(self, prestamo, vueltas):
        """A 5 s por vuelta, un `procesando` huerfano se retoma a los 60 s, no antes."""
        with pytest.raises(_Basta):
            await trabajador._bucle(7.5)

        assert vueltas["retomar"] == [False] * 11 + [True] + [False]
        assert vueltas["duermen"] == [7.5] * 13  # el intervalo pedido, entre vuelta y vuelta

    async def test_solo_avisa_cuando_proceso_algo(self, prestamo, vueltas, capsys):
        vueltas["corta_en"] = 3

        with pytest.raises(_Basta):
            await trabajador._bucle(1.0)

        lineas = [linea for linea in capsys.readouterr().out.splitlines() if linea.startswith("[trabajador]")]
        assert lineas == [
            "[trabajador] trabajos procesados: 2"
        ]  # solo la vuelta 1; las otras fueron en vacio

    async def test_cierra_el_motor_al_salir(self, prestamo, vueltas):
        vueltas["corta_en"] = 1

        with pytest.raises(_Basta):
            await trabajador._bucle(1.0)

        assert prestamo.pedidos == ["inteligencia"]
        assert prestamo.cierres == 1


class TestLineaDeComandos:
    """`main` llama a `asyncio.run`: son pruebas sincronas (no hay bucle de eventos corriendo)."""

    def test_sin_banderas_hace_una_pasada_e_imprime_cuantos(self, monkeypatch, capsys):
        async def _una_vez() -> int:
            return 3

        async def _bucle_no(_intervalo: float) -> None:
            raise AssertionError("sin --seguir no debe entrar al bucle")

        monkeypatch.setattr(trabajador, "correr_una_vez", _una_vez)
        monkeypatch.setattr(trabajador, "_bucle", _bucle_no)

        codigo = trabajador.main([])

        assert codigo == 0
        assert capsys.readouterr().out.strip() == "[trabajador] trabajos procesados: 3"

    @pytest.mark.parametrize(
        ("argv", "esperado"),
        [(["--seguir"], 5.0), (["--seguir", "--intervalo", "0.5"], 0.5)],
        ids=["intervalo_por_omision", "intervalo_pedido"],
    )
    def test_seguir_entra_al_bucle_con_su_intervalo(self, monkeypatch, argv, esperado):
        recibido: list[float] = []

        async def _bucle(intervalo: float) -> None:
            recibido.append(intervalo)

        async def _una_vez_no() -> int:
            raise AssertionError("con --seguir no se hace una pasada suelta")

        monkeypatch.setattr(trabajador, "_bucle", _bucle)
        monkeypatch.setattr(trabajador, "correr_una_vez", _una_vez_no)

        assert trabajador.main(argv) == 0
        assert recibido == [esperado]

    def test_una_bandera_desconocida_sale_con_codigo_2(self, capsys):
        with pytest.raises(SystemExit) as salida:
            trabajador.main(["--no-existe"])

        assert salida.value.code == 2
        assert "--no-existe" in capsys.readouterr().err
