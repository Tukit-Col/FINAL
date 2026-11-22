"""NFR-MAN-01: los adaptadores del puerto de cifrado y la eleccion por entorno.

La CI no instala `cryptography`, asi que el adaptador Fernet se prueba contra un
`cryptography.fernet` de mentira que se inyecta en `sys.modules` (un doble del
borde, con la misma interfaz `encrypt`/`decrypt`); el camino "la libreria no
esta" se fuerza igual, bloqueando el import. Asi las pruebas dicen lo mismo con
o sin la libreria real instalada y nunca necesitan una llave de verdad.

Importa por la nota del manifiesto: lo peligroso no es "no hay cifrado" sino
CREER que lo hay. Se fija que el adaptador por omision se delata (prefijo y
bandera), que una llave inservible degrada en vez de tumbar el arranque, que
nunca se imprime la llave, y que el dato escrito en claro antes de tener llave se
sigue pudiendo leer cuando el adaptador real entra.
"""

from __future__ import annotations

import sys
from types import ModuleType

import pytest
from tukit_comun.cifrado import (
    PREFIJO_EN_CLARO,
    VARIABLE_LLAVE,
    CifradorEnClaro,
    CifradorFernet,
    cifrador_desde_entorno,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

LLAVE_FALSA = "llave-valida-ficticia"


class TokenInvalido(Exception):
    """Lo que Fernet levanta cuando el token no se puede autenticar."""


class FernetFalso:
    """Doble de `cryptography.fernet.Fernet`: reversible, autenticado por prefijo."""

    def __init__(self, llave: str | bytes) -> None:
        texto = llave.decode() if isinstance(llave, bytes) else llave
        if not texto.startswith("llave-valida"):
            raise ValueError("Fernet key must be 32 url-safe base64-encoded bytes.")

    def encrypt(self, datos: bytes) -> bytes:
        return b"token:" + datos[::-1]

    def decrypt(self, datos: bytes) -> bytes:
        if not datos.startswith(b"token:"):
            raise TokenInvalido("firma invalida")
        return datos[len(b"token:") :][::-1]


@pytest.fixture
def con_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hace que `from cryptography.fernet import Fernet` encuentre el doble."""
    paquete = ModuleType("cryptography")
    paquete.__path__ = []  # un paquete, para que el import de `cryptography.fernet` prospere
    modulo = ModuleType("cryptography.fernet")
    modulo.Fernet = FernetFalso  # type: ignore[attr-defined]
    paquete.fernet = modulo  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cryptography", paquete)
    monkeypatch.setitem(sys.modules, "cryptography.fernet", modulo)


@pytest.fixture
def sin_cryptography(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fuerza el `ImportError` aunque la libreria real este instalada."""
    monkeypatch.setitem(sys.modules, "cryptography", None)
    monkeypatch.setitem(sys.modules, "cryptography.fernet", None)


class TestElAdaptadorEnClaroSeDelata:
    def test_marca_el_dato_con_un_prefijo_legible_y_no_oculta_el_contenido(self):
        guardado = CifradorEnClaro().cifrar(b"pesos")

        assert guardado == PREFIJO_EN_CLARO + b"pesos"
        assert guardado.startswith(b"claro:")

    def test_descifrar_quita_el_prefijo_y_devuelve_el_original(self):
        cifrador = CifradorEnClaro()
        assert cifrador.descifrar(cifrador.cifrar(b"\x00\xffbinario")) == b"\x00\xffbinario"

    def test_un_dato_sin_prefijo_se_lee_tal_cual_en_vez_de_perderse(self):
        assert CifradorEnClaro().descifrar(b"escrito-antes-del-prefijo") == b"escrito-antes-del-prefijo"

    def test_json_es_determinista_y_conserva_los_acentos(self):
        """`sort_keys` hace estable lo guardado (comparable y diffeable) y
        `ensure_ascii=False` no convierte una `n` con tilde en una secuencia `\\u`."""
        cifrador = CifradorEnClaro()

        a = cifrador.cifrar_json({"b": 1, "a": "Año escolar"})
        b = cifrador.cifrar_json({"a": "Año escolar", "b": 1})

        assert a == b
        assert a == PREFIJO_EN_CLARO + '{"a": "Año escolar", "b": 1}'.encode()

    def test_ida_y_vuelta_de_json_anidado(self):
        cifrador = CifradorEnClaro()
        valor = {"pesos": {"precio": 0.35, "marca": 0.25}, "lista": [1, None, True], "vacio": {}}

        assert cifrador.descifrar_json(cifrador.cifrar_json(valor)) == valor

    @pytest.mark.parametrize("vacio", [None, b""])
    def test_descifrar_json_de_nada_es_none(self, vacio):
        assert CifradorEnClaro().descifrar_json(vacio) is None

    def test_la_bandera_y_el_nombre_dicen_que_no_cifra(self):
        cifrador = CifradorEnClaro()
        assert (cifrador.nombre, cifrador.cifra_de_verdad) == ("en_claro", False)


class TestElAdaptadorFernet:
    def test_cifra_de_verdad_y_lo_dice(self, con_fernet):
        cifrador = CifradorFernet(LLAVE_FALSA)
        assert (cifrador.nombre, cifrador.cifra_de_verdad) == ("fernet", True)

    def test_el_dato_guardado_no_contiene_el_original_y_vuelve_igual(self, con_fernet):
        cifrador = CifradorFernet(LLAVE_FALSA)

        guardado = cifrador.cifrar(b"encuesta socioeconomica")

        assert b"encuesta socioeconomica" not in guardado
        assert not guardado.startswith(PREFIJO_EN_CLARO)
        assert cifrador.descifrar(guardado) == b"encuesta socioeconomica"

    def test_ida_y_vuelta_de_json(self, con_fernet):
        cifrador = CifradorFernet(LLAVE_FALSA)
        valor = {"perfil": "A", "pesos_usados": {"precio": 0.35}}

        assert cifrador.descifrar_json(cifrador.cifrar_json(valor)) == valor
        assert cifrador.descifrar_json(None) is None

    def test_lee_lo_que_se_guardo_en_claro_antes_de_haber_llave(self, con_fernet):
        """Migrar a Fernet no pierde las filas viejas: el prefijo delata de donde vienen."""
        viejo = CifradorEnClaro().cifrar_json({"precio": 0.35})

        assert CifradorFernet(LLAVE_FALSA).descifrar_json(viejo) == {"precio": 0.35}

    def test_un_token_que_no_autentica_levanta_en_vez_de_devolver_basura(self, con_fernet):
        with pytest.raises(TokenInvalido):
            CifradorFernet(LLAVE_FALSA).descifrar(b"manipulado")

    def test_una_llave_mal_formada_se_rechaza_al_construir(self, con_fernet):
        with pytest.raises(ValueError, match="32 url-safe"):
            CifradorFernet("esto-no-es-una-llave")


class TestLaEleccionPorEntorno:
    def test_con_llave_y_libreria_entra_fernet(self, monkeypatch, con_fernet):
        monkeypatch.setenv(VARIABLE_LLAVE, LLAVE_FALSA)

        cifrador = cifrador_desde_entorno()

        assert isinstance(cifrador, CifradorFernet)
        assert cifrador.descifrar_json(cifrador.cifrar_json({"x": 1})) == {"x": 1}

    def test_los_espacios_alrededor_de_la_llave_no_la_invalidan(self, monkeypatch, con_fernet):
        monkeypatch.setenv(VARIABLE_LLAVE, f"  {LLAVE_FALSA}\n")

        assert cifrador_desde_entorno().nombre == "fernet"

    @pytest.mark.parametrize("valor", ["", "   ", "\n"])
    def test_una_llave_vacia_o_en_blanco_cuenta_como_ausente(self, monkeypatch, con_fernet, valor, capsys):
        monkeypatch.setenv(VARIABLE_LLAVE, valor)

        assert cifrador_desde_entorno().nombre == "en_claro"
        assert capsys.readouterr().out == ""  # no la trata como una llave rota

    def test_con_llave_pero_sin_la_libreria_degrada_y_avisa(self, monkeypatch, sin_cryptography, capsys):
        monkeypatch.setenv(VARIABLE_LLAVE, LLAVE_FALSA)

        cifrador = cifrador_desde_entorno()

        salida = capsys.readouterr().out
        assert cifrador.nombre == "en_claro"
        assert VARIABLE_LLAVE in salida
        assert "cryptography" in salida
        assert "EN CLARO" in salida
        assert LLAVE_FALSA not in salida  # el aviso nunca imprime la llave

    def test_con_llave_mal_formada_degrada_avisa_y_no_filtra_la_llave(self, monkeypatch, con_fernet, capsys):
        monkeypatch.setenv(VARIABLE_LLAVE, "secreto-que-no-sirve")

        cifrador = cifrador_desde_entorno()

        salida = capsys.readouterr().out
        assert cifrador.nombre == "en_claro"
        assert "EN CLARO" in salida
        assert "32 url-safe" in salida  # el motivo del rechazo si se informa
        assert "secreto-que-no-sirve" not in salida

    def test_sin_llave_el_dato_guardado_es_legible_como_en_claro(self, monkeypatch):
        monkeypatch.delenv(VARIABLE_LLAVE, raising=False)

        guardado = cifrador_desde_entorno().cifrar_json({"precio": 0.35})

        assert guardado.startswith(PREFIJO_EN_CLARO)

    # H-A-03 (aviso): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    def test_sin_llave_avisa_que_se_guarda_en_claro(self, monkeypatch, capsys):
        """`cifrador_desde_entorno` promete "en claro si no, y en ese caso se
        avisa" y CONTRATO_API.md:1196 dice que sin llave "el adaptador guarda en
        claro y lo dice al arrancar". Evidencia: cifrado.py:110-121 solo imprime
        cuando la llave esta puesta pero no sirve; con la variable ausente el
        `return CifradorEnClaro()` de cifrado.py:121 no dice nada, que es el
        modo de fallar que el modulo declara querer evitar (creer que hay cifrado)."""
        monkeypatch.delenv(VARIABLE_LLAVE, raising=False)

        cifrador_desde_entorno()

        assert "EN CLARO" in capsys.readouterr().out
