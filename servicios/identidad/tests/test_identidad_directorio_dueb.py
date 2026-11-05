"""NFR-MAN-01: el indice del directorio DUEB, su parser contra volcados reales y su herramienta.

`test_directorio_bogota.py` fija el parser sobre un bloque de ejemplo y el
identificador derivado del DANE. Lo que faltaba es lo que rodea al parser y
decide si el directorio sirve en la practica:

- el indice por DANE (`datos_colegio_nuevo_por_dane`, `ficha_directorio_por_dane`)
  que usa `GET /v1/directorio/{dane}`: se parsea una sola vez, resuelve el
  DANE o devuelve `None`, y tolera un volcado con bytes danados;
- el volcado versionado en el repositorio: cada colegio indexado trae un DANE de
  12 digitos y un nombre, porque sin ellos no habria identificador estable;
- la herramienta `_main` que genera el JSON de busqueda del web app;
- la conducta del parser ante lineas de continuacion (un EMAIL que se parte en
  varias filas sin etiqueta), que hoy pierde campos en silencio.

Todos los colegios de las pruebas sinteticas son ficticios (DANE `9000000000xx`,
correos `@example.test`). El volcado real es un directorio PUBLICO de
instituciones, no contiene datos de menores.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest
from tukit_comun import derivar
from tukit_identidad.dominio import directorio
from tukit_identidad.dominio.directorio import (
    datos_colegio_nuevo_por_dane,
    ficha_directorio_por_dane,
    generar_json_busqueda,
    parsear_directorio,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

_VOLCADO_FICTICIO = """DIRECTORIO FICTICIO DE PRUEBA
Total de colegios: 2
Fuente: https://directorio.example.test/
==============================================================================

NOMBRE       : COLEGIO FICTICIO ZETA
DANE 12      : 900000000002
SECTOR       : OFICIAL
LOCALIDAD    : LOCALIDAD FICTICIA
DIRECCION    : CALLE 1 # 2 - 3
TELEFONO     : 3000000000  --  3000000001
EMAIL        : zeta@example.test  --  zeta2@example.test
WEB          : http://zeta.example.test:8080/inicio
RECTOR       : RECTOR FICTICIO ZETA

NOMBRE       : COLEGIO FICTICIO ALFA
DANE 12      : 900000000001
SECTOR       : NO OFICIAL
LOCALIDAD    : LOCALIDAD FICTICIA
DIRECCION    :
TELEFONO     :
EMAIL        :
WEB          :
RECTOR       : RECTOR FICTICIO ALFA
"""


@pytest.fixture
def indice_ficticio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Apunta el indice a un volcado ficticio y borra la cache de DANE.

    `_FUENTE` se resuelve como `Path(__file__).parent.parent / _FUENTE`; una
    ruta absoluta reemplaza a la base, asi no se toca el volcado versionado.
    `monkeypatch` devuelve ambos valores a su estado original al terminar.
    """
    ruta = tmp_path / "volcado_ficticio.txt"
    ruta.write_text(_VOLCADO_FICTICIO, encoding="utf-8")
    monkeypatch.setattr(directorio, "_FUENTE", str(ruta))
    monkeypatch.setattr(directorio, "_POR_DANE", None)
    return ruta


