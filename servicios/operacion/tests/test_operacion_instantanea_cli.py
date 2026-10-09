"""NFR-MAN-01: el snapshot diario de metricas: filas, reescritura del dia, `_correr` y linea de comandos.

`test_instantanea.py` fija el camino feliz (colegios con kits, cobertura en puntos
base, idempotencia con los mismos datos). Aqui se cierran los bordes: que filas
NO se congelan (colegio sin id, sin kits, cifras nulas), que la cobertura global
pese por lineas y no promedie coberturas, que un dia reescrito conserve los demas
y sea atomico (si el insert revienta no se pierde el snapshot previo), que
`_correr` cierre su motor aunque falle, y que `main` ponga el dia en UTC e imprima
el reporte. Los servicios de metricas son dobles en memoria; no sale ninguna peticion.

Importa porque las cifras de CALIDAD no se pueden volver a medir (el catalogo
cambia): el snapshot es la unica traza de como mejora el algoritmo. Un borrado que
no deba ocurrir es una perdida irrecuperable. Se caracteriza un defecto asi: una
segunda corrida del mismo dia con los servicios caidos borra lo ya congelado.
"""

from __future__ import annotations

import re
import runpy
import sqlite3
import sys
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun import bd
from tukit_comun.bd import MotorServicio
from tukit_operacion import instantanea, remoto
from tukit_operacion.instantanea import (
    _CAMPOS_CATALOGO,
    _a_bps,
    _correr,
    _filas_de_snapshot,
    escribir_instantanea,
    main,
)
from tukit_operacion.modelos import Base

pytestmark = pytest.mark.nfr("NFR-MAN-01")

METRICA = Base.metadata.tables["metrica_diaria"]
HOY = date(2026, 9, 25)
AYER = date(2026, 9, 24)

RESUMEN = {campo: indice + 1 for indice, campo in enumerate(_CAMPOS_CATALOGO)}


def _colegio(
    cid: Any = "col-1",
    *,
    kits: Any = 2,
    comprables: Any = 10,
    resueltas: Any = 5,
    cobertura: Any = 0.5,
    ahorro: Any = 1000,
) -> dict[str, Any]:
    return {
        "colegio_id": cid,
        "kits_armados": kits,
        "lineas_comprables": comprables,
        "lineas_resueltas": resueltas,
        "cobertura": cobertura,
        "ahorro_total_cop": ahorro,
    }


def _por_clave(filas: list[dict[str, Any]]) -> dict[tuple[str, str | None, str], int]:
    return {(f["dimension"], f["dimension_id"], f["metrica"]): f["valor"] for f in filas}


