"""El poller de `colegio_verificado`: aprobar la lista de un colegio nuevo lo
da de alta como aliado en Identidad.

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
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest_asyncio
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_identidad.modelos import (
    AcudienteMatricula,
    Base,
    Colegio,
    Estudiante,
    Matricula,
    Sede,
    Usuario,
)
from tukit_identidad.poller import Poller, _bandeja_reflejada

# La bandeja del Catalogo: la misma forma comun de bandeja (identica en todos los
# servicios), montada aqui en su propio engine (base ajena), asi que la tabla
# reflejada del poller la lee igual que en produccion.
BANDEJA_CATALOGO = _bandeja_reflejada()

COLEGIO = str(uuid.uuid4())
USUARIO_ID = str(uuid.uuid4())


async def _sembrar_usuario(motor: MotorServicio, usuario_id: str = USUARIO_ID) -> None:
    """Mete en la base propia el usuario (contacto) que 'subio' la lista. El
    poller solo matricula si este existe; en produccion lo crea `registrar_contacto`
    cuando el padre usa 'No encontre mi colegio'."""
    async with motor.sesion() as db:
        db.add(Usuario(id=uuid.UUID(usuario_id), correo=f"{usuario_id}@ejemplo.co", clave_hash="x"))


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    """Un `MotorServicio` sobre SQLite en memoria, con el mismo API del runtime.

    Es la base PROPIA de Identidad (donde se da de alta el colegio); su propia
    `bandeja_salida` tiene otra forma, asi que la bandeja del Catalogo vive en un
    motor aparte —igual que en produccion son dos bases distintas—."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="identidad", engine=engine, _fabrica=fabrica)
    await engine.dispose()


@pytest_asyncio.fixture
async def motor_catalogo() -> AsyncIterator[Any]:
    """La base AJENA del Catalogo, con solo su `bandeja_salida`. En produccion es
    otra base; aqui es otro engine, la excepcion outbox declarada."""
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
            colegio = (
                await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))
            ).scalar_one()
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
            colegio = (
                await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))
            ).scalar_one()
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
            colegio = (
                await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))
            ).scalar_one()
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
                await db.execute(
                    select(Matricula).where(Matricula.colegio_id == uuid.UUID(COLEGIO))
                )
            ).scalar_one()
            vinculo = (
                await db.execute(
                    select(AcudienteMatricula).where(
                        AcudienteMatricula.usuario_id == uuid.UUID(USUARIO_ID)
                    )
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
