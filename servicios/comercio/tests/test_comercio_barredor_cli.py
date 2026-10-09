"""NFR-MAN-01: el barredor de reservas vencidas como proceso: TTL por entorno, limite, CLI y bucle.

`test_barredor.py` ya fija la decision (que reserva vence, que pedido se cancela). Aqui se
caracteriza lo que lo rodea y que, si se rompe, deja inventario bloqueado sin que nadie se
entere: el TTL que sale de `TUKIT_TTL_RESERVA_MIN`, el tope por pasada, el reloj real cuando no se
inyecta `ahora`, el cierre del motor aunque la pasada falle, el bucle `--seguir` (imprime solo
cuando libero algo y duerme el intervalo pedido) y la invocacion real `python -m
tukit_comercio.barredor` contra una base SQLite en archivo.

Sin red y sin esperas: el reloj y el `sleep` se inyectan; el unico motor "externo" es un archivo
SQLite en `tmp_path`.
"""

from __future__ import annotations

import asyncio
import runpy
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comercio import barredor
from tukit_comercio.dominio.saga import TTL_RESERVA
from tukit_comercio.modelos import Base, EstadoPedido, Pedido, ReservaInventario

pytestmark = pytest.mark.nfr("NFR-MAN-01")

AHORA = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
PEDIDO = Pedido.__table__
RESERVA = ReservaInventario.__table__


@pytest_asyncio.fixture
async def motor():
    m = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with m.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield m
    await m.dispose()


async def _sembrar(
    motor,
    *,
    edad_min: float,
    reservas: int = 1,
    pedido_estado: str = "pendiente_pago",
    ahora: datetime = AHORA,
) -> uuid.UUID:
    """Un pedido con `reservas` reservas activas, todas de la misma edad."""
    pid = uuid.uuid4()
    async with motor.begin() as conexion:
        await conexion.execute(
            PEDIDO.insert().values(
                id=pid, usuario_id=uuid.uuid4(), total=0, hijos=1, colegios=["C"], estado=pedido_estado
            )
        )
        for _ in range(reservas):
            await conexion.execute(
                RESERVA.insert().values(
                    id=uuid.uuid4(),
                    pedido_id=pid,
                    producto_canonico_id=uuid.uuid4(),
                    cantidad=1,
                    estado="activa",
                    creado_en=ahora - timedelta(minutes=edad_min),
                )
            )
    return pid


async def _estados(motor, pid: uuid.UUID) -> tuple[str, list[str]]:
    async with motor.begin() as conexion:
        pedido = await conexion.scalar(select(PEDIDO.c.estado).where(PEDIDO.c.id == pid))
        reservas = list(await conexion.scalars(select(RESERVA.c.estado).where(RESERVA.c.pedido_id == pid)))
    return pedido, reservas


# --- el TTL sale del entorno --------------------------------------------------------------------


def test_ttl_por_omision_es_el_del_dominio(monkeypatch):
    """Sin variable, el TTL es el conservador del dominio (30 min): nadie lo cambia por accidente."""
    monkeypatch.delenv("TUKIT_TTL_RESERVA_MIN", raising=False)
    assert barredor._ttl() == TTL_RESERVA == timedelta(minutes=30)


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [("5", timedelta(minutes=5)), ("2.5", timedelta(seconds=150)), ("", TTL_RESERVA)],
)
def test_ttl_del_entorno_se_lee_en_minutos_fraccionarios(monkeypatch, crudo, esperado):
    """`TUKIT_TTL_RESERVA_MIN` va en minutos y admite fracciones; vacia equivale a no definirla."""
    monkeypatch.setenv("TUKIT_TTL_RESERVA_MIN", crudo)
    assert barredor._ttl() == esperado


