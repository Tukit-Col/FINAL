"""NFR-MAN-01: las metricas de dominio degradan sin OTel y cuentan con OTel (ADR 0021, B.4).

`test_metricas_dominio.py` solo dice "no revienta". Aqui se prueba la
degradacion de verdad (sin el extra `otel` los contadores devuelven sin hacer
nada y SIN cachear el vacio, de modo que un OTel que aparece despues si cuenta)
y, con un OTel de mentira en `sys.modules`, el comportamiento observable: cada
contador se crea una sola vez, con su nombre estable, y suma uno por llamada; el
gauge del disyuntor se registra una sola vez y su callback lee el registro VIVO
de `resiliencia`.

Importa porque contar una orden o un pago esta en el camino caliente del
checkout y de la saga: no puede tumbarlos ni crear un instrumento por llamada.
Los nombres de las metricas son contrato con el panel de operacion.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from tukit_comun import metricas, resiliencia
from tukit_comun.resiliencia import Disyuntor

pytestmark = pytest.mark.nfr("NFR-MAN-01")

VARIABLE = "OTEL_EXPORTER_OTLP_ENDPOINT"


class Reloj:
    def __call__(self) -> float:
        return 0.0


def _purgar_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    for nombre in [n for n in sys.modules if n == "opentelemetry" or n.startswith("opentelemetry.")]:
        monkeypatch.delitem(sys.modules, nombre)


def _sin_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fuerza `ImportError` al importar OTel, este o no instalado."""
    _purgar_otel(monkeypatch)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    monkeypatch.setitem(sys.modules, "opentelemetry.metrics", None)


class ContadorFalso:
    def __init__(self, nombre: str, descripcion: str) -> None:
        self.nombre = nombre
        self.descripcion = descripcion
        self.suma = 0

    def add(self, cantidad: int) -> None:
        self.suma += cantidad


class MeterFalso:
    def __init__(self) -> None:
        self.contadores: list[ContadorFalso] = []
        self.gauges: list[SimpleNamespace] = []

    def create_counter(self, nombre: str, *, description: str) -> ContadorFalso:
        contador = ContadorFalso(nombre, description)
        self.contadores.append(contador)
        return contador

    def create_observable_gauge(self, nombre: str, *, callbacks: list[Any], description: str) -> None:
        self.gauges.append(SimpleNamespace(nombre=nombre, callbacks=callbacks, descripcion=description))


class Observation:
    def __init__(self, valor: int, atributos: dict[str, str]) -> None:
        self.valor = valor
        self.atributos = atributos


def _instalar_otel(monkeypatch: pytest.MonkeyPatch, *, con_observation: bool = True) -> MeterFalso:
    meter = MeterFalso()
    pedidos: list[str] = []
    modulo_metrics = ModuleType("opentelemetry.metrics")
    modulo_metrics.get_meter = lambda nombre: (pedidos.append(nombre), meter)[1]  # type: ignore[attr-defined]
    if con_observation:
        modulo_metrics.Observation = Observation  # type: ignore[attr-defined]
    paquete = ModuleType("opentelemetry")
    paquete.__path__ = []
    paquete.metrics = modulo_metrics  # type: ignore[attr-defined]
    _purgar_otel(monkeypatch)
    monkeypatch.setitem(sys.modules, "opentelemetry", paquete)
    monkeypatch.setitem(sys.modules, "opentelemetry.metrics", modulo_metrics)
    meter.pedidos = pedidos  # type: ignore[attr-defined]
    return meter


