"""NFR-MAN-01: la orquestacion del repartidor: ramas de una pasada, `correr_una_vez`, el bucle y el CLI.

`test_repartidor.py` fija el camino feliz y el fallo de envio. Aqui se cierran las
decisiones que quedaban: que hace con un evento que no maneja, con un destinatario
que no puede resolver o con un contacto que Identidad no entrega; que el sink del
broker solo ve lo ENTREGADO; que la pasada respeta el limite y el orden; y como
`correr_una_vez` recorre las dos bandejas de origen, comparte notificador e
identidad, y CIERRA motores y sink aunque una pasada reviente. Despues, el bucle
(`--seguir`) y la entrada de linea de comandos, con el reloj y la red sustituidos.

Importa porque el repartidor es la unica pieza que entrega los avisos (outbox,
ADR 0022) y corre desatendida: un evento que no le toca debe marcarse y no
reprocesarse cada pasada, un fallo transitorio debe dejar el evento pendiente para
reintentar sin duplicar lo ya entregado, y un error no puede dejar conexiones
abiertas contra bases AJENAS. Todo con SQLite en memoria y dobles; ningun correo
ni peticion real sale.
"""

from __future__ import annotations

import asyncio
import runpy
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, String, Table, Uuid, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion import repartidor
from tukit_operacion.modelos import Base, Texto
from tukit_operacion.notificador import Contacto, Envio, NotificadorCompuesto, NotificadorFalso
from tukit_operacion.repartidor import NOTIFICACION, Repartidor, _url_web, correr_una_vez, main

pytestmark = pytest.mark.nfr("NFR-MAN-01")

USUARIO = uuid.UUID("22222222-2222-5222-8222-222222222222")
CORREO = "acudiente.ficticio@example.test"
CELULAR = "3000000000"


