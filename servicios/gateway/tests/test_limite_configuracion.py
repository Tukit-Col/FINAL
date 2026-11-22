from __future__ import annotations

import logging

import pytest
from tukit_gateway import api, limite


@pytest.mark.parametrize(
    ("metodo", "ruta", "nombre"),
    [
        ("POST", "/v1/listas/subir", "listas-subir"),
        ("POST", "/v1/trabajos", "trabajos"),
        ("POST", "/v1/trabajos/8a1c/reintentar", "trabajos-reintentar"),
        ("POST", "/v1/trabajos/aplicar-canonico", "trabajos-aplicar-canonico"),
        ("POST", "/v1/admin/onboarding", "onboarding"),
        ("POST", "/v1/admin/onboarding/ver-1/preview", "onboarding-preview"),
        ("POST", "/v1/sesiones", "sesiones"),
        ("POST", "/v1/sesiones/", "sesiones"),
        ("POST", "/v1/cuenta", "cuenta"),
        ("POST", "/v1/registro", "registro"),
        ("POST", "/v1/catalogo/emparejar", "catalogo-emparejar"),
        ("POST", "/v1/admin/sugerencias", "sugerencias"),
        ("POST", "/v1/cuenta/supresion", "cuenta-supresion"),
        ("POST", "/v1/cuenta/supresion/", "cuenta-supresion"),
        ("POST", "/v1/cuenta/consentimientos/revocar", "cuenta-consentimientos"),
        ("GET", "/v1/cuenta/mis-datos", None),
        ("GET", "/v1/cuenta/mis-datos/exportar", None),
        ("GET", "/v1/trabajos", None),
        ("POST", "/v1/sesiones/cierre", None),
        ("POST", "/v1/trabajos/8a1c", None),
        ("PATCH", "/v1/cuenta", None),
        ("POST", "/v1/cuenta/direcciones", None),
        ("POST", "/v1/ordenes", None),
        ("POST", "/v1/comercio/mis-pedidos/p-1/pago", None),
        ("POST", "/v1/pagos/p-1/sincronizar", None),
    ],
)
def test_las_rutas_estrictas(metodo, ruta, nombre):
    assert limite.ruta_estricta(metodo, ruta) == nombre


def test_cada_ruta_estricta_existe_en_el_mapa_de_la_puerta():
    for _, patron in limite.RUTAS_ESTRICTAS:
        ejemplo = patron.pattern.replace("[^/]+", "x")
        assert api.destino(ejemplo) is not None, ejemplo


def test_la_supresion_va_con_su_propio_nivel_mas_corto_que_el_estricto():
    por_contar = limite.cuentas("POST", "/v1/cuenta/supresion", "tok-ana", "203.0.113.7")
    supresion = [c for c in por_contar if c.ruta == "cuenta-supresion"]
    _, estricto = limite.niveles()
    assert {c.nivel for c in supresion} == {"supresion"}
    assert {c.tipo: c.tope for c in supresion} == {"token": 5, "ip": 10}
    assert all(c.tope < estricto.por_token for c in supresion)
    assert all(c.ventana == 3600 for c in supresion)
    assert any(c.nivel == "general" for c in por_contar)


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("GET", "/v1/servicios"),
        ("POST", "/v1/webhooks/wompi"),
        ("POST", "/v1/webhooks"),
        ("OPTIONS", "/v1/catalogo/conceptos"),
        ("GET", "/salud"),
        ("GET", "/health/ready"),
        ("GET", "/favicon.ico"),
    ],
)
def test_las_rutas_exentas(metodo, ruta):
    assert limite.cuentas(metodo, ruta, "tok-ana", "198.51.100.7") == []


def test_los_numeros_por_omision():
    general, estricto = limite.niveles()
    assert (general.ventana, general.por_token, general.por_ip) == (60, 300, 1200)
    assert (estricto.ventana, estricto.por_token, estricto.por_ip) == (600, 30, 60)


def test_se_configuran_por_entorno_y_un_valor_malo_deja_el_de_omision(monkeypatch, caplog):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_VENTANA", "30")
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_TOKEN", "cinco")
    with caplog.at_level(logging.WARNING):
        general, estricto = limite.niveles()
        limite.niveles()

    assert general.ventana == 30
    assert estricto.por_token == 30
    assert caplog.text.count("TUKIT_LIMITE_ESTRICTO_TOKEN") == 1


def test_un_cero_apaga_un_tope_o_un_nivel(monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "0")
    assert [c.tipo for c in limite.cuentas("GET", "/v1/colegios", "tok", "198.51.100.7")] == ["ip"]
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_VENTANA", "0")
    assert [c.nivel for c in limite.cuentas("POST", "/v1/sesiones", "tok", "198.51.100.7")] == ["general"]