class TestParserConVolcadosRaros:
    def test_el_ultimo_bloque_se_cierra_aunque_el_archivo_no_termine_en_linea_en_blanco(self):
        texto = "NOMBRE : COLEGIO FICTICIO UNO\nDANE 12 : 900000000003"

        [colegio] = parsear_directorio(texto)

        assert (colegio.dane, colegio.nombre) == ("900000000003", "COLEGIO FICTICIO UNO")

    def test_una_etiqueta_desconocida_dentro_del_bloque_no_lo_corta_ni_se_guarda(self):
        texto = (
            "NOMBRE : COLEGIO FICTICIO UNO\n"
            "OBSERVACION : texto que el DUEB agrego\n"
            "DANE 12 : 900000000003\n"
            "RECTOR : RECTOR FICTICIO UNO\n"
        )

        [colegio] = parsear_directorio(texto)

        assert colegio.dane == "900000000003"
        assert colegio.rector == "RECTOR FICTICIO UNO"
        assert "OBSERVACION" not in repr(colegio)

    def test_un_bloque_con_dane_pero_sin_nombre_se_descarta(self):
        """Sin nombre no hay tarjeta que mostrar: el bloque no entra al directorio."""
        assert parsear_directorio("DANE 12 : 900000000003\nSECTOR : OFICIAL\n") == []

    def test_los_dos_puntos_dentro_del_valor_se_conservan(self):
        """Solo el primer `:` separa la etiqueta; una URL con puerto llega entera."""
        texto = (
            "NOMBRE : COLEGIO FICTICIO UNO\nDANE 12 : 900000000003\nWEB : http://uno.example.test:8080/a\n"
        )

        [colegio] = parsear_directorio(texto)

        assert colegio.sitio_web == "http://uno.example.test:8080/a"

    def test_el_multivalor_descarta_los_vacios_y_conserva_el_orden(self):
        texto = (
            "NOMBRE : COLEGIO FICTICIO UNO\n"
            "DANE 12 : 900000000003\n"
            "TELEFONO : 3000000000 --  -- 3000000001 --\n"
        )

        [colegio] = parsear_directorio(texto)

        assert colegio.telefono == "3000000000"
        assert colegio.telefonos == ("3000000000", "3000000001")

    def test_generar_json_busqueda_ordena_por_nombre_y_solo_trae_lo_del_buscador(self):
        registros = generar_json_busqueda(_VOLCADO_FICTICIO)

        # 77bb105: cada registro lleva tambien `imageURL`, el logo curado a mano (None sin curar).
        assert registros == [
            {
                "dane": "900000000001",
                "nombre": "COLEGIO FICTICIO ALFA",
                "localidad": "LOCALIDAD FICTICIA",
                "imageURL": None,
            },
            {
                "dane": "900000000002",
                "nombre": "COLEGIO FICTICIO ZETA",
                "localidad": "LOCALIDAD FICTICIA",
                "imageURL": None,
            },
        ]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-18: parsear_directorio cierra el bloque ante cualquier linea sin ':' "
            "(directorio.py:182-185) aunque su docstring (:168-170) dice que las lineas sin etiqueta "
            "conocida se ignoran; "
            "un EMAIL partido en varias filas hace perder WEB y RECTOR"
        ),
    )
    def test_una_linea_de_continuacion_sin_etiqueta_no_hace_perder_los_campos_siguientes(self):
        """En el volcado real el EMAIL de un colegio se parte en cinco filas sin
        etiqueta. Por el docstring esas filas se ignoran; hoy cierran el bloque
        y los campos que vienen despues (WEB, RECTOR) caen en un bloque sin
        DANE que se descarta, sin ningun aviso."""
        texto = (
            "NOMBRE       : COLEGIO FICTICIO UNO\n"
            "DANE 12      : 900000000003\n"
            "EMAIL        : uno@example.test\n"
            "dos@example.test\n"
            "tres@example.test\n"
            "WEB          : www.uno.example.test\n"
            "RECTOR       : RECTOR FICTICIO UNO\n"
        )

        [colegio] = parsear_directorio(texto)

        assert colegio.email == "uno@example.test"
        assert colegio.sitio_web == "www.uno.example.test"
        assert colegio.rector == "RECTOR FICTICIO UNO"


