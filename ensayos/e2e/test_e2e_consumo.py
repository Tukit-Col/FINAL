"""Fase 5 de QA: el limite estricto como freno al consumo del modelo (OWASP LLM10), contra el stack.

`servicios/gateway/tests/test_gateway_limite_patron.py` fija el tope en proceso, con un backend
de mentira. Aqui una acudiente sube por la puerta de los E2E (la copia del gateway con la
inteligencia de los dorados, `conftest.py`) como lo haria un script: con su token y su IP, la
misma pagina una y otra vez. La subida que pasa el tope de la ventana recibe un 429 con su espera
antes de llegar a inteligencia, y el registro de lecturas de la copia no crece con ella. Las que
pasan cuestan sus paginas: una lectura por subida sin Redis en la copia, una sola con Redis.

Los numeros son los que calcula `tukit_gateway.limite` con el entorno de la prueba, el mismo que
hereda la copia del gateway: los del ADR 0047 por omision (30 por token en 600 s), declarados por
el lanzador en `limites.json` (N-132). Todo va a un colegio ficticio que nadie revisa (N-140).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from e2e_flujo import colegio_ficticio, registrar_acudiente
from test_e2e_adversariales import _lecturas, _subir
from tukit_gateway.limite import niveles

pytestmark = pytest.mark.nfr("NFR-SEG-03")

FIXTURE = "ADV-09-p1"  # la lista de tres renglones, sin nada hostil: el ataque es repetirla


@pytest.fixture(scope="module")
def rafaga(http_flujo: httpx.Client, colegio_aliado: str, puerta: dict[str, Any]) -> dict[str, Any]:
    """El tope de subidas seguidas de la misma acudiente, y una mas."""
    _, estricto = niveles()
    acudiente = registrar_acudiente(http_flujo, colegio_aliado)
    colegio = colegio_ficticio("LLM10")
    antes = _lecturas(puerta)
    estados = [
        _subir(http_flujo, acudiente["cabecera"], FIXTURE, colegio).status_code
        for _ in range(estricto.por_token)
    ]
    en_el_tope = _lecturas(puerta)
    ultima = _subir(http_flujo, acudiente["cabecera"], FIXTURE, colegio)
    return {
        "tope": estricto.por_token,
        "ventana": estricto.ventana,
        "estados": estados,
        "ultima": ultima,
        "lecturas_en_el_tope": en_el_tope - antes,
        "lecturas_de_la_ultima": _lecturas(puerta) - en_el_tope,
    }


def test_las_subidas_dentro_del_tope_pasan(rafaga, record_property):
    record_property("tope_por_token", rafaga["tope"])
    record_property("subidas_aceptadas", rafaga["estados"].count(202))
    assert rafaga["estados"] == [202] * rafaga["tope"]


def test_la_subida_que_pasa_el_tope_recibe_un_429_con_su_espera(rafaga, record_property):
    ultima = rafaga["ultima"]

    assert ultima.status_code == 429, ultima.text
    espera = int(ultima.headers["retry-after"])
    record_property("retry_after", espera)
    assert ultima.json()["error"] == "demasiadas_peticiones"
    assert ultima.json()["reintentar_en_segundos"] == espera
    # La espera es de la ventana estricta, no de la general de 60 s; el redondeo hacia arriba
    # puede dar un segundo mas que la ventana (N-127).
    assert 60 < espera <= rafaga["ventana"] + 1


def test_la_subida_rechazada_no_llega_al_modelo(rafaga, record_property):
    record_property("lecturas_en_el_tope", rafaga["lecturas_en_el_tope"])
    record_property("lecturas_de_la_rechazada", rafaga["lecturas_de_la_ultima"])
    assert rafaga["lecturas_de_la_ultima"] == 0
    assert 1 <= rafaga["lecturas_en_el_tope"] <= rafaga["tope"]
