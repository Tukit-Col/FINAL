from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import MetaData, func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comun.bandeja import Resultado, bandeja_reflejada
from tukit_comun.bd import MotorServicio
from tukit_comun.consumidor import Consumidor, Decision
from tukit_comun.mensajes import Evento, cuerpo
from tukit_comun.resiliencia import ESPERA_INICIAL_BUCLE
from tukit_comun.topologia import COLEGIOS
from tukit_identidad import poller as modulo
from tukit_identidad.modelos import (
    AcudienteMatricula,
    Colegio,
    Estudiante,
    Matricula,
    Sede,
    Usuario,
)
from tukit_identidad.poller import Poller

BANDEJA_CATALOGO = bandeja_reflejada(MetaData())

COLEGIO = str(uuid.uuid4())
USUARIO_ID = str(uuid.uuid4())


async def _sembrar_usuario(motor: MotorServicio, usuario_id: str = USUARIO_ID) -> None:
    async with motor.sesion() as db:
        db.add(Usuario(id=uuid.UUID(usuario_id), correo=f"{usuario_id}@ejemplo.co", clave_hash="x"))


@pytest_asyncio.fixture
async def motor_catalogo() -> AsyncIterator[Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA_CATALOGO.metadata.create_all)
    yield engine
    await engine.dispose()


_SIGUIENTE_ID = [0]


async def _sembrar_bandeja(motor_catalogo: Any, **carga: Any) -> None:
    _SIGUIENTE_ID[0] += 1
    async with motor_catalogo.begin() as conexion:
        await conexion.execute(
            insert(BANDEJA_CATALOGO).values(
                id=_SIGUIENTE_ID[0],
                tipo="colegio_verificado",
                agregado_tipo="colegio",
                agregado_id=uuid.UUID(carga.get("colegio_id") or COLEGIO),
                carga=carga,
                intentos=0,
            )
        )


def _carga(**extra: Any) -> dict[str, Any]:
    base = {
        "colegio_id": COLEGIO,
        "grado": "Cuarto",
        "nombre": "ACADEMIA CENTRAL DE SISTEMAS",
        "nit": "311001105731",
        "direccion": "Calle 1 # 2-3",
    }
    base.update(extra)
    return base


class TestPollerDaDeAltaElColegio:
    async def test_un_evento_da_de_alta_el_colegio_con_el_id_del_evento(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga())

        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)
        aplicados = await poller.pasada()

        assert aplicados == 1
        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
        assert str(colegio.id) == COLEGIO
        assert colegio.nombre == "ACADEMIA CENTRAL DE SISTEMAS"
        assert colegio.nit == "311001105731"
        assert colegio.dane == "311001105731"
        assert colegio.direccion == "Calle 1 # 2-3"
        assert colegio.activo is True

    async def test_un_nit_que_no_es_dane_no_llena_la_columna(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga(nit="900.123.456-7"))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)
        await poller.pasada()

        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
        assert colegio.nit == "900.123.456-7"
        assert colegio.dane is None

    async def test_al_colegio_se_le_crea_una_sede_principal(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga())
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)
        await poller.pasada()

        async with motor.sesion() as db:
            sedes = list(
                (await db.execute(select(Sede).where(Sede.colegio_id == uuid.UUID(COLEGIO)))).scalars()
            )
        assert len(sedes) == 1
        assert sedes[0].nombre

    async def test_una_segunda_pasada_no_duplica_el_colegio(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga())
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1
        assert await poller.pasada() == 0

        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert len(colegios) == 1

    async def test_un_segundo_evento_del_mismo_colegio_completa_sin_pisar(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga(nit=None, direccion=None))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)
        await poller.pasada()

        await _sembrar_bandeja(motor_catalogo, **_carga(nit="311001105731", direccion="Calle 1 # 2-3"))
        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
            sedes = list(
                (await db.execute(select(Sede).where(Sede.colegio_id == uuid.UUID(COLEGIO)))).scalars()
            )
        assert colegio.nit == "311001105731"
        assert colegio.direccion == "Calle 1 # 2-3"
        assert len(sedes) == 1


class TestPollerIgnoraLoQueNoLeSirve:
    async def test_un_evento_sin_id_no_da_de_alta_pero_se_marca_publicado(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, colegio_id=None, nombre="X")
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 0
        async with motor.engine.begin() as conexion:
            colegios = list(await conexion.execute(select(Colegio.id)))
        async with motor_catalogo.begin() as conexion:
            pendientes = list(
                await conexion.execute(
                    select(BANDEJA_CATALOGO.c.id).where(BANDEJA_CATALOGO.c.publicado_en.is_(None))
                )
            )
        assert colegios == []
        assert pendientes == []

    async def test_un_evento_sin_nombre_no_da_de_alta_nada(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga(nombre="   "))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 0
        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert colegios == []


