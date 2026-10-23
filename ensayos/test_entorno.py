"""`cargar_env` no pisa el entorno, y la cache de los ensayos se puede mover."""

from __future__ import annotations

import os

from ensayos.entorno import RAIZ, cargar_env, carpeta_cache


def test_cargar_env_no_pisa_lo_que_ya_esta(tmp_path, monkeypatch):
    archivo = tmp_path / ".env"
    archivo.write_text(
        "# comentario\nTUKIT_PRUEBA_A=del_archivo\nTUKIT_PRUEBA_B = 'con comillas'\nsin_igual\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TUKIT_PRUEBA_A", "del_entorno")
    monkeypatch.delenv("TUKIT_PRUEBA_B", raising=False)

    cargar_env(archivo)

    assert os.environ["TUKIT_PRUEBA_A"] == "del_entorno"
    assert os.environ["TUKIT_PRUEBA_B"] == "con comillas"
    monkeypatch.delenv("TUKIT_PRUEBA_B")


def test_sin_archivo_no_hace_nada(tmp_path):
    cargar_env(tmp_path / "no-existe.env")


def test_la_cache_va_a_una_carpeta_ignorada_o_a_la_variable(tmp_path, monkeypatch):
    monkeypatch.delenv("TUKIT_CACHE_ENSAYOS", raising=False)
    assert carpeta_cache() == RAIZ / ".cache" / "ensayos"
    monkeypatch.setenv("TUKIT_CACHE_ENSAYOS", str(tmp_path))
    assert carpeta_cache() == tmp_path
