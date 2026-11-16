"""El repartidor: la mitad de ENTREGA del contrato de eventos (§10, ADR 0041/0042/0046).

Se prueba con bases SQLite en memoria: la de Operacion (donde nace la
notificacion) y una o varias de origen que imitan la bandeja de
Inteligencia/Comercio. No se levanta Postgres, RabbitMQ ni la red: el
`Notificador` es el falso, que registra lo enviado, y el cliente de Identidad es
un doble que devuelve un contacto fijo.

Lo que se defiende, por comportamiento:

- **Sondeo de la bandeja.** Un evento no publicado da EXACTAMENTE una
  notificacion y queda publicado; el destinatario de `kits_publicados` sale de
  `trabajo_pipeline.usuario_id` y el de los pedidos, de la carga. Ni la
  notificacion guardada ni el cuerpo llevan correo o celular (Ley 1581).
- **Un evento, un aviso** (H-B-03, CH-15). Si publicar al broker falla y la
  bandeja vuelve atras, la reentrega no envia otra vez; lo que no se aviso
  (un envio fallido) si se reintenta. El mismo `id` desde otra bandeja es otro
  evento.
- **Consumo de la cola** `operacion.avisos` (ADR 0046): el mismo aviso, el
  destinatario de la carga, ninguna base ajena; lo que no tiene destinatario
  pide reintentar.
- **Vuelve tras una caida** de Postgres o de RabbitMQ (H-B-02): el bucle espera,
  reintenta y entrega; un error de programacion lo sigue terminando.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    insert,
    select,
)
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio
from tukit_comun.consumidor import Consumidor, Decision
from tukit_comun.mensajes import Evento, cuerpo
from tukit_comun.topologia import AVISOS
from tukit_operacion import repartidor
from tukit_operacion.dominio.reparto import _PLANTILLAS
from tukit_operacion.modelos import Base, Texto
from tukit_operacion.notificador import Envio, NotificadorCompuesto, NotificadorFalso
from tukit_operacion.repartidor import NOTIFICACION, Repartidor

USUARIO = uuid.UUID("22222222-2222-5222-8222-222222222222")
CORREO = "ana@ejemplo.com"
CELULAR = "3001234567"
TRABAJO = uuid.UUID("33333333-3333-4333-8333-333333333333")
APODO = "Sofi-la-pilosa"
_INTERVALO = 5.0


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


# La bandeja y los trabajos del servicio de origen, declarados igual que en el
# repartidor (no se importan: regla 1). `carga` usa el tipo portable.
def _tablas_origen() -> tuple[MetaData, Table, Table]:
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
    return metadatos, bandeja, trabajo


class IdentidadContacto:
    """Doble del cliente de Identidad: devuelve un contacto fijo por id.

    Registra a quien le preguntaron para comprobar que el repartidor resuelve el
    contacto al vuelo (y no lo guarda)."""

    def __init__(self, correo: str | None = CORREO, celular: str | None = CELULAR) -> None:
        self.correo = correo
        self.celular = celular
        self.consultados: list[str] = []

    async def contacto_de(self, usuario_id: str) -> dict[str, str | None] | None:
        self.consultados.append(usuario_id)
        return {"correo": self.correo, "celular": self.celular}


class _IdentidadConColegios(IdentidadContacto):
    """Ademas nombra colegios; registra cuales le pidieron."""

    def __init__(self, nombres: dict[str, str]) -> None:
        super().__init__()
        self.nombres = nombres
        self.colegios: list[str] = []

    async def nombre_colegio(self, colegio_id: str) -> str | None:
        self.colegios.append(colegio_id)
        return self.nombres.get(colegio_id)


class _NotificadorQueFallaPrimero(NotificadorFalso):
    """El primer envio no sale (el proveedor de correo no responde); los demas si."""

    def __init__(self) -> None:
        super().__init__()
        self.intentos = 0

    async def enviar(self, contacto, plantilla, datos) -> Envio:
        self.intentos += 1
        if self.intentos == 1:
            return Envio(canal=self.canal, exito=False, detalle="proveedor_caido")
        return await super().enviar(contacto, plantilla, datos)


# aiormq no se importa: las pruebas de los servicios corren sin el. Estas clases
# tienen los nombres y las bases de las de aiormq (`AMQPConnectionError` es un
# `ConnectionError`; `ChannelInvalidStateError`, un `RuntimeError`).
class AMQPConnectionError(ConnectionError):
    pass


class ChannelInvalidStateError(RuntimeError):
    pass


class _SinkIntermitente:
    """Un `BrokerSink` con RabbitMQ caido: lanza los errores dados, en orden, y despues publica."""

    def __init__(self, *errores: BaseException) -> None:
        self.errores = list(errores)
        self.publicados: list[int] = []

    async def publicar(self, fila: Any) -> None:
        if self.errores:
            raise self.errores.pop(0)
        self.publicados.append(fila.id)

    async def cerrar(self) -> None:
        pass


def _broker_caido(veces: int) -> _SinkIntermitente:
    return _SinkIntermitente(*(AMQPConnectionError("[Errno 111] Connection refused") for _ in range(veces)))


class _EngineIntermitente:
    """Un `AsyncEngine` cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion, como asyncpg
    con Postgres caido; despues delega en el engine de verdad. No se cierra: la
    base en memoria de la prueba se perderia.
    """

    def __init__(self, real: Any, *errores: BaseException) -> None:
        self.real = real
        self.errores = list(errores)

    @asynccontextmanager
    async def begin(self):
        if self.errores:
            raise self.errores.pop(0)
        async with self.real.begin() as conexion:
            yield conexion

    async def dispose(self) -> None:
        pass

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


class _MotorDePrueba:
    """El `MotorServicio` de Operacion de la prueba, que no se cierra."""

    def __init__(self, real: MotorServicio) -> None:
        self.real = real
        self.engine = real.engine
        self.cerrado = False

    def sesion(self):
        return self.real.sesion()

    async def cerrar(self) -> None:
        self.cerrado = True


class _Corte(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


def _dormir_que_corta(esperas: list[float]):
    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == _INTERVALO:
            raise _Corte

    return dormir


# ---------------------------------------------------------------------------
# Bases y siembra
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def motor_operacion() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="operacion", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def _base_de_origen() -> tuple[AsyncEngine, Table, Table]:
    metadatos, bandeja, trabajo = _tablas_origen()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(metadatos.create_all)
    return engine, bandeja, trabajo


@pytest_asyncio.fixture
async def motor_origen() -> AsyncIterator[tuple[AsyncEngine, Table, Table]]:
    origen = await _base_de_origen()
    yield origen
    await origen[0].dispose()


@pytest_asyncio.fixture
async def otro_origen() -> AsyncIterator[tuple[AsyncEngine, Table, Table]]:
    """Una segunda bandeja, que numera sus eventos por su cuenta."""
    origen = await _base_de_origen()
    yield origen
    await origen[0].dispose()


@pytest_asyncio.fixture
async def origenes() -> AsyncIterator[dict[str, tuple[AsyncEngine, Table]]]:
    """Las bases de Inteligencia, Comercio y Operacion (respuestas a tickets, S5),
    cada una con su bandeja: `correr_una_vez` recorre las tres."""
    bandejas: dict[str, tuple[AsyncEngine, Table]] = {}
    for origen in ("inteligencia", "comercio", "operacion"):
        engine, bandeja, _trabajo = await _base_de_origen()
        bandejas[origen] = (engine, bandeja)
    yield bandejas
    for engine, _bandeja in bandejas.values():
        await engine.dispose()


async def _sembrar_kits_publicados(engine, bandeja, trabajo, trabajo_id: uuid.UUID, carga=None) -> None:
    async with engine.begin() as conexion:
        await conexion.execute(insert(trabajo).values(id=trabajo_id, usuario_id=USUARIO))
        await conexion.execute(
            insert(bandeja).values(
                tipo="kits_publicados",
                agregado_tipo="trabajo_pipeline",
                agregado_id=trabajo_id,
                carga=carga or {},
                intentos=0,
            )
        )


async def _sembrar_pedido(engine, bandeja, tipo: str = "pedido_pagado", **carga) -> int:
    pedido_id = carga.pop("pedido_id", None) or uuid.uuid4()
    async with engine.begin() as conexion:
        resultado = await conexion.execute(
            insert(bandeja).values(
                tipo=tipo,
                agregado_tipo="pedido",
                agregado_id=pedido_id,
                carga={"usuario_id": str(USUARIO), "pedido_id": str(pedido_id), **carga},
                intentos=0,
            )
        )
    return resultado.inserted_primary_key[0]


async def _notificaciones(motor_operacion) -> list:
    async with motor_operacion.engine.connect() as conexion:
        return list(await conexion.execute(select(NOTIFICACION).order_by(NOTIFICACION.c.creado_en)))


async def _pendientes(engine, bandeja) -> list:
    async with engine.begin() as conexion:
        return list(await conexion.execute(select(bandeja).where(bandeja.c.publicado_en.is_(None))))


async def _publicado(engine, bandeja, evento_id: int) -> bool:
    async with engine.begin() as conexion:
        publicado_en = await conexion.scalar(select(bandeja.c.publicado_en).where(bandeja.c.id == evento_id))
    return publicado_en is not None


def _repartidor(
    motor_operacion, engine, notificador=None, identidad=None, *, origen="inteligencia", sink=None
) -> Repartidor:
    return Repartidor(
        origen=origen,
        motor_operacion=motor_operacion,
        motor_origen=engine,
        notificador=notificador or NotificadorFalso(),
        identidad=identidad or IdentidadContacto(),
        sink=sink,
    )


# ---------------------------------------------------------------------------
# Sondeo de la bandeja de origen
# ---------------------------------------------------------------------------


class TestSondeoDeLaBandeja:
    async def test_una_pasada_crea_una_notificacion_y_marca_publicado(self, motor_operacion, motor_origen):
        engine, bandeja, trabajo = motor_origen
        await _sembrar_kits_publicados(engine, bandeja, trabajo, uuid.uuid4())
        notificador = NotificadorFalso()
        identidad = IdentidadContacto()

        assert await _repartidor(motor_operacion, engine, notificador, identidad).pasada() == 1

        [fila] = await _notificaciones(motor_operacion)
        # El destinatario se resolvio desde trabajo_pipeline.usuario_id, no de la carga.
        assert fila.usuario_id == USUARIO
        assert await _pendientes(engine, bandeja) == []
        # Se resolvio el contacto al vuelo y el notificador registro un envio.
        assert identidad.consultados == [str(USUARIO)]
        assert len(notificador.enviados) == 1

    async def test_segunda_pasada_no_reprocesa(self, motor_operacion, motor_origen):
        engine, bandeja, trabajo = motor_origen
        await _sembrar_kits_publicados(engine, bandeja, trabajo, uuid.uuid4())
        notificador = NotificadorFalso()
        reparto = _repartidor(motor_operacion, engine, notificador)

        assert await reparto.pasada() == 1
        assert await reparto.pasada() == 0
        assert len(await _notificaciones(motor_operacion)) == 1
        assert len(notificador.enviados) == 1

    async def test_notificacion_y_contenido_no_llevan_contacto(self, motor_operacion, motor_origen):
        engine, bandeja, trabajo = motor_origen
        await _sembrar_kits_publicados(engine, bandeja, trabajo, uuid.uuid4())
        notificador = NotificadorFalso()
        await _repartidor(motor_operacion, engine, notificador).pasada()

        [fila] = await _notificaciones(motor_operacion)
        guardado = f"{fila.datos} {fila.canal} {fila.plantilla}"
        texto = notificador.enviados[0]["texto"]
        for contacto in (CORREO, CELULAR):
            assert contacto not in guardado
            assert contacto not in texto

    async def test_kits_publicados_lleva_el_enlace_de_precompra_sin_contacto(
        self, motor_operacion, motor_origen, monkeypatch
    ):
        monkeypatch.setenv("TUKIT_WEB_URL", "https://tukit.co")
        engine, bandeja, trabajo = motor_origen
        trabajo_id = uuid.uuid4()
        await _sembrar_kits_publicados(engine, bandeja, trabajo, trabajo_id)
        notificador = NotificadorFalso()
        await _repartidor(motor_operacion, engine, notificador).pasada()

        texto = notificador.enviados[0]["texto"]
        assert f"https://tukit.co/kits/{trabajo_id}" in texto
        assert CORREO not in texto
        assert CELULAR not in texto

    async def test_kits_publicados_pone_colegio_y_grado_sin_el_apodo(
        self, motor_operacion, motor_origen, monkeypatch
    ):
        monkeypatch.setenv("TUKIT_WEB_URL", "https://tukit.co")
        engine, bandeja, trabajo = motor_origen
        # La carga real no trae apodo; aun si lo trajera, no se usa.
        carga = {"colegio_id": "c1", "grado": "3", "apodo": APODO}
        await _sembrar_kits_publicados(engine, bandeja, trabajo, TRABAJO, carga)
        notificador = NotificadorFalso()
        reparto = _repartidor(
            motor_operacion, engine, notificador, _IdentidadConColegios({"c1": "Colegio Alamei"})
        )

        await reparto.pasada()
        await reparto.pasada()

        [envio] = notificador.enviados
        assert "Colegio Alamei, grado 3" in envio["texto"] and APODO not in envio["texto"]
        [fila] = await _notificaciones(motor_operacion)
        assert APODO not in str(fila)

    async def test_kits_publicados_nombra_todas_las_listas_del_hogar(
        self, motor_operacion, motor_origen, monkeypatch
    ):
        monkeypatch.setenv("TUKIT_WEB_URL", "https://tukit.co")
        engine, bandeja, trabajo = motor_origen
        carga = {
            "colegio_id": "c1",
            "grado": "Septimo",
            "listas": [
                {"colegio_id": "c1", "grado": "Septimo"},
                {"colegio_id": "c1", "grado": "Jardin"},
                {"colegio_id": "c2", "grado": "5"},
            ],
        }
        await _sembrar_kits_publicados(engine, bandeja, trabajo, TRABAJO, carga)
        notificador = NotificadorFalso()
        identidad = _IdentidadConColegios({"c1": "Colegio A", "c2": "Colegio B"})

        await _repartidor(motor_operacion, engine, notificador, identidad).pasada()

        assert "Colegio A, grados Septimo y Jardin y Colegio B, grado 5" in notificador.enviados[0]["texto"]
        # Un nombre por colegio distinto, no por lista.
        assert sorted(identidad.colegios) == ["c1", "c2"]

    async def test_pedido_pagado_saca_el_usuario_de_la_carga(self, motor_operacion, motor_origen):
        engine, bandeja, _trabajo = motor_origen
        await _sembrar_pedido(engine, bandeja)

        assert await _repartidor(motor_operacion, engine).pasada() == 1

        [fila] = await _notificaciones(motor_operacion)
        assert (fila.usuario_id, fila.plantilla) == (USUARIO, "pedido_pagado")

    async def test_pedido_despachado_avisa_con_el_repartidor_y_sin_su_celular(
        self, motor_operacion, motor_origen
    ):
        # Comercio solo pone el NOMBRE en la carga; aun si un evento trajera mas, lo
        # que se guarda son las variables de la plantilla, no la carga entera.
        engine, bandeja, _trabajo = motor_origen
        pedido_id = uuid.UUID("abcd1234-0000-4000-8000-000000000000")
        await _sembrar_pedido(
            engine,
            bandeja,
            "pedido_despachado",
            pedido_id=pedido_id,
            repartidor="Luis",
            repartidor_celular="3109998877",
        )
        notificador = NotificadorFalso()

        assert await _repartidor(motor_operacion, engine, notificador).pasada() == 1

        [fila] = await _notificaciones(motor_operacion)
        assert (fila.usuario_id, fila.plantilla) == (USUARIO, "pedido_despachado")
        assert "3109998877" not in str(fila.datos)
        assert notificador.enviados[0]["texto"] == "Tu pedido ABCD1234 salió y va con Luis."

    async def test_sin_contacto_el_envio_falla_sube_intentos_y_no_publica(
        self, motor_operacion, motor_origen
    ):
        engine, bandeja, trabajo = motor_origen
        await _sembrar_kits_publicados(engine, bandeja, trabajo, uuid.uuid4())

        class SinContacto:
            async def contacto_de(self, usuario_id: str):
                return None

        class NotificadorQueFalla:
            canal = "correo"

            async def enviar(self, contacto, plantilla, datos):
                return Envio(canal="correo", exito=False, detalle="sin_correo")

        assert await _repartidor(motor_operacion, engine, NotificadorQueFalla(), SinContacto()).pasada() == 0

        [pendiente] = await _pendientes(engine, bandeja)
        assert pendiente.intentos == 1
        [fila] = await _notificaciones(motor_operacion)
        assert fila.estado == "fallida"

    async def test_sin_bandeja_de_origen_no_hay_pasada(self, motor_operacion):
        with pytest.raises(ValueError):
            await _repartidor(motor_operacion, None, origen=None).pasada()


# ---------------------------------------------------------------------------
# Un evento, un aviso (H-B-03, ADR 0042)
# ---------------------------------------------------------------------------


class TestUnEventoAvisaUnaVez:
    async def test_si_el_broker_falla_la_reentrega_no_vuelve_a_avisar(self, motor_operacion, motor_origen):
        engine, bandeja, _trabajo = motor_origen
        evento_id = await _sembrar_pedido(engine, bandeja)
        notificador = NotificadorFalso()
        identidad = IdentidadContacto()
        sink = _broker_caido(1)
        reparto = _repartidor(motor_operacion, engine, notificador, identidad, origen="comercio", sink=sink)

        # Primera pasada: el aviso sale y queda registrado, pero publicar falla
        # y la bandeja vuelve atras. Es lo que paso en CH-15.
        with pytest.raises(AMQPConnectionError):
            await reparto.pasada()
        assert not await _publicado(engine, bandeja, evento_id)

        # Segunda pasada, con el broker de vuelta: el mismo evento llega otra vez.
        assert await reparto.pasada() == 1

        assert [envio["plantilla"] for envio in notificador.enviados] == ["pedido_pagado"]
        # Ni siquiera se resolvio otra vez el contacto del acudiente.
        assert identidad.consultados == [str(USUARIO)]
        [fila] = await _notificaciones(motor_operacion)
        assert (fila.plantilla, fila.estado) == ("pedido_pagado", "enviada")
        assert (fila.evento_origen, fila.evento_id) == ("comercio", evento_id)
        assert sink.publicados == [evento_id]
        assert await _publicado(engine, bandeja, evento_id)

    async def test_varias_caidas_del_broker_siguen_dando_un_solo_aviso(self, motor_operacion, motor_origen):
        engine, bandeja, _trabajo = motor_origen
        evento_id = await _sembrar_pedido(engine, bandeja)
        notificador = NotificadorFalso()
        reparto = _repartidor(motor_operacion, engine, notificador, origen="comercio", sink=_broker_caido(3))

        for _ in range(3):
            with pytest.raises(AMQPConnectionError):
                await reparto.pasada()
        assert await reparto.pasada() == 1

        assert len(notificador.enviados) == 1
        assert len(await _notificaciones(motor_operacion)) == 1
        assert await _publicado(engine, bandeja, evento_id)

    async def test_un_envio_fallido_se_reintenta_y_sale(self, motor_operacion, motor_origen):
        engine, bandeja, _trabajo = motor_origen
        evento_id = await _sembrar_pedido(engine, bandeja)
        notificador = _NotificadorQueFallaPrimero()
        reparto = _repartidor(motor_operacion, engine, notificador, origen="comercio")

        assert await reparto.pasada() == 0
        assert not await _publicado(engine, bandeja, evento_id)
        assert await reparto.pasada() == 1

        assert notificador.intentos == 2
        assert len(notificador.enviados) == 1
        filas = await _notificaciones(motor_operacion)
        assert [f.estado for f in filas] == ["fallida", "enviada"]
        assert {(f.evento_origen, f.evento_id) for f in filas} == {("comercio", evento_id)}
        assert await _publicado(engine, bandeja, evento_id)

    async def test_dos_pagos_distintos_dan_dos_avisos(self, motor_operacion, motor_origen):
        engine, bandeja, _trabajo = motor_origen
        primero = await _sembrar_pedido(engine, bandeja)
        segundo = await _sembrar_pedido(engine, bandeja)
        notificador = NotificadorFalso()

        assert await _repartidor(motor_operacion, engine, notificador, origen="comercio").pasada() == 2

        assert len(notificador.enviados) == 2
        filas = await _notificaciones(motor_operacion)
        assert sorted(f.evento_id for f in filas) == sorted([primero, segundo])

    async def test_el_mismo_id_en_otra_bandeja_es_otro_evento(
        self, motor_operacion, motor_origen, otro_origen
    ):
        # Cada bandeja numera sus eventos por su cuenta: el evento 1 de Comercio
        # y el evento 1 de Inteligencia son dos avisos distintos.
        engine_comercio, bandeja_comercio, _ = motor_origen
        engine_inteligencia, bandeja_inteligencia, trabajo = otro_origen
        id_comercio = await _sembrar_pedido(engine_comercio, bandeja_comercio)
        await _sembrar_kits_publicados(engine_inteligencia, bandeja_inteligencia, trabajo, uuid.uuid4())
        notificador = NotificadorFalso()

        assert await _repartidor(motor_operacion, engine_inteligencia, notificador).pasada() == 1
        assert (
            await _repartidor(motor_operacion, engine_comercio, notificador, origen="comercio").pasada() == 1
        )

        assert [envio["plantilla"] for envio in notificador.enviados] == ["kits_publicados", "pedido_pagado"]
        filas = await _notificaciones(motor_operacion)
        assert id_comercio == 1
        assert {(f.evento_origen, f.evento_id) for f in filas} == {("inteligencia", 1), ("comercio", 1)}

    async def test_un_fallo_deja_su_detalle_para_el_panel_de_correos(self, motor_operacion, motor_origen):
        engine, bandeja, _trabajo = motor_origen
        await _sembrar_pedido(engine, bandeja)

        await _repartidor(motor_operacion, engine, _NotificadorQueFallaPrimero(), origen="comercio").pasada()

        [fila] = await _notificaciones(motor_operacion)
        assert (fila.estado, fila.detalle) == ("fallida", "proveedor_caido")

    async def test_un_destino_no_enviable_queda_omitido_y_cierra_el_evento(
        self, motor_operacion, motor_origen, monkeypatch
    ):
        monkeypatch.setenv("TUKIT_SMTP_HOST", "smtp.invalido.test")
        monkeypatch.delenv("TUKIT_CORREO_PERMITIDOS", raising=False)
        engine, bandeja, _trabajo = motor_origen
        evento_id = await _sembrar_pedido(engine, bandeja)
        identidad = IdentidadContacto(correo="operador@tukit.co", celular=None)
        reparto = _repartidor(motor_operacion, engine, NotificadorCompuesto(), identidad, origen="comercio")

        assert await reparto.pasada() == 1

        [fila] = await _notificaciones(motor_operacion)
        assert fila.estado == "omitida"
        assert (fila.detalle, fila.destino_dominio) == ("destino_no_enviable", "tukit.co")
        assert fila.asunto.startswith("Recibimos tu pago")
        assert await _publicado(engine, bandeja, evento_id)


# ---------------------------------------------------------------------------
# Consumo de la cola operacion.avisos (ADR 0046)
# ---------------------------------------------------------------------------


def _de_la_cola(motor_operacion: MotorServicio, notificador: Any = None) -> Repartidor:
    return _repartidor(motor_operacion, None, notificador, origen=None)


def _evento_kits(
    id_: int = 7, *, origen: str = "inteligencia", usuario: uuid.UUID | None = USUARIO
) -> Evento:
    carga: dict[str, Any] = {"trabajo_id": str(TRABAJO)}
    if usuario is not None:
        carga["usuario_id"] = str(usuario)
    return Evento(
        id=id_,
        origen=origen,
        tipo="kits_publicados",
        agregado_tipo="trabajo_pipeline",
        agregado_id=TRABAJO,
        carga=carga,
    )


class TestConsumoDeLaCola:
    async def test_un_evento_de_la_cola_da_el_aviso_con_el_destinatario_de_la_carga(self, motor_operacion):
        notificador = NotificadorFalso()

        assert await _de_la_cola(motor_operacion, notificador).manejar(_evento_kits()) is Resultado.HECHO

        [fila] = await _notificaciones(motor_operacion)
        assert fila.usuario_id == USUARIO
        assert (fila.evento_origen, fila.evento_id) == ("inteligencia", 7)
        assert fila.plantilla == "kits_publicados"
        assert len(notificador.enviados) == 1

    async def test_el_mismo_evento_dos_veces_da_un_solo_aviso(self, motor_operacion):
        notificador = NotificadorFalso()
        reparto = _de_la_cola(motor_operacion, notificador)

        assert await reparto.manejar(_evento_kits()) is Resultado.HECHO
        # El broker lo entrega otra vez (un ack perdido, una publicacion repetida).
        assert await reparto.manejar(_evento_kits()) is Resultado.HECHO

        assert len(await _notificaciones(motor_operacion)) == 1
        assert len(notificador.enviados) == 1

    async def test_el_mismo_id_desde_otro_origen_es_otro_evento(self, motor_operacion):
        reparto = _de_la_cola(motor_operacion)
        pagado = Evento(
            id=7,
            origen="comercio",
            tipo="pedido_pagado",
            agregado_tipo="pedido",
            agregado_id=uuid.uuid4(),
            carga={"pedido_id": "p-1", "usuario_id": str(USUARIO)},
        )

        assert await reparto.manejar(_evento_kits(7)) is Resultado.HECHO
        assert await reparto.manejar(pagado) is Resultado.HECHO

        filas = await _notificaciones(motor_operacion)
        assert sorted(f.evento_origen for f in filas) == ["comercio", "inteligencia"]

    async def test_un_kits_publicados_sin_usuario_pide_reintentar(self, motor_operacion):
        notificador = NotificadorFalso()

        resultado = await _de_la_cola(motor_operacion, notificador).manejar(_evento_kits(usuario=None))

        assert resultado is Resultado.REINTENTAR
        assert notificador.enviados == []
        assert await _notificaciones(motor_operacion) == []

    async def test_un_envio_fallido_pide_reintentar_y_luego_sale(self, motor_operacion):
        reparto = _de_la_cola(motor_operacion, _NotificadorQueFallaPrimero())

        assert await reparto.manejar(_evento_kits()) is Resultado.REINTENTAR
        assert await reparto.manejar(_evento_kits()) is Resultado.HECHO
        assert [f.estado for f in await _notificaciones(motor_operacion)] == ["fallida", "enviada"]

    async def test_un_tipo_sin_plantilla_se_omite(self, motor_operacion):
        solicitado = Evento(id=1, origen="inteligencia", tipo="pedido_solicitado", carga={})

        assert await _de_la_cola(motor_operacion).manejar(solicitado) is Resultado.OMITIR

    async def test_por_el_consumidor_confirma_el_mensaje(self, motor_operacion):
        class _Mensaje:
            headers: dict[str, Any] = {}

            def __init__(self, evento: Evento) -> None:
                self.body = cuerpo(evento)
                self.acks = 0

            async def ack(self) -> None:
                self.acks += 1

        consumidor = Consumidor(cola=AVISOS, manejar=_de_la_cola(motor_operacion).manejar)
        mensaje = _Mensaje(_evento_kits())

        assert await consumidor.procesar(mensaje) is Decision.HECHO
        assert mensaje.acks == 1

    def test_la_cola_recibe_justo_los_tipos_con_plantilla(self):
        assert set(AVISOS.claves) == set(_PLANTILLAS)

    def test_con_rabbitmq_url_main_consume_la_cola_y_no_abre_bases_ajenas(self, monkeypatch, capsys):
        monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@broker:5672/")

        class _MotorFalso:
            cerrado = False

            async def cerrar(self) -> None:
                self.cerrado = True

        motor = _MotorFalso()
        llamadas: list[dict[str, Any]] = []

        async def consumir(url, consumidor, **opciones):
            llamadas.append({"url": url, "cola": consumidor.cola.nombre, **opciones})
            return 3

        def _sin_bases_ajenas(origen):  # pragma: no cover - no debe llamarse
            raise AssertionError(f"abrio la base de {origen}")

        monkeypatch.setattr(repartidor, "crear_motor", lambda servicio: motor)
        monkeypatch.setattr(repartidor, "_motor_lectura", _sin_bases_ajenas)
        monkeypatch.setattr(repartidor, "consumir", consumir)
        monkeypatch.setattr(repartidor, "notificador_desde_entorno", NotificadorFalso)
        monkeypatch.setattr(repartidor, "ClienteIdentidad", IdentidadContacto)

        assert repartidor.main([]) == 0

        [llamada] = llamadas
        assert llamada["url"] == "amqp://guest:guest@broker:5672/"
        assert llamada["cola"] == "operacion.avisos"
        assert llamada["seguir"] is False
        assert llamada["proceso"] == "operacion-repartidor"
        assert motor.cerrado
        assert "operacion.avisos: 3" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# El proceso vuelve tras una caida (H-B-02, ADR 0041)
# ---------------------------------------------------------------------------


def _conectar(
    monkeypatch, motor_operacion, origenes, *, comercio: Any = None, sink: Any = None
) -> NotificadorFalso:
    """Cambia lo que `correr_una_vez` saca del entorno por las piezas de la prueba.

    `correr_una_vez` cierra los motores de origen en cada vuelta: sin el
    envoltorio, la base en memoria se perderia tras la primera."""
    notificador = NotificadorFalso()
    motores = {origen: _EngineIntermitente(engine) for origen, (engine, _bandeja) in origenes.items()}
    if comercio is not None:
        motores["comercio"] = comercio
    monkeypatch.setattr(repartidor, "crear_motor", lambda _servicio: _MotorDePrueba(motor_operacion))
    monkeypatch.setattr(repartidor, "_motor_lectura", lambda origen: motores[origen])
    monkeypatch.setattr(repartidor, "notificador_desde_entorno", lambda: notificador)
    monkeypatch.setattr(repartidor, "ClienteIdentidad", IdentidadContacto)
    monkeypatch.setattr(repartidor, "sink_desde_entorno", lambda: sink)
    return notificador


class TestVuelveTrasUnaCaida:
    async def test_tras_una_caida_de_postgres_entrega_el_aviso(self, motor_operacion, origenes, monkeypatch):
        engine, bandeja = origenes["comercio"]
        evento_id = await _sembrar_pedido(engine, bandeja)
        # En Docker el nombre del contenedor muerto deja de resolver: `socket.gaierror`.
        comercio = _EngineIntermitente(
            engine,
            ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
            ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
            socket.gaierror(8, "nodename nor servname provided, or not known"),
        )
        notificador = _conectar(monkeypatch, motor_operacion, origenes, comercio=comercio)
        esperas: list[float] = []

        with pytest.raises(_Corte):
            await repartidor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == [1.0, 2.0, 4.0, _INTERVALO]
        assert [envio["plantilla"] for envio in notificador.enviados] == ["pedido_pagado"]
        assert await _publicado(engine, bandeja, evento_id)

    async def test_tras_una_caida_de_rabbitmq_publica_el_evento(self, motor_operacion, origenes, monkeypatch):
        engine, bandeja = origenes["comercio"]
        evento_id = await _sembrar_pedido(engine, bandeja)
        sink = _SinkIntermitente(
            AMQPConnectionError("[Errno 111] Connection refused"),
            ChannelInvalidStateError("No active transport in channel"),
        )
        notificador = _conectar(monkeypatch, motor_operacion, origenes, sink=sink)
        esperas: list[float] = []

        with pytest.raises(_Corte):
            await repartidor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == [1.0, 2.0, _INTERVALO]
        assert sink.publicados == [evento_id]
        assert await _publicado(engine, bandeja, evento_id)
        # El evento se entrego tres veces, pero el acudiente recibe un solo aviso y
        # queda una sola notificacion, que es lo que mide CH-15 (H-B-03, ADR 0042).
        assert [envio["plantilla"] for envio in notificador.enviados] == ["pedido_pagado"]
        assert [f.plantilla for f in await _notificaciones(motor_operacion)] == ["pedido_pagado"]

    async def test_un_error_de_programacion_sigue_terminando_el_repartidor(
        self, motor_operacion, origenes, monkeypatch
    ):
        engine, _bandeja = origenes["comercio"]
        _conectar(
            monkeypatch, motor_operacion, origenes, comercio=_EngineIntermitente(engine, ValueError("bug"))
        )
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await repartidor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == []

    async def test_el_bucle_duerme_con_el_asyncio_sleep_de_cuando_corre(self, monkeypatch):
        # Sin `dormir`, el bucle usa el `asyncio.sleep` que ve el modulo al correr,
        # no el de cuando se definio: asi lo sustituyen las pruebas de los procesos.
        vueltas: list[int] = []

        async def _nada() -> dict[str, int]:
            vueltas.append(1)
            if len(vueltas) > 1:
                raise _Corte
            return {}

        esperas: list[float] = []
        monkeypatch.setattr(repartidor, "correr_una_vez", _nada)
        monkeypatch.setattr(repartidor, "asyncio", SimpleNamespace(sleep=_dormir_que_corta(esperas)))

        with pytest.raises(_Corte):
            await repartidor._bucle(_INTERVALO)

        assert esperas == [_INTERVALO]

    def test_el_repartidor_configura_el_log_al_arrancar(self, monkeypatch):
        titulos: list[str] = []
        monkeypatch.setattr(repartidor, "configurar_registro", titulos.append)

        async def _nada() -> dict[str, int]:
            return {}

        monkeypatch.setattr(repartidor, "correr_una_vez", _nada)

        assert repartidor.main([]) == 0
        assert titulos == ["operacion-repartidor"]
