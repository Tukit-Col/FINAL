"""NFR-COS-01: los E2E de la fase 4 no hicieron ninguna llamada real a Gemini.

Corre al final de `ensayos/e2e` (por orden de archivo) y mira las dos guardias:
la de pytest (`acuerdos.md` §4.2), que cuenta los intentos en este proceso, y
la de la copia de inteligencia que atiende las subidas, que anota en su propio
archivo cualquier intento de resolver el dominio de Gemini. Ademas cada pagina
que llego a la percepcion tiene que haberse servido de un fixture grabado.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.nfr("NFR-COS-01")


def test_ninguna_llamada_real_a_gemini_en_ningun_proceso(puerta, _guardia_sesion, record_property):
    guardia = puerta["guardia"]
    intentos_inteligencia = len(guardia.read_text().splitlines()) if guardia.exists() else 0

    record_property("intentos_pytest", _guardia_sesion["intentos"])
    record_property("intentos_inteligencia", intentos_inteligencia)
    record_property("llamadas_reales", _guardia_sesion["intentos"] + intentos_inteligencia)
    assert _guardia_sesion["intentos"] == 0
    assert intentos_inteligencia == 0


def test_cada_pagina_leida_salio_de_un_fixture(puerta, record_property):
    lecturas = puerta["lecturas"].read_text().splitlines() if puerta["lecturas"].exists() else []

    sin_fixture = [linea for linea in lecturas if linea.split()[-1] == "-"]
    record_property("paginas_leidas", len(lecturas))
    record_property("paginas_sin_fixture", len(sin_fixture))
    assert lecturas, "la percepcion no leyo ninguna pagina: los E2E no pasaron por la copia de inteligencia"
    assert sin_fixture == []