class TestIndicePorDane:
    def test_resuelve_el_dane_con_los_siete_campos_del_alta(self, indice_ficticio: Path):
        assert datos_colegio_nuevo_por_dane("900000000002") == {
            "dane": "900000000002",
            "nombre": "COLEGIO FICTICIO ZETA",
            "direccion": "CALLE 1 # 2 - 3",
            "sitio_web": "http://zeta.example.test:8080/inicio",
            "contacto_email": "zeta@example.test",
            "contacto_telefono": "3000000000",
            "contacto_nombre": "RECTOR FICTICIO ZETA",
        }

    def test_la_ficha_completa_agrega_sector_localidad_rector_y_las_listas(self, indice_ficticio: Path):
        ficha = ficha_directorio_por_dane("900000000002")
        alta = datos_colegio_nuevo_por_dane("900000000002")

        assert ficha is not None and alta is not None
        # Superconjunto aditivo: las siete claves del alta no cambian.
        assert {k: ficha[k] for k in alta} == alta
        assert ficha["sector"] == "OFICIAL"
        assert ficha["localidad"] == "LOCALIDAD FICTICIA"
        assert ficha["rector"] == "RECTOR FICTICIO ZETA"
        assert ficha["telefonos"] == ["3000000000", "3000000001"]
        assert ficha["correos"] == ["zeta@example.test", "zeta2@example.test"]

    def test_un_colegio_con_campos_vacios_devuelve_none_en_ellos_y_listas_vacias(self, indice_ficticio: Path):
        ficha = ficha_directorio_por_dane("900000000001")

        assert ficha is not None
        assert ficha["direccion"] is None
        assert ficha["contacto_email"] is None
        assert ficha["sitio_web"] is None
        assert ficha["telefonos"] == []
        assert ficha["correos"] == []

    def test_un_dane_que_no_esta_en_el_directorio_devuelve_none(self, indice_ficticio: Path):
        assert datos_colegio_nuevo_por_dane("999999999999") is None
        assert ficha_directorio_por_dane("999999999999") is None

    def test_el_volcado_se_parsea_una_sola_vez_y_despues_se_sirve_de_memoria(self, indice_ficticio: Path):
        assert directorio._POR_DANE is None  # perezoso: nadie lo parseo todavia

        primero = datos_colegio_nuevo_por_dane("900000000001")
        indice_ficticio.unlink()  # si se volviera a leer el archivo, fallaria
        segundo = datos_colegio_nuevo_por_dane("900000000001")

        assert primero is not None
        assert segundo == primero
        assert set(directorio._POR_DANE or {}) == {"900000000001", "900000000002"}

    def test_un_byte_danado_en_el_volcado_no_impide_cargar_el_directorio(self, indice_ficticio: Path):
        """Se lee con `errors="replace"`: un byte invalido se vuelve U+FFFD y el
        resto del directorio sigue disponible, en vez de tumbar la ruta."""
        indice_ficticio.write_bytes(
            b"NOMBRE : COLEGIO BILING\xbfE FICTICIO\nDANE 12 : 900000000004\n\n"
            b"NOMBRE : COLEGIO FICTICIO SANO\nDANE 12 : 900000000005\n"
        )

        danado = datos_colegio_nuevo_por_dane("900000000004")
        sano = datos_colegio_nuevo_por_dane("900000000005")

        assert danado is not None and "�" in str(danado["nombre"])
        assert sano is not None and sano["nombre"] == "COLEGIO FICTICIO SANO"