async def test_el_ttl_del_entorno_decide_que_reserva_vence(motor, monkeypatch):
    """Una reserva de 10 min sobrevive al TTL por omision y vence al bajarlo a 5 min por entorno."""
    pid = await _sembrar(motor, edad_min=10)

    monkeypatch.delenv("TUKIT_TTL_RESERVA_MIN", raising=False)
    assert await barredor.pasada(motor, ahora=AHORA) == 0
    assert await _estados(motor, pid) == ("pendiente_pago", ["activa"])

    monkeypatch.setenv("TUKIT_TTL_RESERVA_MIN", "5")
    assert await barredor.pasada(motor, ahora=AHORA) == 1
    assert await _estados(motor, pid) == (EstadoPedido.CANCELADO.value, ["liberada"])


# --- la pasada: conteo, tope y reloj ------------------------------------------------------------


async def test_pedido_con_varias_reservas_libera_todas_y_cuenta_reservas_no_pedidos(motor):
    """El conteo devuelto es de RESERVAS liberadas; el pedido abandonado se cancela una sola vez
    y las reservas de otro pedido todavia vigente no se tocan."""
    abandonado = await _sembrar(motor, edad_min=45, reservas=3)
    reciente = await _sembrar(motor, edad_min=5, reservas=2)

    liberadas = await barredor.pasada(motor, ahora=AHORA)

    assert liberadas == 3
    assert await _estados(motor, abandonado) == (EstadoPedido.CANCELADO.value, ["liberada"] * 3)
    assert await _estados(motor, reciente) == ("pendiente_pago", ["activa"] * 2)


async def test_el_limite_acota_la_pasada_y_la_siguiente_termina_el_trabajo(motor):
    """`limite` topa las filas que una pasada toma; lo que quedo se barre en la pasada siguiente."""
    a = await _sembrar(motor, edad_min=60)
    b = await _sembrar(motor, edad_min=60)

    assert await barredor.pasada(motor, ahora=AHORA, limite=1) == 1
    pedidos_cancelados = [(await _estados(motor, pid))[0] == EstadoPedido.CANCELADO.value for pid in (a, b)]
    assert sorted(pedidos_cancelados) == [False, True]

    assert await barredor.pasada(motor, ahora=AHORA, limite=1) == 1
    assert await barredor.pasada(motor, ahora=AHORA, limite=1) == 0
    for pid in (a, b):
        assert await _estados(motor, pid) == (EstadoPedido.CANCELADO.value, ["liberada"])


async def test_sin_ahora_inyectado_la_pasada_usa_el_reloj_real(motor):
    """En produccion no se inyecta `ahora`: una reserva de hace 2 h ya vencio y una de hace 1 min no."""
    ahora_real = datetime.now(UTC)
    vieja = await _sembrar(motor, edad_min=120, ahora=ahora_real)
    fresca = await _sembrar(motor, edad_min=1, ahora=ahora_real)

    assert await barredor.pasada(motor) == 1
    assert (await _estados(motor, vieja))[0] == EstadoPedido.CANCELADO.value
    assert await _estados(motor, fresca) == ("pendiente_pago", ["activa"])


# --- correr_una_vez: abre un motor propio y lo cierra siempre -----------------------------------


