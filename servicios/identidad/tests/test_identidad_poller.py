"""El poller de `colegio_verificado`: aprobar la lista de un colegio nuevo lo
da de alta como aliado en Identidad.

Prueba `tukit_identidad.poller` en sus tres modos: la pasada sobre la bandeja
del Catalogo, el consumo de la cola `identidad.colegios` con RabbitMQ (ADR 0046)
y el bucle resiliente que sobrevive a una caida de Postgres (ADR 0041).

Cuando un administrador aprueba la version que un acudiente subio para un
colegio que aun no existia en Tukit, el Catalogo escribe `colegio_verificado`
en su bandeja (nunca llama a Identidad: eso invertiria el grafo). Este poller la
drena y da de alta el colegio con el MISMO `colegio_id` que el Catalogo ya
derivo, de modo que la lista verificada y el colegio quedan ligados sin FK entre
bases.

Lo que se fija aqui:

- Un evento da de alta el colegio con el id del evento (el que el Catalogo
  derivo del DANE o del nombre), su nombre y sus datos, y le crea una sede.
- El evento se marca publicado: una segunda pasada no crea un colegio duplicado.
- Un segundo evento del MISMO colegio no lo pisa: completa los campos vacios sin
  borrar lo que el revisor ya habia puesto.
- Un evento sin `colegio_id` valido o sin nombre no da de alta nada, pero se
  marca publicado para no reintentarlo en vano.
- Un `colegio_verificado` de la cola da de alta el colegio igual que la fila de
  la bandeja, sin abrir la base del Catalogo, y un evento repetido deja la base
  igual: por eso el consumidor no guarda que eventos proceso.
- Con Postgres caido (`ConnectionRefusedError`, o `socket.gaierror` cuando el
  contenedor deja de resolver en Docker) el bucle espera, reintenta y da de alta
  el colegio cuando la base vuelve; un error de programacion lo termina.
"""

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

# La bandeja del Catalogo: la misma forma comun de bandeja (identica en todos los
# servicios), montada aqui en su propio engine (base ajena), asi que la tabla
# reflejada del poller la lee igual que en produccion.
BANDEJA_CATALOGO = bandeja_reflejada(MetaData())

COLEGIO = str(uuid.uuid4())
USUARIO_ID = str(uuid.uuid4())


async def _sembrar_usuario(motor: MotorServicio, usuario_id: str = USUARIO_ID) -> None:
    """Mete en la base propia el usuario (contacto) que 'subio' la lista. El
    poller solo matricula si este existe; en produccion lo crea `registrar_contacto`
    cuando el padre usa 'No encontre mi colegio'."""
    async with motor.sesion() as db:
        db.add(Usuario(id=uuid.UUID(usuario_id), correo=f"{usuario_id}@ejemplo.co", clave_hash="x"))