class TestVolcadoVersionado:
    """El archivo real que viaja con el paquete (`datos/colegios_bogota.txt`)."""

    def test_un_colegio_conocido_se_resuelve_con_su_ficha(self):
        ficha = ficha_directorio_por_dane("311001105731")

        assert ficha is not None
        assert ficha["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"
        assert ficha["localidad"] == "BARRIOS UNIDOS"
        assert ficha["sector"] == "NO OFICIAL"
        assert ficha["telefonos"] == ["6012352887", "3223573876"]

    def test_cada_colegio_indexado_tiene_dane_de_12_digitos_nombre_e_id_propio(self):
        """Si el volcado se truncara o el parser se rompiera, apareceria aqui:
        un colegio sin DANE de 12 digitos no podria derivar su UUID estable."""
        indice = directorio._indice_por_dane()

        assert len(indice) > 3000
        assert all(dane.isdigit() and len(dane) == 12 for dane in indice)
        assert all(colegio.nombre.strip() for colegio in indice.values())
        assert len({colegio.id for colegio in indice.values()}) == len(indice)
        assert indice["311001105731"].id == derivar("colegio", "311001105731")

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-18: el EMAIL partido en filas sin etiqueta de 'COLEGIO MADRE PAULA MONTAL' "
            "(colegios_bogota.txt:8835-8839) corta el bloque y la ficha pierde WEB y RECTOR "
            "(directorio.py:182-185)"
        ),
    )
    def test_el_colegio_con_correo_partido_conserva_su_rector_y_su_web(self):
        ficha = ficha_directorio_por_dane("311001033391")

        assert ficha is not None
        assert ficha["rector"] == "MADRE ROUSMELY SUAREZ RUIZ"
        assert ficha["sitio_web"] == "www.colegiomadrepaulamontal.edu.co"


class TestHerramientaDeDatos:
    """`_main`: del volcado DUEB al JSON que el web app sirve y busca en el cliente."""

    def test_genera_el_json_de_busqueda_ordenado_y_con_acentos_legibles(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        fuente = tmp_path / "fuente.txt"
        destino = tmp_path / "salida.json"
        fuente.write_text(
            _VOLCADO_FICTICIO + "\nNOMBRE : COLEGIO FICTICIO CAÑADA\nDANE 12 : 900000000009\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(sys, "argv", ["directorio", str(fuente), str(destino)])

        directorio._main()

        registros = json.loads(destino.read_text(encoding="utf-8"))
        assert [r["dane"] for r in registros] == ["900000000001", "900000000009", "900000000002"]
        assert registros[1] == {
            "dane": "900000000009",
            "nombre": "COLEGIO FICTICIO CAÑADA",
            "localidad": None,
            "imageURL": None,
        }
        # `ensure_ascii=False`: el archivo guarda la letra, no un escape \u00d1.
        assert "CAÑADA" in destino.read_text(encoding="utf-8")
        assert capsys.readouterr().out == f"3 colegios -> {destino}\n"

    @pytest.mark.parametrize(
        "argv", [["directorio"], ["directorio", "solo-fuente.txt"], ["d", "a", "b", "c"]]
    )
    def test_con_un_numero_de_argumentos_equivocado_imprime_el_uso_y_sale_con_2(
        self,
        argv: list[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", argv)

        with pytest.raises(SystemExit) as salida:
            directorio._main()

        assert salida.value.code == 2
        assert "Uso:" in capsys.readouterr().out
        assert list(tmp_path.iterdir()) == []  # no escribio nada

    def test_ejecutado_como_script_aplica_la_misma_validacion_de_argumentos(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        """`python -m tukit_identidad.dominio.directorio` cae en `_main()`."""
        monkeypatch.delitem(sys.modules, "tukit_identidad.dominio.directorio")
        monkeypatch.setattr(sys, "argv", ["directorio"])

        with pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_identidad.dominio.directorio", run_name="__main__")

        assert salida.value.code == 2
        assert "Uso:" in capsys.readouterr().out

    # H-A-19, corregido en 77bb105 (el uso nombra `tukit_identidad.dominio.directorio`): salia
    # XPASS(strict) en la corrida oe5 y se quito el xfail.
    def test_el_modulo_que_anuncia_el_mensaje_de_uso_existe(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        import importlib.util

        monkeypatch.setattr(sys, "argv", ["directorio"])
        with pytest.raises(SystemExit):
            directorio._main()
        uso = capsys.readouterr().out
        modulo = uso.split("python -m ", 1)[1].split()[0]

        assert importlib.util.find_spec(modulo) is not None