class _MotorEspia:
    """Doble de `MotorServicio`: expone `.engine` y registra el cierre."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


async def test_correr_una_vez_devuelve_el_conteo_y_cierra_el_motor(motor, monkeypatch):
    espia = _MotorEspia(motor)
    monkeypatch.setattr(barredor, "crear_motor", lambda servicio: espia)
    ahora_real = datetime.now(UTC)
    pid = await _sembrar(motor, edad_min=90, reservas=2, ahora=ahora_real)

    assert await barredor.correr_una_vez() == 2
    assert espia.cerrado is True
    assert (await _estados(motor, pid))[0] == EstadoPedido.CANCELADO.value


async def test_correr_una_vez_cierra_el_motor_aunque_la_pasada_falle(monkeypatch):
    """Si la pasada revienta (base sin esquema) el motor igual se cierra: no se filtran conexiones."""
    vacio = create_async_engine("sqlite+aiosqlite:///:memory:")
    espia = _MotorEspia(vacio)
    monkeypatch.setattr(barredor, "crear_motor", lambda servicio: espia)
    try:
        with pytest.raises(OperationalError):
            await barredor.correr_una_vez()
    finally:
        await vacio.dispose()
    assert espia.cerrado is True


# --- el bucle y la CLI --------------------------------------------------------------------------


class _Detener(Exception):
    """Corta el bucle infinito desde el `sleep` inyectado."""


async def test_el_bucle_imprime_solo_cuando_libero_y_duerme_el_intervalo(monkeypatch, capsys):
    """`--seguir`: una linea por pasada que libero algo, silencio en la que no, y `sleep(intervalo)`."""
    resultados = iter([2, 0])

    async def _pasada_falsa() -> int:
        return next(resultados)

    dormidos: list[float] = []

    async def _dormir(segundos: float) -> None:
        dormidos.append(segundos)
        if len(dormidos) == 2:
            raise _Detener

    monkeypatch.setattr(barredor, "correr_una_vez", _pasada_falsa)
    monkeypatch.setattr(asyncio, "sleep", _dormir)

    with pytest.raises(_Detener):
        await barredor._bucle(7.5)

    assert dormidos == [7.5, 7.5]
    assert capsys.readouterr().out == "[barredor] reservas vencidas liberadas: 2\n"


@pytest.mark.parametrize(
    ("argv", "intervalo"),
    [(["--seguir"], 60.0), (["--seguir", "--intervalo", "5"], 5.0)],
)
def test_main_con_seguir_entra_al_bucle_con_el_intervalo_pedido(monkeypatch, argv, intervalo):
    """`--seguir` delega en el bucle (60 s por omision) y NO hace la pasada unica."""
    recibido: list[float] = []

    async def _bucle_falso(valor: float) -> None:
        recibido.append(valor)

    async def _no_debe_correr() -> int:
        raise AssertionError("con --seguir no hay pasada unica")

    monkeypatch.setattr(barredor, "_bucle", _bucle_falso)
    monkeypatch.setattr(barredor, "correr_una_vez", _no_debe_correr)

    assert barredor.main(argv) == 0
    assert recibido == [intervalo]


def test_main_rechaza_un_intervalo_que_no_es_numero():
    """argparse corta con codigo 2 antes de tocar la base."""
    with pytest.raises(SystemExit) as salida:
        barredor.main(["--seguir", "--intervalo", "mucho"])
    assert salida.value.code == 2


@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_python_m_barredor_libera_contra_una_base_real_y_sale_con_cero(tmp_path, monkeypatch, capsys):
    """`python -m tukit_comercio.barredor` de punta a punta: lee la URL del entorno, barre una
    base SQLite en archivo, imprime el conteo y termina con `SystemExit(0)`."""
    archivo = tmp_path / "comercio.db"
    url = f"sqlite+aiosqlite:///{archivo}"

    async def _preparar() -> uuid.UUID:
        engine = create_async_engine(url)
        async with engine.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)
        pid = await _sembrar(engine, edad_min=120, reservas=2, ahora=datetime.now(UTC))
        await engine.dispose()
        return pid

    async def _leer(pid: uuid.UUID) -> tuple[str, list[str]]:
        engine = create_async_engine(url)
        try:
            return await _estados(engine, pid)
        finally:
            await engine.dispose()

    pid = asyncio.run(_preparar())
    monkeypatch.setenv("TUKIT_COMERCIO_DB_URL", url)
    monkeypatch.delenv("TUKIT_TTL_RESERVA_MIN", raising=False)
    monkeypatch.setattr(sys, "argv", ["tukit_comercio.barredor"])

    with pytest.raises(SystemExit) as salida:
        runpy.run_module("tukit_comercio.barredor", run_name="__main__")

    assert salida.value.code == 0
    assert capsys.readouterr().out == "[barredor] reservas vencidas liberadas: 2\n"
    assert asyncio.run(_leer(pid)) == (EstadoPedido.CANCELADO.value, ["liberada", "liberada"])
