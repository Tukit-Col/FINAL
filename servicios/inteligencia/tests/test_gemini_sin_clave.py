"""NFR-MAN-01: El adaptador de Gemini sin clave: falla antes de abrir una conexion y no inventa renglones.

Lo que el contrato pide de esta dependencia es que NO haya respuesta inventada:
si falta la clave (o la llamada no vuelve, o vuelve algo que no es el JSON
pedido) se alza `PercepcionFallida` y el trabajo queda fallido y reintentable.
Estas pruebas cubren solo lo que se alcanza SIN clave y sin red:

- sin `GEMINI_API_KEY` el adaptador se niega ANTES de armar la peticion, de
  resolver el dominio o de abrir un socket (la guardia del `conftest` borra la
  variable de cada prueba y hace fallar cualquier resolucion de Gemini);
- el mensaje de error nombra la variable que falta, para que quien opera sepa
  que configurar, y el trabajo lo muestra como `percepcion_fallida`;
- el esquema `_ESQUEMA` que se le pide a la API coincide campo por campo con el
  modelo que luego valida la respuesta (`PaginaLeida`): si uno cambia sin el
  otro, la API contesta algo que el parser rechaza en produccion, no en CI.

Las ramas que SI exigen la clave (armar la peticion, `urlopen`, mapear HTTP,
timeout y JSON invalido) quedan sin cubrir a proposito.
"""

from __future__ import annotations

import re
import urllib.request
from typing import Any

import pytest
from tukit_inteligencia import gemini
from tukit_inteligencia.percepcion import (
    ItemExtraido,
    PaginaLeida,
    PercepcionFallida,
    percibir,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")


@pytest.fixture()
def sin_conexion(monkeypatch):
    """Cualquier intento de abrir una conexion saliente falla la prueba."""

    def _no(*_a: Any, **_k: Any) -> Any:
        pytest.fail("el adaptador abrio una conexion sin tener clave")

    monkeypatch.setattr(urllib.request, "urlopen", _no)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _no)


class TestSinClave:
    def test_la_clave_y_el_modelo_se_niegan_con_un_mensaje_que_nombra_la_variable(self):
        with pytest.raises(PercepcionFallida) as info:
            gemini._clave_y_modelo()

        assert "GEMINI_API_KEY" in str(info.value)
        assert "no voy a inventar" in str(info.value)

    def test_pedir_pagina_falla_antes_de_abrir_una_conexion(self, sin_conexion):
        """Con la peticion sin armar no hay ni URL, ni cuerpo, ni socket: no se filtra nada."""
        with pytest.raises(PercepcionFallida, match="GEMINI_API_KEY"):
            gemini.pedir_pagina(b"\x89PNG-ficticio", 1)

    def test_la_percepcion_lo_convierte_en_un_archivo_rechazado_sin_kit_a_medias(self, sin_conexion):
        """Sin clave el acudiente ve un rechazo que dice en que pagina fallo: nunca renglones inventados."""
        resultado = percibir(b"png-ficticio", renderizar=lambda c: [c, c], leer=gemini.pedir_pagina)

        assert resultado.aceptada is False
        assert resultado.error == "percepcion_fallida"
        assert resultado.items == ()  # ni una linea leida de la pagina 1
        assert resultado.paginas == 2
        assert resultado.degradaciones == ("gemini",)
        assert resultado.mensaje.startswith("No pude leer la pagina 1:")
        assert "GEMINI_API_KEY" in resultado.mensaje


class TestEsquemaPedidoALaApi:
    def test_es_un_objeto_con_los_tres_campos_obligatorios_de_la_pagina(self):
        esquema = gemini._ESQUEMA

        assert esquema["type"] == "OBJECT"
        assert set(esquema["properties"]) == {"grados", "completa", "items"}
        assert set(esquema["required"]) == {"grados", "items", "completa"}

    def test_los_tipos_son_los_del_subconjunto_openapi_de_gemini(self):
        """Gemini acepta tipos en MAYUSCULAS (`STRING`, `ARRAY`...): un `string` minuscula se rechaza."""
        propiedades = gemini._ESQUEMA["properties"]
        renglon = propiedades["items"]["items"]

        assert propiedades["grados"] == {"type": "ARRAY", "items": {"type": "STRING"}}
        assert propiedades["completa"] == {"type": "BOOLEAN"}
        assert propiedades["items"]["type"] == "ARRAY"
        assert renglon["type"] == "OBJECT"
        assert renglon["properties"]["descripcion"] == {"type": "STRING"}
        assert renglon["properties"]["cantidad"] == {"type": "INTEGER", "nullable": True}
        assert renglon["properties"]["confianza"] == {"type": "NUMBER", "nullable": True}

    def test_solo_la_descripcion_es_obligatoria_en_cada_renglon(self):
        """Una fila sin cantidad es legitima (`cantidad` null): no se le exige a la pagina inventarla."""
        assert gemini._ESQUEMA["properties"]["items"]["items"]["required"] == ["descripcion"]

    def test_el_esquema_y_el_modelo_que_valida_la_respuesta_hablan_de_los_mismos_campos(self):
        renglon = gemini._ESQUEMA["properties"]["items"]["items"]["properties"]

        assert set(gemini._ESQUEMA["properties"]) == set(PaginaLeida.model_fields)
        assert set(renglon) == set(ItemExtraido.model_fields)

    def test_una_pagina_escrita_segun_el_esquema_la_acepta_el_modelo(self):
        """Lo que la API promete devolver (todo opcional salvo lo `required`) debe parsear."""
        completa = (
            '{"grados": ["Cuarto"], "completa": true, "items": '
            '[{"descripcion": "Cuaderno cuadriculado", "cantidad": 2, "confianza": 0.9}]}'
        )
        minima = '{"grados": [], "completa": false, "items": [{"descripcion": "Regla", "cantidad": null}]}'

        pagina = PaginaLeida.model_validate_json(completa)
        corta = PaginaLeida.model_validate_json(minima)

        assert pagina.items[0].cantidad == 2 and pagina.items[0].confianza == 0.9
        assert corta.completa is False
        assert corta.items[0].cantidad is None and corta.items[0].confianza is None

    def test_el_prompt_solo_nombra_campos_que_el_esquema_define(self):
        """El prompt pide `cantidad`, `grados` y `completa` por nombre: no puede nombrar uno inexistente."""
        nombrados = set(re.findall(r"`(\w+)`", gemini._PROMPT))
        definidos = set(gemini._ESQUEMA["properties"]) | set(
            gemini._ESQUEMA["properties"]["items"]["items"]["properties"]
        )

        assert nombrados == {"cantidad", "grados", "completa"}
        assert nombrados <= definidos