@pytest.fixture(autouse=True)
def _entorno_sin_servidores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin SMTP ni broker en el entorno: el correo va a consola y no hay sink."""
    for nombre in ("TUKIT_SMTP_HOST", "TUKIT_WEB_URL", "RABBITMQ_URL"):
        monkeypatch.delenv(nombre, raising=False)


# ---------------------------------------------------------------------------
# Bases de mentira: la de Operacion y las bandejas de origen (declaradas, no importadas)
# ---------------------------------------------------------------------------


@dataclass
class Origen:
    """Una base de origen en memoria con su bandeja y su tabla de trabajos.

    Hace de `motor_origen`: expone lo que `drenar` y el repartidor usan
    (`begin`, `connect`) y anota `dispose` SIN cerrar el motor, para poder leer
    la base despues de que `correr_una_vez` termine."""

    engine: AsyncEngine
    bandeja: Table
    trabajo: Table
    dispuesto: bool = False

    def begin(self) -> Any:
        return self.engine.begin()

    def connect(self) -> Any:
        return self.engine.connect()

    async def dispose(self) -> None:
        self.dispuesto = True

    async def sembrar(self, tipo: str, *, agregado_id: uuid.UUID | None = None, carga: Any = None) -> int:
        async with self.engine.begin() as conexion:
            resultado = await conexion.execute(
                insert(self.bandeja).values(
                    tipo=tipo,
                    agregado_tipo="agregado",
                    agregado_id=agregado_id or uuid.uuid4(),
                    carga=carga if carga is not None else {},
                    intentos=0,
                )
            )
            return int(resultado.inserted_primary_key[0])

    async def sembrar_trabajo(self, trabajo_id: uuid.UUID, usuario_id: uuid.UUID | None = USUARIO) -> None:
        async with self.engine.begin() as conexion:
            await conexion.execute(insert(self.trabajo).values(id=trabajo_id, usuario_id=usuario_id))

    async def pendientes(self) -> list[Any]:
        async with self.engine.begin() as conexion:
            return list(
                await conexion.execute(
                    select(self.bandeja)
                    .where(self.bandeja.c.publicado_en.is_(None))
                    .order_by(self.bandeja.c.id)
                )
            )


async def _crear_origen() -> Origen:
    metadatos = MetaData()
    bandeja = Table(
        "bandeja_salida",
        metadatos,
        Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
        Column("tipo", String(128)),
        Column("agregado_tipo", String(64)),
        Column("agregado_id", Uuid(as_uuid=True)),
        Column("carga", Texto),
        Column("publicado_en", DateTime(timezone=True)),
        Column("intentos", Integer, default=0),
    )
    trabajo = Table(
        "trabajo_pipeline",
        metadatos,
        Column("id", Uuid(as_uuid=True), primary_key=True),
        Column("usuario_id", Uuid(as_uuid=True)),
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(metadatos.create_all)
    return Origen(engine=engine, bandeja=bandeja, trabajo=trabajo)


@pytest_asyncio.fixture
async def origen() -> AsyncIterator[Origen]:
    uno = await _crear_origen()
    yield uno
    await uno.engine.dispose()


@pytest_asyncio.fixture
async def origenes() -> AsyncIterator[dict[str, Origen]]:
    por_servicio = {"inteligencia": await _crear_origen(), "comercio": await _crear_origen()}
    yield por_servicio
    for uno in por_servicio.values():
        await uno.engine.dispose()


@pytest_asyncio.fixture
async def operacion() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield MotorServicio(
        servicio="operacion", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    await engine.dispose()


async def _notificaciones(motor: MotorServicio) -> list[Any]:
    async with motor.engine.begin() as conexion:
        return list(await conexion.execute(select(NOTIFICACION).order_by(NOTIFICACION.c.creado_en)))


class IdentidadFalsa:
    """Identidad de mentira: `contacto` es lo que devuelve (`None` = no responde)."""

    def __init__(self, contacto: dict[str, str | None] | None = None) -> None:
        self.contacto = {"correo": CORREO, "celular": None} if contacto is None else contacto
        self.disponible = True
        self.consultados: list[str] = []

    async def contacto_de(self, usuario_id: str) -> dict[str, str | None] | None:
        self.consultados.append(usuario_id)
        return self.contacto if self.disponible else None


class SinkEspia:
    """El broker de mentira: anota lo publicado y cuando se cerro."""

    def __init__(self) -> None:
        self.eventos: list[str] = []

    async def publicar(self, fila: Any) -> None:
        self.eventos.append(f"publicar:{fila.tipo}")

    async def cerrar(self) -> None:
        self.eventos.append("cerrar")


def _repartidor(
    operacion: MotorServicio,
    origen: Origen,
    *,
    notificador: Any = None,
    identidad: Any = None,
    sink: Any = None,
) -> Repartidor:
    return Repartidor(
        origen="inteligencia",
        motor_operacion=operacion,
        motor_origen=origen,  # type: ignore[arg-type]
        notificador=notificador or NotificadorFalso(),
        identidad=identidad or IdentidadFalsa(),
        sink=sink,
    )


# ---------------------------------------------------------------------------
# Una pasada: las ramas de `_entregar` / `_destinatario`
# ---------------------------------------------------------------------------


class TestUnaPasada:
    async def test_un_tipo_que_no_maneja_se_marca_publicado_sin_avisar_a_nadie(self, operacion, origen):
        """OMITIR no es un fallo: "no me toca". Se marca para no reprocesarlo en cada
        pasada, no cuenta como entregado y no resuelve contacto ni crea notificacion."""
        await origen.sembrar("evento_de_otro_equipo")
        notificador, identidad = NotificadorFalso(), IdentidadFalsa()

        entregados = await _repartidor(
            operacion, origen, notificador=notificador, identidad=identidad
        ).pasada()

        assert entregados == 0
        assert await origen.pendientes() == []
        assert notificador.enviados == []
        assert identidad.consultados == []
        assert await _notificaciones(operacion) == []

    async def test_kits_publicados_de_un_trabajo_inexistente_queda_pendiente_con_un_intento(
        self, operacion, origen
    ):
        await origen.sembrar("kits_publicados", agregado_id=uuid.uuid4())  # sin fila en trabajo_pipeline
        notificador = NotificadorFalso()

        entregados = await _repartidor(operacion, origen, notificador=notificador).pasada()

        (pendiente,) = await origen.pendientes()
        assert entregados == 0
        assert pendiente.intentos == 1
        assert notificador.enviados == []
        assert await _notificaciones(operacion) == []  # sin destinatario no hay aviso que registrar

    async def test_un_trabajo_sin_usuario_tampoco_tiene_destinatario(self, operacion, origen):
        trabajo_id = uuid.uuid4()
        await origen.sembrar_trabajo(trabajo_id, usuario_id=None)
        await origen.sembrar("kits_publicados", agregado_id=trabajo_id)

        assert await _repartidor(operacion, origen).pasada() == 0
        assert (await origen.pendientes())[0].intentos == 1

    @pytest.mark.parametrize(
        "carga", [{}, {"usuario_id": None}, {"usuario_id": ""}], ids=["vacia", "nulo", "vacio"]
    )
    async def test_pedido_pagado_sin_usuario_en_la_carga_queda_pendiente(self, operacion, origen, carga):
        await origen.sembrar("pedido_pagado", carga=carga)

        entregados = await _repartidor(operacion, origen).pasada()

        assert entregados == 0
        assert [p.intentos for p in await origen.pendientes()] == [1]
        assert await _notificaciones(operacion) == []

    async def test_incidencia_toma_el_usuario_de_la_carga_y_usa_su_plantilla(self, operacion, origen):
        incidencia_id = uuid.uuid4()
        await origen.sembrar(
            "incidencia",
            agregado_id=incidencia_id,
            carga={"usuario_id": str(USUARIO), "pedido_id": str(incidencia_id)},
        )
        notificador = NotificadorFalso()

        entregados = await _repartidor(operacion, origen, notificador=notificador).pasada()

        (notificacion,) = await _notificaciones(operacion)
        assert entregados == 1
        assert (notificacion.usuario_id, notificacion.plantilla, notificacion.estado) == (
            USUARIO,
            "incidencia",
            "enviada",
        )
        assert notificacion.enviada_en is not None
        assert notificador.enviados[0]["texto"].startswith(
            f"Hubo una novedad con tu pedido {str(incidencia_id)[:8].upper()}"
        )

    async def test_si_identidad_cae_el_aviso_queda_pendiente_y_al_volver_se_entrega_sin_duplicar(
        self, operacion, origen
    ):
        """Con el notificador real (sin SMTP), un contacto no resuelto no puede salir:
        la pasada deja el evento para reintentar y registra el intento como fallido;
        cuando Identidad vuelve, la siguiente pasada lo entrega y una tercera no repite."""
        await origen.sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)})
        identidad = IdentidadFalsa()
        identidad.disponible = False
        reparto = _repartidor(operacion, origen, notificador=NotificadorCompuesto(), identidad=identidad)

        assert await reparto.pasada() == 0
        assert [p.intentos for p in await origen.pendientes()] == [1]
        assert [n.estado for n in await _notificaciones(operacion)] == ["fallida"]

        identidad.disponible = True
        assert await reparto.pasada() == 1
        assert await origen.pendientes() == []
        assert sorted(n.estado for n in await _notificaciones(operacion)) == ["enviada", "fallida"]

        assert await reparto.pasada() == 0  # nada pendiente: no se vuelve a avisar
        assert len(await _notificaciones(operacion)) == 2
        assert identidad.consultados == [str(USUARIO)] * 2

    async def test_la_notificacion_guarda_el_canal_que_se_uso_y_nunca_el_contacto(self, operacion, origen):
        await origen.sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)})
        identidad = IdentidadFalsa({"correo": CORREO, "celular": CELULAR})

        await _repartidor(operacion, origen, notificador=NotificadorCompuesto(), identidad=identidad).pasada()

        (notificacion,) = await _notificaciones(operacion)
        assert notificacion.canal == "wa_link"  # con celular, la via reactiva
        assert CORREO not in str(notificacion)
        assert CELULAR not in str(notificacion)

    async def test_el_sink_solo_recibe_lo_entregado(self, operacion, origen):
        await origen.sembrar("evento_de_otro_equipo")  # OMITIR
        await origen.sembrar("kits_publicados")  # REINTENTAR: no hay trabajo
        await origen.sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)})  # HECHO
        sink = SinkEspia()

        entregados = await _repartidor(operacion, origen, sink=sink).pasada()

        assert entregados == 1
        assert sink.eventos == ["publicar:pedido_pagado"]

    async def test_el_limite_acota_la_pasada_y_conserva_el_orden_de_llegada(self, operacion, origen):
        ids = [await origen.sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)}) for _ in range(3)]

        entregados = await _repartidor(operacion, origen).pasada(limite=2)

        assert entregados == 2
        assert [p.id for p in await origen.pendientes()] == [ids[2]]  # queda el ultimo en llegar


class TestElMotorDeLectura:
    @pytest.mark.parametrize("servicio", ["inteligencia", "comercio"])
    def test_apunta_a_la_base_del_servicio_de_origen_y_verifica_la_conexion_antes_de_usarla(
        self, servicio, monkeypatch
    ):
        """La URL la deriva `tukit_comun` del nombre del servicio (regla 3: este modulo
        nunca escribe `tukit_<otro>`); el pool comprueba la conexion antes de cada uso
        porque el repartidor corre horas y la base ajena puede reiniciarse.

        Se espia `create_async_engine`: un motor `postgresql+asyncpg` exige el driver,
        que es opcional (`tukit-comun[postgres]`) y el job `pruebas` del CI no instala."""
        # La URL completa del entorno ganaria sobre el nombre derivado (la prueba
        # siguiente): sin quitarla, el resultado depende de la terminal que corre.
        monkeypatch.delenv(f"TUKIT_{servicio.upper()}_DB_URL", raising=False)
        pedidos: list[tuple[Any, dict[str, Any]]] = []
        monkeypatch.setattr(repartidor, "create_async_engine", lambda url, **kw: pedidos.append((url, kw)))

        repartidor._motor_lectura(servicio)

        [(url, opciones)] = pedidos
        assert make_url(url).database == f"tukit_{servicio}"
        assert make_url(url).drivername == "postgresql+asyncpg"
        assert opciones == {"pool_pre_ping": True}

    async def test_la_url_completa_del_entorno_gana_sobre_las_piezas(self, monkeypatch):
        monkeypatch.setenv("TUKIT_COMERCIO_DB_URL", "sqlite+aiosqlite:///:memory:")

        motor = repartidor._motor_lectura("comercio")
        try:
            assert motor.url.drivername == "sqlite+aiosqlite"
        finally:
            await motor.dispose()


class TestLaUrlDeLaApp:
    def test_por_omision_es_el_next_de_desarrollo(self):
        assert _url_web() == "http://localhost:3000"

    def test_del_entorno_sin_barra_final(self, monkeypatch):
        monkeypatch.setenv("TUKIT_WEB_URL", "https://tukit.example.test//")

        assert _url_web() == "https://tukit.example.test"


# ---------------------------------------------------------------------------
# correr_una_vez: las dos bandejas, y el cierre de todo
# ---------------------------------------------------------------------------


class MotorOperacionEspia:
    """Hace de `MotorServicio`: delega la sesion y anota `cerrar` sin cerrar el motor."""

    def __init__(self, motor: MotorServicio, eventos: list[str]) -> None:
        self.motor = motor
        self.engine = motor.engine
        self._eventos = eventos

    def sesion(self) -> Any:
        return self.motor.sesion()

    async def cerrar(self) -> None:
        self._eventos.append("cerrar_operacion")


@dataclass
class Entorno:
    eventos: list[str]
    pedidos_de_lectura: list[str]
    notificador: NotificadorFalso
    identidad: IdentidadFalsa
    operacion: MotorOperacionEspia


@pytest.fixture
def entorno(monkeypatch, operacion, origenes) -> Entorno:
    """Sustituye lo que `correr_una_vez` saca del entorno: motores, notificador, identidad y sink."""
    eventos: list[str] = []
    pedidos: list[str] = []
    notificador, identidad = NotificadorFalso(), IdentidadFalsa()
    espia = MotorOperacionEspia(operacion, eventos)

    def motor_lectura(servicio: str) -> Origen:
        pedidos.append(servicio)
        return origenes[servicio]

    monkeypatch.setattr(repartidor, "crear_motor", lambda servicio: espia)
    monkeypatch.setattr(repartidor, "_motor_lectura", motor_lectura)
    monkeypatch.setattr(repartidor, "notificador_desde_entorno", lambda: notificador)
    monkeypatch.setattr(repartidor, "ClienteIdentidad", lambda: identidad)
    monkeypatch.setattr(repartidor, "sink_desde_entorno", lambda: None)
    return Entorno(eventos, pedidos, notificador, identidad, espia)


class TestCorrerUnaVez:
    async def test_recorre_inteligencia_y_luego_comercio_y_reporta_lo_entregado_en_cada_una(
        self, entorno, origenes, operacion
    ):
        trabajo_id = uuid.uuid4()
        await origenes["inteligencia"].sembrar_trabajo(trabajo_id)
        await origenes["inteligencia"].sembrar("kits_publicados", agregado_id=trabajo_id)
        for _ in range(2):
            await origenes["comercio"].sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)})

        resultado = await correr_una_vez()

        assert resultado == {"inteligencia": 1, "comercio": 2}
        assert entorno.pedidos_de_lectura == ["inteligencia", "comercio"]
        assert [e["plantilla"] for e in entorno.notificador.enviados] == [
            "kits_publicados",
            "pedido_pagado",
            "pedido_pagado",
        ]  # un solo notificador, compartido por las dos pasadas
        assert entorno.identidad.consultados == [str(USUARIO)] * 3
        assert len(await _notificaciones(operacion)) == 3
        assert [await uno.pendientes() for uno in origenes.values()] == [[], []]

    async def test_sin_nada_pendiente_reporta_ceros(self, entorno):
        assert await correr_una_vez() == {"inteligencia": 0, "comercio": 0}

    async def test_cierra_los_motores_de_origen_y_el_de_operacion(self, entorno, origenes):
        await correr_una_vez()

        assert [uno.dispuesto for uno in origenes.values()] == [True, True]
        assert entorno.eventos == ["cerrar_operacion"]

    async def test_con_broker_publica_cada_entrega_y_lo_cierra_al_final(self, entorno, origenes, monkeypatch):
        sink = SinkEspia()
        monkeypatch.setattr(repartidor, "sink_desde_entorno", lambda: sink)
        await origenes["comercio"].sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)})

        await correr_una_vez()

        assert sink.eventos == ["publicar:pedido_pagado", "cerrar"]

    async def test_si_una_pasada_revienta_cierra_todo_y_el_error_sale(self, entorno, origenes, monkeypatch):
        """Lo que NO puede pasar en un proceso desatendido: dejar conexiones abiertas
        contra la base de otro servicio (la excepcion outbox declarada)."""

        async def revienta(contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
            raise RuntimeError("el notificador se cayo")

        sink = SinkEspia()
        monkeypatch.setattr(repartidor, "sink_desde_entorno", lambda: sink)
        monkeypatch.setattr(entorno.notificador, "enviar", revienta)
        await origenes["inteligencia"].sembrar("pedido_pagado", carga={"usuario_id": str(USUARIO)})

        with pytest.raises(RuntimeError, match="el notificador se cayo"):
            await correr_una_vez()

        assert origenes["inteligencia"].dispuesto is True
        assert entorno.eventos == ["cerrar_operacion"]
        assert sink.eventos == ["cerrar"]
        assert [p.intentos for p in await origenes["inteligencia"].pendientes()] == [0]  # nada se marco


# ---------------------------------------------------------------------------
# El bucle (`--seguir`) y la entrada de linea de comandos
# ---------------------------------------------------------------------------


class _Alto(Exception):
    """Corta el bucle infinito desde el reloj de mentira."""


class TestElBucle:
    async def test_imprime_solo_las_pasadas_que_entregaron_algo_y_duerme_el_intervalo(
        self, monkeypatch, capsys
    ):
        pasadas = iter([{"inteligencia": 0, "comercio": 0}, {"inteligencia": 1, "comercio": 0}, {}])
        dormidos: list[float] = []

        async def una_vez() -> dict[str, int]:
            return next(pasadas)

        async def dormir(segundos: float) -> None:
            dormidos.append(segundos)
            if len(dormidos) == 3:
                raise _Alto

        monkeypatch.setattr(repartidor, "correr_una_vez", una_vez)
        monkeypatch.setattr(repartidor, "asyncio", SimpleNamespace(sleep=dormir))

        with pytest.raises(_Alto):
            await repartidor._bucle(2.5)

        assert dormidos == [2.5, 2.5, 2.5]
        assert capsys.readouterr().out == "[repartidor] entregados: {'inteligencia': 1, 'comercio': 0}\n"


class TestMain:
    def test_sin_seguir_hace_una_pasada_imprime_el_reporte_y_devuelve_cero(self, monkeypatch, capsys):
        async def una_vez() -> dict[str, int]:
            return {"inteligencia": 2, "comercio": 0}

        monkeypatch.setattr(repartidor, "correr_una_vez", una_vez)

        assert main([]) == 0
        assert capsys.readouterr().out == "[repartidor] entregados: {'inteligencia': 2, 'comercio': 0}\n"

    @pytest.mark.parametrize(
        ("argumentos", "intervalo"),
        [(["--seguir"], 5.0), (["--seguir", "--intervalo", "2.5"], 2.5)],
        ids=["intervalo-por-omision", "intervalo-pedido"],
    )
    def test_con_seguir_corre_el_bucle_y_no_la_pasada_unica(self, monkeypatch, argumentos, intervalo):
        bucles: list[float] = []

        async def bucle(segundos: float) -> None:
            bucles.append(segundos)

        async def una_vez() -> dict[str, int]:
            raise AssertionError("con --seguir no hay pasada unica")

        monkeypatch.setattr(repartidor, "_bucle", bucle)
        monkeypatch.setattr(repartidor, "correr_una_vez", una_vez)

        assert main(argumentos) == 0
        assert bucles == [intervalo]

    def test_un_intervalo_que_no_es_numero_se_rechaza_antes_de_correr(self, monkeypatch):
        async def una_vez() -> dict[str, int]:
            raise AssertionError("no debia correr")

        monkeypatch.setattr(repartidor, "correr_una_vez", una_vez)

        with pytest.raises(SystemExit) as salida:
            main(["--seguir", "--intervalo", "cinco"])

        assert salida.value.code == 2

    def test_ejecutado_como_modulo_sale_con_el_codigo_de_main(self, monkeypatch, capsys):
        """`python -m tukit_operacion.repartidor`: una pasada, el reporte y salida 0."""
        corridas: list[str] = []

        def correr(corrutina: Awaitable[Any]) -> dict[str, int]:
            corridas.append("asyncio.run")
            corrutina.close()  # type: ignore[attr-defined]
            return {"inteligencia": 0, "comercio": 0}

        monkeypatch.setattr(sys, "argv", ["tukit_operacion.repartidor"])
        monkeypatch.setattr(asyncio, "run", correr)

        with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_operacion.repartidor", run_name="__main__")

        assert salida.value.code == 0
        assert corridas == ["asyncio.run"]
        assert capsys.readouterr().out == "[repartidor] entregados: {'inteligencia': 0, 'comercio': 0}\n"
