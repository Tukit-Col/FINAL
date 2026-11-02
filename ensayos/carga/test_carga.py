"""El resumen del ensayo de carga: percentiles y la separacion de los 429."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parent / "carga.py"
_spec = importlib.util.spec_from_file_location("ensayo_carga", _RUTA)
assert _spec is not None and _spec.loader is not None
carga = importlib.util.module_from_spec(_spec)
# Un dataclass resuelve sus anotaciones por el nombre del modulo en sys.modules.
sys.modules[_spec.name] = carga
_spec.loader.exec_module(carga)


def _m(ms: float, estado: int = 200) -> object:
    return carga.Muestra(inicio=0.0, fin=ms / 1000, punto="x", estado=estado, bytes=10)


def test_percentil_por_rango_no_interpola():
    datos = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert carga.percentil(datos, 50) == 5.0
    assert carga.percentil(datos, 95) == 10.0
    assert carga.percentil([7.0], 99) == 7.0


def test_un_429_no_es_error_ni_entra_en_la_latencia():
    muestras = [_m(10), _m(20), _m(1, 429), _m(1, 429), _m(5, 500), _m(0, 0)]
    r = carga.resumir(muestras, duracion_s=2.0)
    assert r["limitadas_429"] == 2
    assert r["errores"] == 2  # el 500 y la que no tuvo respuesta
    assert r["exitosas_2xx"] == 2
    assert r["latencia_ms"]["p50"] == pytest.approx(10.0)
    assert r["peticiones_por_s"] == 3.0


def test_solo_se_ensaya_contra_la_maquina_local():
    with pytest.raises(SystemExit):
        carga._validar_local("https://ejemplo.trycloudflare.com")
    carga._validar_local("http://127.0.0.1:8010")
