"""El barrido de supresiones atascadas en `propagando` (ADR 0048, Ley 1581 art. 15).

Lo que no puede romperse en silencio: que una solicitud atascada se reenvie y se
avise, que reenviar no duplique ni inunde la bandeja, y que una solicitud ya
cerrada no se toque nunca.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_identidad.barrido_supresion import barrer, vence_el
from tukit_identidad.modelos import BandejaSalida, Base, SolicitudSupresion, Usuario
from tukit_identidad.repositorios import RepoIdentidad

TITULAR = uuid.uuid4()
# Un lunes, para que los plazos en dias habiles se lean sin calendario a mano.
RECIBIDA = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="identidad", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def _solicitud(motor: MotorServicio, *, confirmados: tuple[str, ...] = ()) -> uuid.UUID:
    """Una solicitud real (por `suprimir_titular`), fechada en RECIBIDA y con su envio ya publicado."""
    async with motor.sesion() as db:
        db.add(Usuario(id=TITULAR, correo="ana@ejemplo.com", clave_hash="x"))
    async with motor.engine.begin() as conexion:
        solicitud = await RepoIdentidad(conexion).suprimir_titular(
            TITULAR, correo_nuevo="suprimido@tukit.invalid"
        )
    async with motor.sesion() as db:
        await db.execute(
            update(SolicitudSupresion)
            .where(SolicitudSupresion.id == solicitud)
            .values(creado_en=RECIBIDA, suscriptores_confirmados=list(confirmados))
        )
        await db.execute(update(BandejaSalida).values(creado_en=RECIBIDA, publicado_en=RECIBIDA))
    return solicitud


async def _envios(motor: MotorServicio) -> list[BandejaSalida]:
    async with motor.sesion() as db:
        return list((await db.execute(select(BandejaSalida).order_by(BandejaSalida.id))).scalars())


def test_el_plazo_son_quince_dias_habiles_sin_contar_el_dia_del_recibo():
    # Lunes 5 oct: el dia 1 es el martes 6; 15 dias habiles caen el lunes 26.
    assert vence_el(RECIBIDA) == date(2026, 10, 26)
    # Un sabado: el primer dia habil es el lunes siguiente.
    assert vence_el(datetime(2026, 10, 10, 12, 0, tzinfo=UTC)) == date(2026, 10, 30)


def test_el_plazo_cuenta_con_la_hora_de_bogota():
    # 03:00 UTC del martes es todavia el lunes 5 en Bogota (UTC-5).
    assert vence_el(datetime(2026, 10, 6, 3, 0, tzinfo=UTC)) == date(2026, 10, 26)


async def test_no_toca_lo_reciente(motor):
    await _solicitud(motor)

    reporte = await barrer(motor, ahora=RECIBIDA + timedelta(minutes=10))

    assert (reporte.revisadas, reporte.reenviadas, reporte.vencidas) == (1, [], [])
    assert len(await _envios(motor)) == 1


async def test_reenvia_el_evento_con_la_misma_carga_y_los_servicios_que_faltan(motor):
    solicitud = await _solicitud(motor, confirmados=("comercio",))

    reporte = await barrer(motor, ahora=RECIBIDA + timedelta(hours=2))

    assert reporte.reenviadas == [str(solicitud)]
    original, reenvio = await _envios(motor)
    assert (reenvio.tipo, reenvio.agregado_id, reenvio.publicado_en) == ("titular_suprimido", solicitud, None)
    assert reenvio.carga["usuario_id"] == str(TITULAR)
    assert reenvio.carga["solicitud_id"] == str(solicitud)
    assert reenvio.carga["pendientes"] == ["inteligencia", "operacion"]
    assert reenvio.carga["reenvio"] == 1
    assert original.carga["solicitud_id"] == reenvio.carga["solicitud_id"]


async def test_no_acumula_reenvios_mientras_el_anterior_no_haya_salido(motor):
    await _solicitud(motor)
    await barrer(motor, ahora=RECIBIDA + timedelta(hours=2))

    reporte = await barrer(motor, ahora=RECIBIDA + timedelta(hours=5))

    assert reporte.reenviadas == []
    assert len(reporte.sin_publicar) == 1
    assert len(await _envios(motor)) == 2


async def test_vuelve_a_reenviar_cuando_el_envio_anterior_ya_salio_y_paso_el_intervalo(motor):
    await _solicitud(motor)
    await barrer(motor, ahora=RECIBIDA + timedelta(hours=2))
    async with motor.sesion() as db:
        await db.execute(update(BandejaSalida).values(publicado_en=RECIBIDA + timedelta(hours=2)))

    assert (await barrer(motor, ahora=RECIBIDA + timedelta(hours=2, minutes=30))).reenviadas == []
    reporte = await barrer(motor, ahora=RECIBIDA + timedelta(hours=4))

    assert len(reporte.reenviadas) == 1
    assert [e.carga.get("reenvio") for e in await _envios(motor)][-1] == 2


async def test_avisa_la_solicitud_vencida_con_nivel_error(motor, caplog):
    solicitud = await _solicitud(motor, confirmados=("comercio", "operacion"))
    despues_del_plazo = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)  # martes 27, un dia habil tarde

    with caplog.at_level(logging.WARNING):
        reporte = await barrer(motor, ahora=despues_del_plazo)

    assert reporte.vencidas == [str(solicitud)]
    [aviso] = [r for r in caplog.records if r.levelno == logging.ERROR and "vencida" in r.getMessage()]
    assert str(solicitud) in aviso.getMessage() and "faltan=inteligencia" in aviso.getMessage()


async def test_la_vencida_se_avisa_una_sola_vez_en_el_bucle(motor, caplog):
    solicitud = await _solicitud(motor, confirmados=("comercio", "operacion"))
    despues_del_plazo = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)
    avisadas: set[str] = set()

    with caplog.at_level(logging.WARNING):
        primera = await barrer(motor, ahora=despues_del_plazo, ya_avisadas=avisadas)
        segunda = await barrer(motor, ahora=despues_del_plazo + timedelta(minutes=15), ya_avisadas=avisadas)

    # El reporte sigue listandola (esta vencida), pero el ERROR sale una vez.
    assert primera.vencidas == segunda.vencidas == [str(solicitud)]
    errores = [r for r in caplog.records if r.levelno == logging.ERROR and "vencida" in r.getMessage()]
    assert len(errores) == 1


async def test_el_ultimo_dia_del_plazo_todavia_no_esta_vencido(motor):
    await _solicitud(motor)

    reporte = await barrer(motor, ahora=datetime(2026, 10, 26, 22, 0, tzinfo=UTC))

    assert reporte.vencidas == []


async def test_una_solicitud_cerrada_no_se_toca(motor):
    solicitud = await _solicitud(motor)
    async with motor.sesion() as db:
        await db.execute(
            update(SolicitudSupresion)
            .where(SolicitudSupresion.id == solicitud)
            .values(estado="completada", resuelto_en=RECIBIDA + timedelta(minutes=1))
        )

    reporte = await barrer(motor, ahora=RECIBIDA + timedelta(days=60))

    assert reporte.revisadas == 0
    assert len(await _envios(motor)) == 1


async def test_con_las_tres_confirmaciones_no_reenvia_ni_cierra(motor, caplog):
    solicitud = await _solicitud(motor, confirmados=("comercio", "operacion", "inteligencia"))

    with caplog.at_level(logging.WARNING):
        reporte = await barrer(motor, ahora=RECIBIDA + timedelta(days=2))

    assert reporte.reenviadas == []
    assert any("tres confirmaciones" in r.getMessage() for r in caplog.records)
    async with motor.sesion() as db:
        assert (await db.get(SolicitudSupresion, solicitud)).estado == "propagando"


async def test_deja_de_reenviar_al_llegar_al_tope(motor):
    solicitud = await _solicitud(motor)
    async with motor.sesion() as db:
        for _ in range(3):
            db.add(
                BandejaSalida(
                    tipo="titular_suprimido",
                    agregado_tipo="solicitud_supresion",
                    agregado_id=solicitud,
                    carga={},
                    creado_en=RECIBIDA,
                    publicado_en=RECIBIDA,
                )
            )

    reporte = await barrer(motor, ahora=RECIBIDA + timedelta(hours=3), max_reenvios=2)

    assert reporte.reenviadas == []
    assert reporte.sin_reenvios == [str(solicitud)]
