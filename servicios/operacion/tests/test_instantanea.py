"""El snapshot diario de metricas de calidad (`instantanea`) y su lectura.

Se prueba lo unico no trivial: (1) el mapeo puro de agregados a filas
(`_filas_de_snapshot`) —que solo cuenta colegios con actividad y guarda la
cobertura en puntos base—, y (2) que reescribir el dia sea idempotente (correrlo
dos veces deja lo mismo, no lo duplica). El cliente HTTP se sustituye por un
doble en memoria; no se levanta ningun servicio.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.instantanea import _a_bps, _filas_de_snapshot, escribir_instantanea
from tukit_operacion.modelos import Base

METRICA = Base.metadata.tables["metrica_diaria"]

HOY = date(2026, 9, 25)

_RESUMEN = {
    "conceptos": 120,
    "productos": 385,
    "conceptos_con_tres_niveles": 40,
    "conceptos_sin_producto": 12,
    "productos_con_foto": 300,
    "tiendas": 8,
    "productos_sin_revisar": 5,
}

# Un colegio con actividad y otro sin kits: el segundo no debe aportar filas.
_METRICAS = [
    {
        "colegio_id": "col-1",
        "kits_armados": 3,
        "lineas_comprables": 26,
        "lineas_resueltas": 24,
        "cobertura": 0.9231,
        "ahorro_total_cop": 45000,
    },
    {
        "colegio_id": "col-2",
        "kits_armados": 0,
        "lineas_comprables": 0,
        "lineas_resueltas": 0,
        "cobertura": 0.0,
        "ahorro_total_cop": 0,
    },
]


class MetricasFalsas:
    """Devuelve agregados fijos sin salir a la red."""

    def __init__(self, resumen=_RESUMEN, colegios=None, metricas=None) -> None:
        self.resumen = resumen
        if colegios is None:
            colegios = [{"colegio_id": "col-1"}, {"colegio_id": "col-2"}]
        self._colegios = colegios
        self._metricas = {m["colegio_id"]: m for m in (metricas if metricas is not None else _METRICAS)}

    async def resumen_catalogo(self):
        return self.resumen

    async def colegios(self):
        return self._colegios

    async def metricas_colegio(self, colegio_id: str):
        return self._metricas.get(colegio_id)


def test_a_bps_redondea_a_puntos_base():
    assert _a_bps(0.9231) == 9231
    assert _a_bps(0.0) == 0
    assert _a_bps(1.0) == 10000
    # Fuera de rango se recorta, no explota.
    assert _a_bps(1.5) == 10000
    assert _a_bps(-0.2) == 0


def test_filas_solo_incluye_colegios_con_kits():
    filas = _filas_de_snapshot(HOY, _RESUMEN, _METRICAS)
    colegios = {f["dimension_id"] for f in filas if f["dimension"] == "colegio"}
    assert colegios == {"col-1"}  # col-2 no tiene kits -> no aporta traza

    # La cobertura del colegio activo va en puntos base.
    cobertura = [f["valor"] for f in filas if f["dimension"] == "colegio" and f["metrica"] == "cobertura_bps"]
    assert cobertura == [9231]

    # Las siete cifras del catalogo se congelan como conteo directo.
    catalogo = {f["metrica"]: f["valor"] for f in filas if f["dimension"] == "catalogo"}
    assert catalogo["productos"] == 385
    assert catalogo["conceptos"] == 120

    # El top-line global agrega sobre lo comprable de los colegios activos.
    global_ = {f["metrica"]: f["valor"] for f in filas if f["dimension"] == "global"}
    assert global_["colegios_activos"] == 1
    assert global_["cobertura_bps"] == _a_bps(24 / 26)


def test_catalogo_caido_no_congela_filas_de_catalogo():
    filas = _filas_de_snapshot(HOY, None, _METRICAS)
    assert not [f for f in filas if f["dimension"] == "catalogo"]
    # Pero los colegios con actividad si se congelan: snapshot parcial valido.
    assert [f for f in filas if f["dimension"] == "colegio"]


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def test_escribir_es_idempotente(motor):
    cliente = MetricasFalsas()

    primero = await escribir_instantanea(motor, cliente, HOY)
    assert primero["filas"] > 0
    assert primero["colegios_con_metricas"] == 2  # ambos devuelven metricas...
    # ...pero solo col-1 aporta filas (col-2 sin kits).

    # Correrlo de nuevo el mismo dia deja EXACTAMENTE lo mismo, no lo duplica.
    segundo = await escribir_instantanea(motor, cliente, HOY)
    assert segundo["filas"] == primero["filas"]

    async with motor.sesion() as db:
        conexion = await db.connection()
        total = await conexion.scalar(select(func.count()).select_from(METRICA))
    assert total == primero["filas"]


@pytest_asyncio.fixture
async def cliente_http(motor) -> AsyncIterator[httpx.AsyncClient]:
    app.state.motor = motor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


async def test_series_devuelve_lo_congelado(motor, cliente_http):
    await escribir_instantanea(motor, MetricasFalsas(), HOY)

    respuesta = await cliente_http.get("/v1/operacion/metricas", params={"dimension": "colegio"})
    assert respuesta.status_code == 200
    puntos = respuesta.json()["puntos"]
    assert puntos  # hay traza
    assert all(p["dimension"] == "colegio" for p in puntos)
    assert {p["dimension_id"] for p in puntos} == {"col-1"}


async def test_series_vacia_sin_snapshots(cliente_http):
    respuesta = await cliente_http.get("/v1/operacion/metricas")
    assert respuesta.status_code == 200
    assert respuesta.json()["puntos"] == []


async def test_series_desde_invalida_da_422(cliente_http):
    # `desde` que no es fecha ISO no es una serie vacia: es una entrada mala.
    respuesta = await cliente_http.get("/v1/operacion/metricas", params={"desde": "no-es-fecha"})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "fecha_invalida"


async def test_series_desde_valida_acota_por_fecha(motor, cliente_http):
    # Dos dias congelados; `desde` el dia de hoy deja fuera el snapshot viejo.
    ayer = date(HOY.year, HOY.month, HOY.day - 1)
    await escribir_instantanea(motor, MetricasFalsas(), ayer)
    await escribir_instantanea(motor, MetricasFalsas(), HOY)

    respuesta = await cliente_http.get("/v1/operacion/metricas", params={"desde": HOY.isoformat()})
    assert respuesta.status_code == 200
    fechas = {p["fecha"] for p in respuesta.json()["puntos"]}
    assert fechas == {HOY.isoformat()}