class TestFilasDeSnapshot:
    def test_nada_leido_no_arma_ninguna_fila(self):
        assert _filas_de_snapshot(HOY, None, []) == []

    def test_las_siete_cifras_del_catalogo_se_congelan_por_nombre(self):
        filas = _filas_de_snapshot(HOY, RESUMEN, [])

        assert [f["metrica"] for f in filas] == list(_CAMPOS_CATALOGO)
        assert {(f["dimension"], f["dimension_id"], f["fecha"]) for f in filas} == {("catalogo", None, HOY)}
        assert [f["valor"] for f in filas] == [1, 2, 3, 4, 5, 6, 7]

    def test_un_catalogo_que_responde_vacio_congela_ceros_a_diferencia_de_uno_caido(self):
        """`{}` es una medicion (el corpus esta vacio); `None` es "no pude medir"."""
        con_ceros = _filas_de_snapshot(HOY, {"productos": 5, "tiendas": None}, [])

        assert len(con_ceros) == len(_CAMPOS_CATALOGO)
        assert {f["metrica"]: f["valor"] for f in con_ceros} == {
            campo: {"productos": 5}.get(campo, 0) for campo in _CAMPOS_CATALOGO
        }
        assert _filas_de_snapshot(HOY, None, []) == []

    def test_un_colegio_activo_aporta_sus_cinco_cifras(self):
        filas = _filas_de_snapshot(HOY, None, [_colegio("col-1", kits=3, cobertura=0.9231, ahorro=45000)])

        assert {m: v for (d, i, m), v in _por_clave(filas).items() if d == "colegio" and i == "col-1"} == {
            "kits_armados": 3,
            "lineas_comprables": 10,
            "lineas_resueltas": 5,
            "cobertura_bps": 9231,
            "ahorro_cop": 45000,
        }

    @pytest.mark.parametrize(
        "colegio",
        [
            pytest.param({"kits_armados": 3}, id="sin-clave-colegio_id"),
            pytest.param(_colegio(None), id="id-nulo"),
            pytest.param(_colegio(""), id="id-vacio"),
            pytest.param(_colegio(kits=0), id="sin-kits"),
            pytest.param(_colegio(kits=None), id="kits-nulo"),
            pytest.param(_colegio(kits=-2), id="kits-negativos"),
        ],
    )
    def test_un_colegio_sin_id_o_sin_actividad_no_deja_traza_ni_global(self, colegio):
        assert _filas_de_snapshot(HOY, None, [colegio]) == []

    def test_el_id_numerico_se_guarda_como_texto(self):
        filas = _filas_de_snapshot(HOY, None, [_colegio(7)])

        assert {f["dimension_id"] for f in filas if f["dimension"] == "colegio"} == {"7"}

    def test_la_cobertura_global_pesa_por_lineas_y_no_promedia_coberturas(self):
        """Un colegio pequeno al 100 % y uno grande al 0 % no dan 50 %: dan 10 % de las lineas."""
        pequeno = _colegio("col-1", comprables=10, resueltas=10, cobertura=1.0)
        grande = _colegio("col-2", comprables=90, resueltas=0, cobertura=0.0)

        global_ = _por_clave(_filas_de_snapshot(HOY, None, [pequeno, grande]))

        assert global_[("global", None, "cobertura_bps")] == 1000
        assert global_[("global", None, "colegios_activos")] == 2

    def test_colegios_activos_sin_lineas_comprables_dan_cobertura_global_cero_sin_dividir(self):
        filas = _por_clave(_filas_de_snapshot(HOY, None, [_colegio(comprables=0, resueltas=0, cobertura=0)]))

        assert filas[("global", None, "cobertura_bps")] == 0
        assert filas[("global", None, "colegios_activos")] == 1

    @pytest.mark.parametrize(
        ("cobertura", "esperado"),
        [(1.7, 10000), (-0.3, 0), (None, 0), (0.92314, 9231), (0.92316, 9232)],
        ids=["sobre-uno", "negativa", "nula", "redondea-abajo", "redondea-arriba"],
    )
    def test_la_cobertura_de_un_colegio_se_recorta_y_se_redondea_a_puntos_base(self, cobertura, esperado):
        filas = _por_clave(_filas_de_snapshot(HOY, None, [_colegio(cobertura=cobertura)]))

        assert filas[("colegio", "col-1", "cobertura_bps")] == esperado

    def test_a_bps_no_acepta_mas_que_el_rango_cerrado(self):
        assert [_a_bps(x) for x in (-5.0, 0.0, 0.5, 1.0, 5.0)] == [0, 0, 5000, 10000, 10000]