async def _contar(motor: MotorServicio) -> tuple[int, int, int]:
    async with motor.sesion() as db:
        estudiantes = list((await db.execute(select(Estudiante))).scalars())
        matriculas = list((await db.execute(select(Matricula))).scalars())
        vinculos = list((await db.execute(select(AcudienteMatricula))).scalars())
    return len(estudiantes), len(matriculas), len(vinculos)


class TestPollerMatriculaAlHijo:

    async def test_matricula_al_hijo_cuando_el_padre_existe(self, motor, motor_catalogo):
        await _sembrar_usuario(motor)
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            matricula = (
                await db.execute(select(Matricula).where(Matricula.colegio_id == uuid.UUID(COLEGIO)))
            ).scalar_one()
            vinculo = (
                await db.execute(
                    select(AcudienteMatricula).where(AcudienteMatricula.usuario_id == uuid.UUID(USUARIO_ID))
                )
            ).scalar_one()
        assert matricula.grado == "Cuarto"
        assert matricula.anio_lectivo == datetime.now(UTC).year
        assert vinculo.matricula_id == matricula.id
        assert vinculo.es_principal is True
        assert vinculo.parentesco == "acudiente"
        assert await _contar(motor) == (1, 1, 1)

    async def test_una_segunda_pasada_no_duplica_la_matricula(self, motor, motor_catalogo):
        await _sembrar_usuario(motor)
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1
        assert await poller.pasada() == 0

        assert await _contar(motor) == (1, 1, 1)

    async def test_sin_contacto_referencia_crea_colegio_pero_no_matricula(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga())
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert len(colegios) == 1
        assert await _contar(motor) == (0, 0, 0)

    async def test_con_padre_inexistente_crea_colegio_pero_no_matricula(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert len(colegios) == 1
        assert await _contar(motor) == (0, 0, 0)

    async def test_idempotencia_entre_eventos_repetidos(self, motor, motor_catalogo):
        await _sembrar_usuario(motor)
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        await poller.pasada()

        assert await _contar(motor) == (1, 1, 1)


class TestPollerConsumeLaColaConRabbitmq:

    @staticmethod
    def _evento(id_: int = 1, **extra: Any) -> Evento:
        return Evento(
            id=id_,
            origen="catalogo",
            tipo="colegio_verificado",
            agregado_tipo="colegio",
            agregado_id=uuid.UUID(COLEGIO),
            carga=_carga(contacto_referencia=USUARIO_ID, **extra),
        )

    @staticmethod
    async def _cuantos(motor, modelo) -> int:
        async with motor.sesion() as db:
            return await db.scalar(select(func.count()).select_from(modelo))

    async def test_un_evento_de_la_cola_da_de_alta_el_colegio(self, motor):
        await _sembrar_usuario(motor)
        poller = Poller(motor_identidad=motor, motor_catalogo=None)

        assert await poller.manejar(self._evento()) is Resultado.HECHO

        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio))).scalar_one()
        assert str(colegio.id) == COLEGIO
        assert colegio.nombre == _carga()["nombre"]
        assert await _contar(motor) == (1, 1, 1)

    async def test_un_evento_repetido_deja_la_base_igual(self, motor):
        await _sembrar_usuario(motor)
        poller = Poller(motor_identidad=motor, motor_catalogo=None)
        consumidor = Consumidor(cola=modulo.COLEGIOS, manejar=poller.manejar)
        evento = self._evento(7)

        class _Mensaje:
            headers: dict[str, Any] = {}

            def __init__(self) -> None:
                self.body = cuerpo(evento)
                self.acks = 0

            async def ack(self) -> None:
                self.acks += 1

        primero, segundo = _Mensaje(), _Mensaje()
        assert await consumidor.procesar(primero) is Decision.HECHO
        assert await consumidor.procesar(segundo) is Decision.HECHO

        assert (primero.acks, segundo.acks) == (1, 1)
        assert await self._cuantos(motor, Colegio) == 1
        assert await self._cuantos(motor, Sede) == 1
        assert await _contar(motor) == (1, 1, 1)

    async def test_otro_tipo_se_omite(self, motor):
        poller = Poller(motor_identidad=motor, motor_catalogo=None)
        lista = Evento(id=2, origen="catalogo", tipo="lista_verificada", carga=_carga())

        assert await poller.manejar(lista) is Resultado.OMITIR
        assert await self._cuantos(motor, Colegio) == 0

    async def test_sin_la_bandeja_del_catalogo_no_hay_pasada(self, motor):
        with pytest.raises(ValueError):
            await Poller(motor_identidad=motor, motor_catalogo=None).pasada()

    def test_con_rabbitmq_url_main_consume_la_cola_y_no_abre_el_catalogo(self, monkeypatch):
        monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@broker:5672/")
        motor_falso = _MotorFalso()
        llamadas: list[dict[str, Any]] = []

        async def consumir(url, consumidor, **opciones):
            llamadas.append({"url": url, "cola": consumidor.cola.nombre, **opciones})
            return 2

        def _sin_base_ajena(servicio, **_):  # pragma: no cover - no debe llamarse
            raise AssertionError(f"abrio la base de {servicio}")

        monkeypatch.setattr(modulo, "crear_motor", lambda servicio: motor_falso)
        monkeypatch.setattr(modulo, "url_desde_entorno", _sin_base_ajena)
        monkeypatch.setattr(modulo, "consumir", consumir)

        assert modulo.main(["--seguir", "--intervalo", "2"]) == 0

        [llamada] = llamadas
        assert (llamada["cola"], llamada["seguir"], llamada["intervalo"]) == (COLEGIOS.nombre, True, 2.0)
        assert llamada["proceso"] == "identidad-poller"
        assert motor_falso.cerrado