@pytest_asyncio.fixture
async def motor_catalogo() -> AsyncIterator[Any]:
    """La base AJENA del Catalogo, con solo su `bandeja_salida`. La base PROPIA
    de Identidad (fixture `motor` del conftest) tiene otra `bandeja_salida`, asi
    que esta vive en otro engine, igual que en produccion son dos bases: la
    excepcion outbox declarada."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA_CATALOGO.metadata.create_all)
    yield engine
    await engine.dispose()


_SIGUIENTE_ID = [0]


async def _sembrar_bandeja(motor_catalogo: Any, **carga: Any) -> None:
    """Mete un evento `colegio_verificado` en la bandeja del Catalogo de prueba.

    El `id` se asigna a mano: la tabla reflejada declara la PK como BigInteger y
    SQLite no la autoincrementa (solo lo hace con INTEGER), a diferencia de
    Postgres. En produccion la PK la pone el Catalogo; aqui basta con que sea
    unica y creciente para respetar el orden del `ORDER BY id` del poller."""
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
        # El id es el del evento: el mismo que el Catalogo derivo del DANE.
        assert str(colegio.id) == COLEGIO
        assert colegio.nombre == "ACADEMIA CENTRAL DE SISTEMAS"
        assert colegio.nit == "311001105731"
        # El evento no trae clave `dane`; se rescata del `nit` porque tiene la
        # forma del DANE del DUEB (12 digitos). `nit` no cambia.
        assert colegio.dane == "311001105731"
        assert colegio.direccion == "Calle 1 # 2-3"
        assert colegio.activo is True

    async def test_un_nit_que_no_es_dane_no_llena_la_columna(self, motor, motor_catalogo):
        """Si el `nit` no tiene la forma del DANE del DUEB (12 digitos), la
        columna `dane` queda vacia: no se ensucia con un NIT tributario."""
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
        assert await poller.pasada() == 0  # ya publicado: nada que hacer

        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert len(colegios) == 1

    async def test_un_segundo_evento_del_mismo_colegio_completa_sin_pisar(self, motor, motor_catalogo):
        # Primera lista: solo nombre. El revisor NO completo el logo.
        await _sembrar_bandeja(motor_catalogo, **_carga(nit=None, direccion=None))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)
        await poller.pasada()

        # Segunda lista del mismo colegio: ahora trae nit y direccion.
        await _sembrar_bandeja(motor_catalogo, **_carga(nit="311001105731", direccion="Calle 1 # 2-3"))
        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
            sedes = list(
                (await db.execute(select(Sede).where(Sede.colegio_id == uuid.UUID(COLEGIO)))).scalars()
            )
        # Los campos que estaban vacios se completaron.
        assert colegio.nit == "311001105731"
        assert colegio.direccion == "Calle 1 # 2-3"
        # No se creo una segunda sede.
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
        assert pendientes == []  # se marco publicado

    async def test_un_evento_sin_nombre_no_da_de_alta_nada(self, motor, motor_catalogo):
        await _sembrar_bandeja(motor_catalogo, **_carga(nombre="   "))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 0
        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert colegios == []


async def _contar(motor: MotorServicio) -> tuple[int, int, int]:
    """Estudiantes, matriculas y vinculos que hay en la base propia."""
    async with motor.sesion() as db:
        estudiantes = list((await db.execute(select(Estudiante))).scalars())
        matriculas = list((await db.execute(select(Matricula))).scalars())
        vinculos = list((await db.execute(select(AcudienteMatricula))).scalars())
    return len(estudiantes), len(matriculas), len(vinculos)


class TestPollerMatriculaAlHijo:
    """Cerrar el hueco de 'No encontre mi colegio': al volverse aliado el colegio,
    el hijo del padre que subio la lista queda matriculado (reusa la funcion del
    registro), de forma idempotente y con el apodo vacio."""

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
        # (colegio, "Sede principal", grado, año actual): el año es el mismo que el
        # registro, para que el id derivado coincida y no se duplique.
        assert matricula.grado == "Cuarto"
        assert matricula.anio_lectivo == datetime.now(UTC).year
        assert vinculo.matricula_id == matricula.id
        assert vinculo.es_principal is True
        assert vinculo.parentesco == "acudiente"
        # Un estudiante, una matricula, un vinculo.
        assert await _contar(motor) == (1, 1, 1)

    async def test_una_segunda_pasada_no_duplica_la_matricula(self, motor, motor_catalogo):
        await _sembrar_usuario(motor)
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1
        assert await poller.pasada() == 0  # ya publicado: nada que hacer

        assert await _contar(motor) == (1, 1, 1)

    async def test_sin_contacto_referencia_crea_colegio_pero_no_matricula(self, motor, motor_catalogo):
        # Onboarding administrativo: sin padre esperando, el evento no trae la clave.
        await _sembrar_bandeja(motor_catalogo, **_carga())
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert len(colegios) == 1
        assert await _contar(motor) == (0, 0, 0)

    async def test_con_padre_inexistente_crea_colegio_pero_no_matricula(self, motor, motor_catalogo):
        # El evento trae la referencia pero el usuario no existe en Identidad: no se
        # inventa una cuenta desde el poller. El colegio si se da de alta.
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        assert await poller.pasada() == 1

        async with motor.sesion() as db:
            colegios = list((await db.execute(select(Colegio))).scalars())
        assert len(colegios) == 1
        assert await _contar(motor) == (0, 0, 0)

    async def test_idempotencia_entre_eventos_repetidos(self, motor, motor_catalogo):
        # Dos eventos identicos en un mismo lote: el SELECT-then-INSERT de
        # `_materializar_hijos` cae en los mismos id derivados y no duplica.
        await _sembrar_usuario(motor)
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        await _sembrar_bandeja(motor_catalogo, **_carga(contacto_referencia=USUARIO_ID))
        poller = Poller(motor_identidad=motor, motor_catalogo=motor_catalogo)

        await poller.pasada()

        assert await _contar(motor) == (1, 1, 1)


class TestPollerConsumeLaColaConRabbitmq:
    """Con dobles y sin broker; el viaje por un RabbitMQ de verdad esta en las
    pruebas de punta a punta. Con broker no hay motor del Catalogo."""

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

        # Toda base ajena se abre por `url_desde_entorno` (la regla de fronteras
        # lo exige); si el camino con broker llegara a ella, esta prueba cae.
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


# ------------------------------------------------------------ bucle resiliente

_INTERVALO = 5.0


class _Corte(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


class _Intermitente:
    """Un motor cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion, como asyncpg
    con Postgres caido; despues delega en el motor de verdad. No se cierra:
    `correr_una_vez` cierra sus motores en cada vuelta, y la base en memoria de
    la prueba se perderia.
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
    """La base propia y la del Catalogo de la prueba, por las fronteras publicas
    del modulo: `crear_motor` (la propia) y `create_async_engine` sobre la URL
    que deriva `url_desde_entorno` (la ajena)."""
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

        # Retroceso exponencial desde la espera inicial del bucle comun, y al
        # volver la base, el intervalo normal.
        e = ESPERA_INICIAL_BUCLE
        assert esperas == [e, 2 * e, 4 * e, _INTERVALO]
        async with motor.sesion() as db:
            colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
        assert colegio.nombre == "Colegio Ficticio de Prueba"
        async with motor_catalogo.begin() as conexion:
            publicado = await conexion.scalar(select(BANDEJA_CATALOGO.c.publicado_en))
        assert publicado is not None
        # Cada vuelta reabre la base ajena (la del Catalogo), y solo esa.
        assert set(urls) == {"prueba://catalogo"}

    async def test_un_error_de_programacion_termina_el_poller(self, motor, motor_catalogo, monkeypatch):
        _conectar(monkeypatch, motor, _Intermitente(motor_catalogo, ValueError("bug")))
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await modulo._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == []

    async def test_el_bucle_duerme_con_el_asyncio_sleep_de_cuando_corre(self, monkeypatch):
        # Sin `dormir`, el bucle usa el `asyncio.sleep` que ve el modulo al correr,
        # no el de cuando se definio: asi lo sustituyen las pruebas de los procesos.
        vueltas: list[int] = []

        async def _nada() -> int:
            # Si el bucle durmiera con el `asyncio.sleep` de verdad, la segunda vuelta corta.
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
