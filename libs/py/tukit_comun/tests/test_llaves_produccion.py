from __future__ import annotations

import pytest
from tukit_comun.cifrado import CifradorEnClaro, cifrador_desde_entorno
from tukit_comun.entorno import ConfiguracionInsegura, en_produccion

pytest.importorskip("cryptography")
from cryptography.fernet import Fernet  # noqa: E402


@pytest.fixture
def produccion(monkeypatch):
    monkeypatch.setenv("TUKIT_ENTORNO", "produccion")


def test_sin_variable_de_entorno_no_es_produccion(monkeypatch):
    monkeypatch.delenv("TUKIT_ENTORNO", raising=False)
    assert not en_produccion()


def test_en_desarrollo_sin_llave_de_cifrado_arranca_en_claro(monkeypatch):
    monkeypatch.delenv("TUKIT_ENTORNO", raising=False)
    monkeypatch.delenv("TUKIT_LLAVE_CIFRADO", raising=False)
    assert isinstance(cifrador_desde_entorno(), CifradorEnClaro)


def test_en_produccion_sin_llave_de_cifrado_no_arranca(monkeypatch, produccion):
    monkeypatch.delenv("TUKIT_LLAVE_CIFRADO", raising=False)
    with pytest.raises(ConfiguracionInsegura, match="TUKIT_LLAVE_CIFRADO"):
        cifrador_desde_entorno()


def test_en_produccion_una_llave_de_cifrado_invalida_no_arranca(monkeypatch, produccion):
    monkeypatch.setenv("TUKIT_LLAVE_CIFRADO", "no-es-una-llave-fernet")
    with pytest.raises(ConfiguracionInsegura, match="no sirve"):
        cifrador_desde_entorno()


def test_en_produccion_con_llave_valida_cifra_de_verdad(monkeypatch, produccion):
    monkeypatch.setenv("TUKIT_LLAVE_CIFRADO", Fernet.generate_key().decode())
    cifrador = cifrador_desde_entorno()
    assert cifrador.cifra_de_verdad
    assert cifrador.descifrar(cifrador.cifrar(b"Sofia")) == b"Sofia"


def test_lo_guardado_en_claro_antes_de_poner_la_llave_se_sigue_leyendo(monkeypatch):
    monkeypatch.delenv("TUKIT_LLAVE_CIFRADO", raising=False)
    guardado = CifradorEnClaro().cifrar(b"Sofia")
    monkeypatch.setenv("TUKIT_LLAVE_CIFRADO", Fernet.generate_key().decode())
    assert cifrador_desde_entorno().descifrar(guardado) == b"Sofia"