class _MotorFalso:
    def __init__(self) -> None:
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


_INTERVALO = 5.0


class _Corte(Exception):
    pass


class _Intermitente:

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

    async def cerrar(self) -> None:
        pass

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


def _dormir_que_corta(esperas: list[float]):
    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == _INTERVALO:
            raise _Corte

    return dormir


def _conectar(monkeypatch, motor, catalogo) -> list[str]:
    urls: list[str] = []

    def _engine_catalogo(url, **_opciones):
        urls.append(url)
        return catalogo

    monkeypatch.setattr(modulo, "crear_motor", lambda _servicio: _Intermitente(motor))
    monkeypatch.setattr(modulo, "url_desde_entorno", lambda servicio: f"prueba://{servicio}")
    monkeypatch.setattr(modulo, "create_async_engine", _engine_catalogo)
    return urls


class TestPollerResisteCaidasDePostgres:
    async def test_el_poller_vuelve_tras_una_caida_de_postgres(self, motor, motor_catalogo, monkeypatch):
        await _sembrar_bandeja(motor_catalogo, colegio_id=COLEGIO, nombre="Colegio Ficticio de Prueba")
        catalogo = _Intermitente(
            motor_catalogo,
            ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
            ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
            socket.gaierror(8, "nodename nor servname provided, or not known"),
        )
        urls = _conectar(monkeypatch, motor, catalogo)
        esperas: list[float] = []

        with pytest.raises(_Corte):
            await modulo._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        e = ESPERA_INICIAL_BUCLE
        assert esperas == [e, 2 * e, 4 * e, _INTERVALO]
        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
        assert colegio.nombre == "Colegio Ficticio de Prueba"
        async with motor_catalogo.begin() as conexion:
            publicado = await conexion.scalar(select(BANDEJA_CATALOGO.c.publicado_en))
        assert publicado is not None
        assert set(urls) == {"prueba://catalogo"}

    async def test_un_error_de_programacion_termina_el_poller(self, motor, motor_catalogo, monkeypatch):
        _conectar(monkeypatch, motor, _Intermitente(motor_catalogo, ValueError("bug")))
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await modulo._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == []

    async def test_el_bucle_duerme_con_el_asyncio_sleep_de_cuando_corre(self, monkeypatch):
        vueltas: list[int] = []

        async def _nada() -> int:
            vueltas.append(1)
            if len(vueltas) > 1:
                raise _Corte
            return 0

        esperas: list[float] = []
        monkeypatch.setattr(modulo, "correr_una_vez", _nada)
        monkeypatch.setattr(modulo, "asyncio", SimpleNamespace(sleep=_dormir_que_corta(esperas)))

        with pytest.raises(_Corte):
            await modulo._bucle(_INTERVALO)

        assert esperas == [_INTERVALO]

    def test_el_poller_configura_el_log_al_arrancar(self, monkeypatch):
        titulos: list[str] = []
        monkeypatch.setattr(modulo, "configurar_registro", titulos.append)

        async def _nada() -> int:
            return 0

        monkeypatch.setattr(modulo, "correr_una_vez", _nada)

        assert modulo.main([]) == 0
        assert titulos == ["identidad-poller"]
