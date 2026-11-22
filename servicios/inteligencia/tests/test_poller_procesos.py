"""NFR-MAN-01: El poller de `lista_verificada`: eventos que no sirven, atomicidad y arranque como proceso.

`test_poller.py` fija el camino feliz (un evento arma el kit del padre, el
evento se marca publicado, una segunda pasada no duplica). Aqui se fijan los
bordes que deciden si el outbox pierde o duplica trabajo:

- un evento sin colegio o sin grado no sirve para armar un kit de grado: se
  OMITE y se marca publicado, para no reintentarlo eternamente;
- el poller solo atiende `lista_verificada`; otro tipo de evento no se toca
  (otro consumidor lo necesitara sin publicar);
- si crear el trabajo falla, el evento NO queda marcado publicado: se reintenta
  en la pasada siguiente en vez de perderse;
- el `limite` acota cuantos eventos se atienden por pasada;
- `anio_lectivo` solo viaja al trabajo si el evento lo trae;
- `correr_una_vez`/`_bucle`/`main` abren los dos motores (el propio y el de
  lectura al catalogo, la unica excepcion de frontera de bases) y los cierran
  SIEMPRE.

Los motores son el SQLite de la fixture envuelto para anotar el cierre; el
catalogo, un doble; el `asyncio.sleep` del bucle, uno que corta cuando la
prueba decide. Ninguna prueba duerme ni abre una conexion real.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import MetaData, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine
from _ayudas_inteligencia import catalogo_verificado as _catalogo_verificado
from conftest import COLEGIO
from _ayudas_inteligencia import BANDEJA_CATALOGO
from _ayudas_inteligencia import carga_lista_verificada as _carga
from _ayudas_inteligencia import sembrar_bandeja as _sembrar_bandeja
from tukit_comun.bandeja import bandeja_reflejada
from tukit_inteligencia import poller as modulo_poller
from tukit_inteligencia import trabajos
from tukit_inteligencia.poller import Poller

pytestmark = pytest.mark.nfr("NFR-MAN-01")

# La tabla de bandeja es comun a todos los servicios: se refleja la misma que
# usa `drenar` para leer los eventos sembrados.
_BANDEJA = bandeja_reflejada(MetaData())


class MotorPrestado:
    """El motor SQLite de la fixture, con el cierre anotado en vez de ejecutado.

    Sirve de motor propio (`cerrar`) y de motor de lectura (`dispose`): si
    cerrara de verdad se perderia la base en memoria antes de poder leerla.
    """

    def __init__(self, motor: Any) -> None:
        self._motor = motor
        self.cierres = 0

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._motor, nombre)

    def begin(self) -> Any:
        return self._motor.engine.begin()

    async def cerrar(self) -> None:
        self.cierres += 1

    async def dispose(self) -> None:
        self.cierres += 1


class _Basta(Exception):  # noqa: N818  (senal de prueba para romper un bucle infinito)
    """Corta el bucle `while True` del poller cuando la prueba ya vio lo que queria."""


async def _publicado_en(motor, agregado_id: uuid.UUID) -> Any:
    async with motor.engine.begin() as conexion:
        return await conexion.scalar(
            select(_BANDEJA.c.publicado_en).where(_BANDEJA.c.agregado_id == agregado_id)
        )


async def _trabajos_creados(motor) -> list[Any]:
    async with motor.engine.begin() as conexion:
        return list(await conexion.execute(select(trabajos.TRABAJO.c.id, trabajos.TRABAJO.c.hijos)))


def _poller(motor) -> Poller:
    return Poller(motor_inteligencia=motor, motor_catalogo=motor.engine, catalogo=_catalogo_verificado())


class TestEventosQueNoSirvenParaUnKit:
    @pytest.mark.parametrize(
        "carga",
        [
            {"contacto_referencia": str(uuid.uuid4()), "grado": "Cuarto"},
            {"contacto_referencia": str(uuid.uuid4()), "colegio_id": COLEGIO},
            {"contacto_referencia": str(uuid.uuid4()), "colegio_id": "", "grado": ""},
            {},
        ],
        ids=["sin_colegio", "sin_grado", "vacios", "carga_vacia"],
    )
    async def test_sin_colegio_o_grado_se_omite_y_se_marca_publicado(self, motor, carga):
        """No hay como armar un kit de grado: reintentar el evento seria un bucle sin salida."""
        version_id = await _sembrar_bandeja(motor, **carga)

        arrancados = await _poller(motor).pasada()

        assert arrancados == 0  # OMITIR no cuenta como kit arrancado
        assert await _publicado_en(motor, version_id) is not None
        assert await _trabajos_creados(motor) == []

    async def test_solo_atiende_lista_verificada_y_deja_los_demas_eventos(self, motor):
        """Otro tipo de evento en la misma bandeja es de otro consumidor: no se publica por error."""
        ajeno = uuid.uuid4()
        propio = await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                insert(BANDEJA_CATALOGO).values(
                    tipo="producto_actualizado",
                    agregado_tipo="producto",
                    agregado_id=ajeno,
                    carga={"colegio_id": COLEGIO, "grado": "Cuarto"},
                    intentos=0,
                )
            )

        arrancados = await _poller(motor).pasada()

        assert arrancados == 1
        assert await _publicado_en(motor, propio) is not None
        assert await _publicado_en(motor, ajeno) is None  # sigue pendiente para su consumidor
        assert len(await _trabajos_creados(motor)) == 1


class TestAtomicidadDelEvento:
    async def test_si_crear_el_trabajo_falla_el_evento_sigue_pendiente(self, motor, monkeypatch):
        """Un evento perdido es un padre que nunca recibe su kit: se reintenta en la pasada siguiente."""
        version_id = await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))

        original = trabajos.crear

        async def _crear_que_falla(*_a: Any, **_k: Any) -> dict[str, Any]:
            raise RuntimeError("base de inteligencia caida")

        monkeypatch.setattr(trabajos, "crear", _crear_que_falla)

        with pytest.raises(RuntimeError, match="base de inteligencia caida"):
            await _poller(motor).pasada()

        assert await _publicado_en(motor, version_id) is None
        assert await _trabajos_creados(motor) == []

        monkeypatch.setattr(trabajos, "crear", original)  # la base vuelve: la pasada siguiente SI arma el kit
        assert await _poller(motor).pasada() == 1
        assert await _publicado_en(motor, version_id) is not None

    async def test_el_limite_acota_los_eventos_por_pasada(self, motor):
        for _ in range(3):
            await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))
        poller = _poller(motor)

        assert await poller.pasada(limite=2) == 2
        assert len(await _trabajos_creados(motor)) == 2
        assert await poller.pasada(limite=2) == 1  # el que quedo
        assert await poller.pasada(limite=2) == 0


class TestHijoDelTrabajo:
    async def test_el_anio_lectivo_solo_viaja_si_el_evento_lo_trae(self, motor):
        """Sin anio en el evento el catalogo elige el vigente: el poller no inventa uno."""
        sin_anio = {"contacto_referencia": None, "colegio_id": COLEGIO, "grado": "Cuarto"}
        con_anio = {**sin_anio, "anio_lectivo": 2027}
        await _sembrar_bandeja(motor, **sin_anio)
        await _sembrar_bandeja(motor, **con_anio)

        assert await _poller(motor).pasada() == 2

        hijos = [fila.hijos[0] for fila in await _trabajos_creados(motor)]
        assert sorted(("anio_lectivo" in h, h.get("anio_lectivo")) for h in hijos) == [
            (False, None),
            (True, 2027),
        ]
        assert {h["colegio_id"] for h in hijos} == {COLEGIO}
        assert {h["grado"] for h in hijos} == {"Cuarto"}
        assert {h["referencia"] for h in hijos} == {"hijo-1"}

    async def test_las_preferencias_ausentes_son_un_diccionario_vacio(self, motor, monkeypatch):
        """El kit del colegio se arma con las preferencias base: `None` no debe llegar a `crear`."""
        visto: dict[str, Any] = {}
        original = trabajos.crear

        async def _espia(motor_, **kw: Any) -> dict[str, Any]:
            visto.update(kw)
            return await original(motor_, **kw)

        monkeypatch.setattr(trabajos, "crear", _espia)
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4()), None))

        assert await _poller(motor).pasada() == 1

        assert visto["preferencias"] == {}
        assert visto["origen"] == "lista_verificada"


class TestMotorDeLectura:
    def test_la_url_viene_de_la_variable_completa_del_servicio(self, monkeypatch):
        """El nombre de la base ajena no se escribe aqui: lo pone `url_desde_entorno`."""
        monkeypatch.setenv("TUKIT_CATALOGO_DB_URL", "sqlite+aiosqlite:///catalogo-de-prueba.db")

        motor = modulo_poller._motor_lectura("catalogo")

        assert isinstance(motor, AsyncEngine)
        assert str(motor.url) == "sqlite+aiosqlite:///catalogo-de-prueba.db"
        assert motor.sync_engine.pool._pre_ping is True  # un pool que sobrevive a una base reiniciada

    def test_sin_variable_la_base_se_deriva_del_nombre_del_servicio(self, monkeypatch):
        """Se espia `create_async_engine`: armar un motor `postgresql+asyncpg` exige
        el driver, que es opcional a proposito (`tukit-comun[postgres]`) y el job
        `pruebas` del CI no instala."""
        monkeypatch.delenv("TUKIT_CATALOGO_DB_URL", raising=False)
        monkeypatch.setenv("TUKIT_DB_HOST", "bd.interna.example.test")
        monkeypatch.setenv("TUKIT_DB_PORT", "6543")
        pedidos: list[tuple[Any, dict[str, Any]]] = []
        monkeypatch.setattr(modulo_poller, "create_async_engine", lambda url, **kw: pedidos.append((url, kw)))

        servicio = "catalogo"

        modulo_poller._motor_lectura(servicio)

        [(url, opciones)] = pedidos
        url = make_url(url)
        assert url.host == "bd.interna.example.test"
        assert url.port == 6543
        # Armado con el nombre del servicio, no escrito: la frontera
        # `test_ningun_servicio_nombra_la_base_de_otro` mira los literales.
        assert url.database == f"tukit_{servicio}"
        assert opciones == {"pool_pre_ping": True}


class TestArranqueComoProceso:
    @pytest.fixture()
    def motores(self, motor, monkeypatch):
        """Los dos motores del proceso, prestados; anota que servicio pidio cada fabrica."""
        propio, lectura = MotorPrestado(motor), MotorPrestado(motor)
        pedidos: list[tuple[str, str]] = []

        def _crear_motor(servicio: str, **_kw: Any) -> MotorPrestado:
            pedidos.append(("propio", servicio))
            return propio

        def _motor_lectura(servicio: str) -> MotorPrestado:
            pedidos.append(("lectura", servicio))
            return lectura

        monkeypatch.setattr(modulo_poller, "crear_motor", _crear_motor)
        monkeypatch.setattr(modulo_poller, "_motor_lectura", _motor_lectura)
        monkeypatch.setattr(modulo_poller, "ClienteCatalogo", lambda: _catalogo_verificado())
        return {"propio": propio, "lectura": lectura, "pedidos": pedidos}

    async def test_una_pasada_lee_del_catalogo_crea_en_lo_propio_y_cierra_ambos(self, motor, motores):
        version_id = await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))

        arrancados = await modulo_poller.correr_una_vez()

        assert arrancados == 1
        assert motores["pedidos"] == [("propio", "inteligencia"), ("lectura", "catalogo")]
        assert await _publicado_en(motor, version_id) is not None
        assert (motores["propio"].cierres, motores["lectura"].cierres) == (1, 1)

    async def test_cierra_ambos_motores_aunque_la_pasada_reviente(self, motores, monkeypatch):
        async def _revienta(self: Poller, **_k: Any) -> int:
            raise RuntimeError("catalogo ilegible")

        monkeypatch.setattr(Poller, "pasada", _revienta)

        with pytest.raises(RuntimeError, match="catalogo ilegible"):
            await modulo_poller.correr_una_vez()

        assert (motores["propio"].cierres, motores["lectura"].cierres) == (1, 1)

    async def test_el_bucle_repite_duerme_el_intervalo_y_solo_avisa_si_arranco_kits(
        self, monkeypatch, capsys
    ):
        resultados = iter([2, 0, 5])
        duermen: list[float] = []

        async def _una_vez() -> int:
            return next(resultados)

        async def _dormir(segundos: float, *_a: Any, **_k: Any) -> None:
            duermen.append(segundos)
            if len(duermen) == 3:
                raise _Basta

        monkeypatch.setattr(modulo_poller, "correr_una_vez", _una_vez)
        monkeypatch.setattr(asyncio, "sleep", _dormir)

        with pytest.raises(_Basta):
            await modulo_poller._bucle(2.5)

        assert duermen == [2.5, 2.5, 2.5]
        lineas = [x for x in capsys.readouterr().out.splitlines() if x.startswith("[poller]")]
        assert lineas == [
            "[poller] kits de ruta rapida arrancados: 2",
            "[poller] kits de ruta rapida arrancados: 5",
        ]


class TestLineaDeComandos:
    """`main` llama a `asyncio.run`: son pruebas sincronas (no hay bucle de eventos corriendo)."""

    def test_sin_banderas_hace_una_pasada_e_imprime_cuantos(self, monkeypatch, capsys):
        async def _una_vez() -> int:
            return 4

        async def _bucle_no(_intervalo: float) -> None:
            raise AssertionError("sin --seguir no debe entrar al bucle")

        monkeypatch.setattr(modulo_poller, "correr_una_vez", _una_vez)
        monkeypatch.setattr(modulo_poller, "_bucle", _bucle_no)

        assert modulo_poller.main([]) == 0
        assert capsys.readouterr().out.strip() == "[poller] kits de ruta rapida arrancados: 4"

    @pytest.mark.parametrize(
        ("argv", "esperado"),
        [(["--seguir"], 5.0), (["--seguir", "--intervalo", "0.25"], 0.25)],
        ids=["intervalo_por_omision", "intervalo_pedido"],
    )
    def test_seguir_entra_al_bucle_con_su_intervalo(self, monkeypatch, argv, esperado):
        recibido: list[float] = []

        async def _bucle(intervalo: float) -> None:
            recibido.append(intervalo)

        async def _una_vez_no() -> int:
            raise AssertionError("con --seguir no se hace una pasada suelta")

        monkeypatch.setattr(modulo_poller, "_bucle", _bucle)
        monkeypatch.setattr(modulo_poller, "correr_una_vez", _una_vez_no)

        assert modulo_poller.main(argv) == 0
        assert recibido == [esperado]

    def test_un_intervalo_que_no_es_numero_sale_con_codigo_2(self, capsys):
        with pytest.raises(SystemExit) as salida:
            modulo_poller.main(["--seguir", "--intervalo", "rapido"])

        assert salida.value.code == 2
        assert "--intervalo" in capsys.readouterr().err
