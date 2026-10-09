"""NFR-MAN-01: La linea de comandos de Inteligencia: parsear, percibir y esquema, con su codigo de salida.

`python -m tukit_inteligencia` es la herramienta con la que se ensaya el pipeline
sin levantar el servicio y con la que el ejecutor de tareas materializa las
tablas. Su contrato es el codigo de salida y el JSON que imprime:

- `parsear` no necesita modelo ni base: imprime la demanda del renglon y dice si
  se busca en catalogo (un "disponible en casa" es cantidad cero y no se busca);
- `percibir` sale con 0 si el archivo se acepto y con 2 si se rechazo, y en
  ambos casos imprime el diagnostico completo (error, mensaje, paginas,
  degradaciones); sin `GEMINI_API_KEY` el rechazo es `percepcion_fallida`, jamas
  renglones inventados;
- `esquema` materializa las tablas del servicio sobre su base y sale con 0;
- un argumento mal formado o un subcomando ausente salen con 2 (argparse), sin
  traceback.

Nada abre un socket ni toca una base: la percepcion se sustituye por un doble
(o falla por falta de clave antes de abrir una conexion) y `materializar` es un
doble que anota con que servicio y que base se le llamo.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
import tukit_comun.esquema as esquema_comun
from tukit_inteligencia import __main__ as cli
from tukit_inteligencia import gemini
from tukit_inteligencia.modelos import Base
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida

pytestmark = pytest.mark.nfr("NFR-MAN-01")


def _imprimio(capsys) -> Any:
    return json.loads(capsys.readouterr().out)


@pytest.fixture()
def lista(tmp_path: Path) -> Path:
    """Una 'imagen' de lista: `renderizar` devuelve los bytes tal cual, y la lectura esta sustituida."""
    ruta = tmp_path / "lista.png"
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n-imagen-ficticia")
    return ruta


class TestParsear:
    def test_imprime_la_demanda_del_renglon_y_si_se_busca_en_catalogo(self, capsys):
        codigo = cli.main(["parsear", "2 cuadernos cuadriculados"])

        demanda = _imprimio(capsys)
        assert codigo == 0
        assert demanda["texto"] == "2 cuadernos cuadriculados"
        assert (demanda["tipo_item"], demanda["modo_adquisicion"], demanda["cantidad"]) == (
            "util",
            "mercado_abierto",
            2,
        )
        assert demanda["busca_en_catalogo"] is True

    def test_lo_que_ya_se_tiene_en_casa_es_cantidad_cero_y_no_se_busca(self, capsys):
        """Cero es la respuesta honesta de 'no compres esto', no un 'no supe leerlo'."""
        codigo = cli.main(["parsear", "Diccionario: el disponible en casa"])

        demanda = _imprimio(capsys)
        assert codigo == 0
        assert demanda["tipo_item"] == "no_comprar" and demanda["cantidad"] == 0
        assert demanda["busca_en_catalogo"] is False
        assert demanda["nota"] == "El colegio indica usar el que ya tienes."

    def test_la_cantidad_pedida_gana_sobre_el_numero_del_texto(self, capsys):
        cli.main(["parsear", "cuaderno cuadriculado", "--cantidad", "3"])

        assert _imprimio(capsys)["cantidad"] == 3

    def test_las_tildes_salen_tal_cual_y_no_escapadas(self, capsys):
        cli.main(["parsear", "Lápiz negro #2"])

        assert "Lápiz negro #2" in capsys.readouterr().out

    def test_una_cantidad_que_no_es_entera_sale_con_codigo_2(self, capsys):
        with pytest.raises(SystemExit) as salida:
            cli.main(["parsear", "cuaderno", "--cantidad", "tres"])

        assert salida.value.code == 2
        assert "--cantidad" in capsys.readouterr().err


class TestPercibir:
    def test_un_archivo_aceptado_sale_con_0_e_imprime_los_renglones_parseados(
        self, monkeypatch, capsys, lista
    ):
        def _leer(png: bytes, numero: int) -> PaginaLeida:
            return PaginaLeida(
                grados=["Cuarto"],
                items=[
                    ItemExtraido(descripcion="cuaderno cuadriculado", cantidad=2, confianza=0.9),
                    ItemExtraido(descripcion="Diccionario: el disponible en casa", confianza=0.7),
                ],
            )

        monkeypatch.setattr(gemini, "pedir_pagina", _leer)

        codigo = cli.main(["percibir", str(lista)])

        cuerpo = _imprimio(capsys)
        assert codigo == 0
        assert cuerpo["aceptada"] is True and cuerpo["error"] is None
        assert cuerpo["grados"] == ["Cuarto"] and cuerpo["paginas"] == 1
        assert cuerpo["degradaciones"] == []
        primero, segundo = cuerpo["items"]
        assert (primero["cantidad"], primero["confianza"], primero["busca_en_catalogo"]) == (2, 0.9, True)
        assert (segundo["cantidad"], segundo["busca_en_catalogo"]) == (0, False)

    def test_sin_clave_el_archivo_se_rechaza_con_2_y_sin_renglones_inventados(self, capsys, lista):
        """El conftest quita `GEMINI_API_KEY`: el adaptador real se niega antes de abrir una conexion."""
        codigo = cli.main(["percibir", str(lista)])

        cuerpo = _imprimio(capsys)
        assert codigo == 2
        assert cuerpo["aceptada"] is False
        assert cuerpo["error"] == "percepcion_fallida"
        assert "GEMINI_API_KEY" in cuerpo["mensaje"]
        assert cuerpo["items"] == []
        assert cuerpo["degradaciones"] == ["gemini"]

    def test_un_archivo_vacio_se_rechaza_con_2_sin_llamar_al_modelo(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(
            gemini, "pedir_pagina", lambda *_a: pytest.fail("un archivo vacio no se le muestra al modelo")
        )
        vacio = tmp_path / "vacio.png"
        vacio.write_bytes(b"")

        codigo = cli.main(["percibir", str(vacio)])

        assert codigo == 2
        assert _imprimio(capsys)["error"] == "archivo_vacio"

    def test_sin_archivo_en_los_argumentos_sale_con_codigo_2(self, capsys):
        with pytest.raises(SystemExit) as salida:
            cli.main(["percibir"])

        assert salida.value.code == 2
        assert "archivo" in capsys.readouterr().err


class TestEsquema:
    def test_materializa_las_tablas_del_servicio_y_sale_con_0(self, monkeypatch):
        llamadas: list[tuple[str, Any]] = []
        monkeypatch.setattr(
            esquema_comun, "materializar", lambda servicio, base: llamadas.append((servicio, base))
        )

        assert cli.main(["esquema"]) == 0

        assert llamadas == [("inteligencia", Base)]


class TestEntradaDelModulo:
    def test_sin_subcomando_sale_con_codigo_2(self, capsys):
        with pytest.raises(SystemExit) as salida:
            cli.main([])

        assert salida.value.code == 2
        assert "comando" in capsys.readouterr().err

    def test_un_subcomando_desconocido_sale_con_codigo_2(self, capsys):
        with pytest.raises(SystemExit) as salida:
            cli.main(["inventar"])

        assert salida.value.code == 2
        assert "inventar" in capsys.readouterr().err

    def test_python_dash_m_entrega_el_codigo_de_main_al_proceso(self, monkeypatch, capsys):
        """`python -m tukit_inteligencia ...` termina con `sys.exit(main())`: el codigo llega al shell."""
        monkeypatch.setattr(sys, "argv", ["tukit_inteligencia", "parsear", "2 lapices"])
        # Ya importado arriba: se retira de `sys.modules` (monkeypatch lo restaura) para ejecutarlo limpio.
        monkeypatch.delitem(sys.modules, "tukit_inteligencia.__main__")

        with pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_inteligencia.__main__", run_name="__main__")

        assert salida.value.code == 0
        assert json.loads(capsys.readouterr().out)["cantidad"] == 2
