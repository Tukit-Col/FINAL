from __future__ import annotations

import pytest
from tukit_comun.entorno import ConfiguracionInsegura
from tukit_identidad.dominio import sesiones


@pytest.fixture
def produccion(monkeypatch):
    monkeypatch.setenv("TUKIT_ENTORNO", "produccion")


def test_en_desarrollo_sin_llave_de_sesion_usa_la_de_desarrollo(monkeypatch):
    monkeypatch.delenv("TUKIT_ENTORNO", raising=False)
    monkeypatch.delenv("TUKIT_LLAVE_SESION", raising=False)
    assert sesiones._llave() == sesiones._LLAVE_DESARROLLO.encode()


@pytest.mark.parametrize(
    "llave",
    ["", "corta", sesiones._LLAVE_DESARROLLO],
    ids=["sin_llave", "llave_corta", "llave_de_desarrollo"],
)
def test_en_produccion_una_llave_de_sesion_insegura_no_arranca(monkeypatch, produccion, llave):
    monkeypatch.setenv("TUKIT_LLAVE_SESION", llave)
    with pytest.raises(ConfiguracionInsegura, match="TUKIT_LLAVE_SESION"):
        sesiones._llave()


def test_en_produccion_una_llave_de_sesion_larga_se_usa(monkeypatch, produccion):
    llave = "x" * 48
    monkeypatch.setenv("TUKIT_LLAVE_SESION", llave)
    assert sesiones._llave() == llave.encode()