@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contadores, bandera del gauge y registro de disyuntores son globales."""
    monkeypatch.setattr(metricas, "_contadores", {})
    monkeypatch.setattr(metricas, "_gauge_registrado", False)
    monkeypatch.setattr(resiliencia, "_disyuntores", {})
    monkeypatch.delenv(VARIABLE, raising=False)


CONTADORES = [
    (metricas.contar_orden_creada, "tukit.ordenes.creadas"),
    (metricas.contar_pago_aprobado, "tukit.pagos.aprobados"),
    (metricas.contar_trabajo_publicado, "tukit.trabajos.publicados"),
]


class TestSinElExtraLosContadoresNoHacenNada:
    @pytest.mark.parametrize(("contar", "nombre"), CONTADORES)
    def test_devuelve_sin_error_y_no_deja_rastro(self, monkeypatch, contar, nombre):
        _sin_otel(monkeypatch)

        assert contar() is None
        assert contar() is None

        assert metricas._contadores == {}  # no se cachea el vacio

    def test_si_el_extra_aparece_despues_el_contador_se_crea_en_el_primer_uso(self, monkeypatch):
        """El contador se resuelve perezosamente: da igual el orden de arranque."""
        with monkeypatch.context() as sin_extra:
            _sin_otel(sin_extra)
            metricas.contar_orden_creada()  # antes de que haya OTel: se pierde, sin error

        meter = _instalar_otel(monkeypatch)
        metricas.contar_orden_creada()

        (contador,) = meter.contadores
        assert (contador.nombre, contador.suma) == ("tukit.ordenes.creadas", 1)

    def test_configurar_metricas_con_endpoint_pero_sin_el_extra_no_registra_el_gauge(self, monkeypatch):
        _sin_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, "http://collector.example.test:4317")

        assert metricas.configurar_metricas() is None

        assert metricas._gauge_registrado is False

    def test_configurar_metricas_sin_endpoint_no_toca_el_meter_aunque_haya_otel(self, monkeypatch):
        meter = _instalar_otel(monkeypatch)

        metricas.configurar_metricas()

        assert meter.pedidos == []  # ni siquiera pidio el meter
        assert meter.gauges == []
        assert metricas._gauge_registrado is False


class TestConOtelCadaContadorSumaUno:
    @pytest.mark.parametrize(("contar", "nombre"), CONTADORES)
    def test_el_contador_lleva_el_nombre_del_contrato_y_suma_uno_por_llamada(
        self, monkeypatch, contar, nombre
    ):
        meter = _instalar_otel(monkeypatch)

        for _ in range(3):
            contar()

        (contador,) = meter.contadores  # creado UNA vez, no uno por llamada
        assert contador.nombre == nombre
        assert contador.suma == 3
        assert contador.descripcion  # el panel muestra la descripcion

    def test_los_tres_contadores_son_instrumentos_distintos(self, monkeypatch):
        meter = _instalar_otel(monkeypatch)

        metricas.contar_orden_creada()
        metricas.contar_pago_aprobado()
        metricas.contar_trabajo_publicado()
        metricas.contar_orden_creada()

        sumas = {c.nombre: c.suma for c in meter.contadores}
        assert sumas == {
            "tukit.ordenes.creadas": 2,
            "tukit.pagos.aprobados": 1,
            "tukit.trabajos.publicados": 1,
        }
        assert set(metricas._contadores) == set(sumas)

    def test_el_meter_se_pide_con_el_nombre_tukit(self, monkeypatch):
        meter = _instalar_otel(monkeypatch)

        metricas.contar_pago_aprobado()

        assert meter.pedidos == ["tukit"]


class TestElGaugeDelDisyuntor:
    async def _abrir(self, destino: str) -> Disyuntor:
        d = Disyuntor(destino, umbral=1, reloj=Reloj())
        resiliencia._disyuntores[destino] = d
        with pytest.raises(ConnectionError):
            async with d:
                raise ConnectionError("caido")
        return d

    async def test_se_registra_con_su_nombre_y_el_callback_lee_el_estado_de_cada_destino(self, monkeypatch):
        meter = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, "http://collector.example.test:4317")
        await self._abrir("catalogo")
        resiliencia._disyuntores["identidad"] = Disyuntor("identidad", reloj=Reloj())

        metricas.configurar_metricas()

        (gauge,) = meter.gauges
        assert gauge.nombre == "tukit.breaker.abierto"
        assert "ADR 0020" in gauge.descripcion
        (callback,) = gauge.callbacks
        lecturas = {o.atributos["destino"]: o.valor for o in callback(None)}
        assert lecturas == {"catalogo": 1, "identidad": 0}
        assert metricas._gauge_registrado is True

    async def test_el_callback_ve_los_disyuntores_que_nacen_despues_del_registro(self, monkeypatch):
        """Es observable: lee el registro vivo en cada barrido, nadie empuja."""
        meter = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, "http://collector.example.test:4317")
        metricas.configurar_metricas()
        (callback,) = meter.gauges[0].callbacks
        assert callback(None) == []

        await self._abrir("comercio")
        assert [(o.atributos, o.valor) for o in callback(None)] == [({"destino": "comercio"}, 1)]

        resiliencia._disyuntores["comercio"] = Disyuntor("comercio", reloj=Reloj())  # se cerro
        assert [(o.atributos, o.valor) for o in callback(None)] == [({"destino": "comercio"}, 0)]

    def test_es_idempotente_no_registra_el_gauge_dos_veces(self, monkeypatch):
        meter = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, "http://collector.example.test:4317")

        metricas.configurar_metricas()
        metricas.configurar_metricas()

        assert len(meter.gauges) == 1

    def test_si_la_api_de_otel_no_trae_observation_no_registra_nada(self, monkeypatch):
        meter = _instalar_otel(monkeypatch, con_observation=False)
        monkeypatch.setenv(VARIABLE, "http://collector.example.test:4317")

        assert metricas.configurar_metricas() is None

        assert meter.gauges == []
        assert metricas._gauge_registrado is False