class MetricasFalsas:
    """Los tres agregados de mentira. `consultados` anota a quien se le pidieron metricas."""

    def __init__(
        self,
        resumen: dict[str, Any] | None = RESUMEN,
        colegios: list[dict[str, Any]] | None = None,
        metricas: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.resumen = resumen
        self._colegios = [{"colegio_id": "col-1"}] if colegios is None else colegios
        self._metricas = {"col-1": _colegio("col-1")} if metricas is None else metricas
        self.consultados: list[Any] = []

    async def resumen_catalogo(self) -> dict[str, Any] | None:
        return self.resumen

    async def colegios(self) -> list[dict[str, Any]]:
        return self._colegios

    async def metricas_colegio(self, colegio_id: str) -> dict[str, Any] | None:
        self.consultados.append(colegio_id)
        return self._metricas.get(colegio_id)


CAIDOS = MetricasFalsas(resumen=None, colegios=[], metricas={})


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield MotorServicio(
        servicio="operacion", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    await engine.dispose()


async def _guardado(motor: Any, fecha: date | None = None) -> dict[tuple[str, str | None, str], int]:
    """Lo congelado hasta ahora (de un dia, o de todos), como {(dimension, id, metrica): valor}."""
    consulta = select(METRICA.c.dimension, METRICA.c.dimension_id, METRICA.c.metrica, METRICA.c.valor)
    if fecha is not None:
        consulta = consulta.where(METRICA.c.fecha == fecha)
    async with motor.sesion() as db:
        conexion = await db.connection()
        return {(d, i, m): v for d, i, m, v in await conexion.execute(consulta)}


class TestEscribirInstantanea:
    async def test_el_reporte_dice_cuanto_se_escribio_y_que_servicios_respondieron(self, motor):
        reporte = await escribir_instantanea(motor, MetricasFalsas(), HOY)

        assert reporte == {
            "fecha": "2026-09-25",
            "filas": 7 + 5 + 2,  # catalogo + un colegio + top-line global
            "colegios_con_metricas": 1,
            "catalogo_ok": True,
        }
        assert len(await _guardado(motor, HOY)) == reporte["filas"]

    async def test_a_cada_colegio_se_le_piden_metricas_con_su_id_como_texto_y_sin_id_no_se_pide(self, motor):
        falsas = MetricasFalsas(
            colegios=[{"colegio_id": 7}, {"colegio_id": None}, {"colegio_id": ""}, {}],
            metricas={"7": _colegio(7)},
        )

        reporte = await escribir_instantanea(motor, falsas, HOY)

        assert falsas.consultados == ["7"]
        assert reporte["colegios_con_metricas"] == 1

    async def test_un_colegio_sin_respuesta_no_cuenta_pero_no_aborta_el_snapshot(self, motor):
        falsas = MetricasFalsas(
            colegios=[{"colegio_id": "col-1"}, {"colegio_id": "col-2"}], metricas={"col-2": _colegio("col-2")}
        )

        reporte = await escribir_instantanea(motor, falsas, HOY)

        assert falsas.consultados == ["col-1", "col-2"]
        assert reporte["colegios_con_metricas"] == 1
        assert {i for (d, i, _), _v in (await _guardado(motor)).items() if d == "colegio"} == {"col-2"}

    async def test_con_el_catalogo_caido_el_snapshot_es_parcial_y_valido(self, motor):
        reporte = await escribir_instantanea(motor, MetricasFalsas(resumen=None), HOY)

        guardado = await _guardado(motor, HOY)
        assert reporte["catalogo_ok"] is False
        assert {d for d, _, _ in guardado} == {"colegio", "global"}
        assert reporte["filas"] == len(guardado) == 5 + 2

    async def test_con_todo_caido_la_primera_corrida_no_falla_y_no_escribe_nada(self, motor):
        reporte = await escribir_instantanea(motor, CAIDOS, HOY)

        assert reporte == {
            "fecha": "2026-09-25",
            "filas": 0,
            "colegios_con_metricas": 0,
            "catalogo_ok": False,
        }
        assert await _guardado(motor) == {}

    async def test_reescribir_el_dia_reemplaza_los_valores_y_no_duplica_filas(self, motor):
        await escribir_instantanea(motor, MetricasFalsas(), HOY)
        despues = MetricasFalsas(
            resumen={**RESUMEN, "productos": 999}, metricas={"col-1": _colegio("col-1", kits=9)}
        )

        await escribir_instantanea(motor, despues, HOY)

        guardado = await _guardado(motor, HOY)
        async with motor.sesion() as db:
            total = await (await db.connection()).scalar(select(func.count()).select_from(METRICA))
        assert total == len(guardado) == 14  # ninguna fila de mas
        assert guardado[("catalogo", None, "productos")] == 999
        assert guardado[("colegio", "col-1", "kits_armados")] == 9

    async def test_reescribir_hoy_no_toca_el_snapshot_de_otros_dias(self, motor):
        await escribir_instantanea(motor, MetricasFalsas(), AYER)
        ayer = await _guardado(motor, AYER)

        await escribir_instantanea(motor, MetricasFalsas(resumen={**RESUMEN, "productos": 999}), HOY)
        await escribir_instantanea(motor, CAIDOS, HOY + (HOY - AYER))  # manana, con todo caido

        assert await _guardado(motor, AYER) == ayer
        assert (await _guardado(motor, HOY))[("catalogo", None, "productos")] == 999

    async def test_si_el_insert_revienta_el_borrado_se_deshace_y_el_snapshot_previo_sigue_ahi(self, motor):
        """Borrar-e-insertar va en UNA transaccion: una fila que no cabe no puede dejar el dia vacio."""
        await escribir_instantanea(motor, MetricasFalsas(), HOY)
        antes = await _guardado(motor, HOY)
        inservible = MetricasFalsas(metricas={"col-1": _colegio("col-1", kits=2**70)})

        with pytest.raises(OverflowError, match="too large"):
            await escribir_instantanea(motor, inservible, HOY)

        assert await _guardado(motor, HOY) == antes

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-29: re-correr el dia con todo caido borra el snapshot ya congelado",
    )
    async def test_una_segunda_corrida_con_todo_caido_no_borra_lo_ya_congelado(self, motor):
        """Una corrida que no logro medir NADA no puede dejar el dia vacio. El modulo promete que
        correrlo dos veces el mismo dia "deja lo mismo" (instantanea.py:14-16), que un snapshot
        parcial es una respuesta valida (22-23) y que las cifras de calidad "ya no se pueden volver
        a medir" (5-9). Evidencia: instantanea.py:175 hace el `delete` del dia SIEMPRE y solo el
        insert esta protegido por `if filas` (176): con todo caido `filas` queda vacio y el dia
        entero congelado se pierde, con un reporte de `0 filas` y salida 0 como si nada. Lo
        correcto es no borrar lo ya congelado cuando no hay nada nuevo que poner."""
        await escribir_instantanea(motor, MetricasFalsas(), HOY)
        antes = await _guardado(motor, HOY)

        await escribir_instantanea(motor, CAIDOS, HOY)

        assert await _guardado(motor, HOY) == antes


class MotorEspia:
    """Hace de `MotorServicio`: delega la sesion y anota `cerrar` sin cerrar el engine (para releer)."""

    def __init__(self, motor: MotorServicio) -> None:
        self.motor = motor
        self.cerrado = False
        self.pedidos: list[str] = []

    def sesion(self) -> Any:
        return self.motor.sesion()

    async def cerrar(self) -> None:
        self.cerrado = True


class TestCorrer:
    @pytest.fixture
    def espia(self, monkeypatch: pytest.MonkeyPatch, motor: MotorServicio) -> MotorEspia:
        espia = MotorEspia(motor)

        def crear(servicio: str) -> MotorEspia:
            espia.pedidos.append(servicio)
            return espia

        monkeypatch.setattr(instantanea, "crear_motor", crear)
        monkeypatch.setattr(instantanea, "ClienteMetricas", MetricasFalsas)
        return espia

    async def test_escribe_en_la_base_de_operacion_y_cierra_el_motor(self, espia, motor):
        reporte = await _correr(HOY)

        assert reporte["filas"] == 14
        assert espia.pedidos == ["operacion"]  # su propia base, no la de otro servicio
        assert espia.cerrado is True
        assert len(await _guardado(motor, HOY)) == 14

    async def test_si_la_escritura_falla_el_motor_se_cierra_igual_y_el_error_sale(self, espia, monkeypatch):
        async def revienta(motor: Any, cliente: Any, hoy: date) -> dict[str, Any]:
            raise RuntimeError("la base no contesta")

        monkeypatch.setattr(instantanea, "escribir_instantanea", revienta)

        with pytest.raises(RuntimeError, match="la base no contesta"):
            await _correr(HOY)

        assert espia.cerrado is True


class _RelojUTC:
    """Un `datetime` de mentira: anota la zona que se le pidio y siempre es la misma noche, en UTC."""

    zonas: list[Any] = []

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        cls.zonas.append(tz)
        return datetime(2026, 9, 25, 23, 59, tzinfo=UTC)


class TestMain:
    def test_congela_el_dia_utc_imprime_el_reporte_y_devuelve_cero(self, monkeypatch, capsys):
        """El dia se mide en UTC, no en la zona de la maquina: 23:59 UTC sigue siendo el 25."""
        recibidos: list[date] = []

        async def correr(hoy: date) -> dict[str, Any]:
            recibidos.append(hoy)
            return {"fecha": hoy.isoformat(), "filas": 14, "colegios_con_metricas": 1, "catalogo_ok": True}

        _RelojUTC.zonas = []
        monkeypatch.setattr(instantanea, "datetime", _RelojUTC)
        monkeypatch.setattr(instantanea, "_correr", correr)

        assert main([]) == 0

        assert _RelojUTC.zonas == [UTC]
        assert recibidos == [HOY]
        assert capsys.readouterr().out == "snapshot 2026-09-25: 14 filas, 1 colegios, catalogo=ok\n"

    def test_con_el_catalogo_caido_lo_dice_en_la_salida(self, monkeypatch, capsys):
        async def correr(hoy: date) -> dict[str, Any]:
            return {"fecha": hoy.isoformat(), "filas": 0, "colegios_con_metricas": 0, "catalogo_ok": False}

        monkeypatch.setattr(instantanea, "_correr", correr)

        assert main([]) == 0
        assert capsys.readouterr().out.endswith(": 0 filas, 0 colegios, catalogo=caido\n")

    def test_un_argumento_desconocido_se_rechaza_sin_correr_nada(self, monkeypatch, capsys):
        async def correr(hoy: date) -> dict[str, Any]:
            raise AssertionError("no debia correr")

        monkeypatch.setattr(instantanea, "_correr", correr)

        with pytest.raises(SystemExit) as salida:
            main(["--seguir"])

        assert salida.value.code == 2
        assert "--seguir" in capsys.readouterr().err

    def test_ejecutado_como_modulo_congela_el_snapshot_de_hoy_en_la_base_de_operacion(
        self, monkeypatch, tmp_path: Path, capsys
    ):
        """`python -m tukit_operacion.instantanea` de punta a punta, con una base SQLite en archivo
        y los agregados de mentira: sale con 0, imprime el reporte y deja las filas del dia."""
        ruta = tmp_path / "operacion.db"
        sincrono = create_engine(f"sqlite:///{ruta}")
        Base.metadata.create_all(sincrono)
        sincrono.dispose()
        pedidos: list[str] = []

        def crear(servicio: str) -> MotorServicio:
            pedidos.append(servicio)
            engine = create_async_engine(f"sqlite+aiosqlite:///{ruta}")
            return MotorServicio(
                servicio=servicio, engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
            )

        monkeypatch.setattr(bd, "crear_motor", crear)
        monkeypatch.setattr(remoto, "ClienteMetricas", MetricasFalsas)
        monkeypatch.setattr(sys, "argv", ["tukit_operacion.instantanea"])

        # runpy avisa que el modulo ya estaba importado: es justo lo que se esta ensayando.
        with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_operacion.instantanea", run_name="__main__")

        asegurado = re.fullmatch(
            r"snapshot (\d{4}-\d{2}-\d{2}): 14 filas, 1 colegios, catalogo=ok\n", capsys.readouterr().out
        )
        assert salida.value.code == 0
        assert asegurado is not None
        assert pedidos == ["operacion"]
        conexion = sqlite3.connect(ruta)
        try:
            fechas = {f for (f,) in conexion.execute("select fecha from metrica_diaria")}
            filas = conexion.execute("select count(*) from metrica_diaria").fetchone()
        finally:
            conexion.close()
        assert fechas == {asegurado.group(1)}
        assert filas == (14,)
