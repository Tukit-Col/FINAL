"""NFR-MAN-01: los logs llevan el id de correlacion en texto humano y en JSON (`registro.py`).

Un fallo cruza cinco servicios; el id de correlacion es el hilo que los une en el
agregador. Se prueba por el handler real que instala `configurar_registro` en el
logger raiz (con su salida redirigida a un buffer): el formato humano de
desarrollo, el JSON de un agregador (una linea parseable por registro, con
acentos y excepcion), que el id se lee del contexto en cada registro y no al
configurar, que la configuracion es idempotente y que el nivel sale del entorno.

El logger raiz es global al proceso: cada prueba parte de un raiz sin el handler
de Tukit y lo deja como lo encontro. Se caracteriza ademas un defecto conocido
(H-C-09): el JSON no lleva marca de tiempo ni nombre del servicio.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest
from tukit_comun.http import fijar_correlacion, reset_correlacion
from tukit_comun.registro import _FormatoJSON, configurar_registro

pytestmark = pytest.mark.nfr("NFR-MAN-01")

_log = logging.getLogger("tukit.prueba.registro")


@pytest.fixture
def raiz(monkeypatch: pytest.MonkeyPatch) -> Iterator[logging.Logger]:
    """Logger raiz sin el handler de Tukit; al salir queda exactamente como estaba."""
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    nivel = raiz.level
    for handler in antes:
        if getattr(handler, "_tukit", False):
            raiz.removeHandler(handler)
    monkeypatch.delenv("TUKIT_LOG_JSON", raising=False)
    monkeypatch.delenv("TUKIT_LOG_NIVEL", raising=False)
    yield raiz
    for handler in list(raiz.handlers):
        if handler not in antes:
            raiz.removeHandler(handler)
    for handler in antes:
        if handler not in raiz.handlers:
            raiz.addHandler(handler)
    raiz.setLevel(nivel)


def _handler_de_tukit(raiz: logging.Logger) -> logging.StreamHandler:
    (handler,) = [h for h in raiz.handlers if getattr(h, "_tukit", False)]
    return handler


def _salida(raiz: logging.Logger) -> io.StringIO:
    """Redirige el handler de Tukit a un buffer para leer lo que escribiria."""
    buffer = io.StringIO()
    _handler_de_tukit(raiz).setStream(buffer)
    return buffer


class TestFormatoHumano:
    def test_la_correlacion_de_la_peticion_sale_entre_corchetes(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        token = fijar_correlacion("req-uno")
        try:
            _log.info("pedido %s creado", "p-1")
        finally:
            reset_correlacion(token)

        assert buffer.getvalue() == "INFO tukit.prueba.registro [req-uno] pedido p-1 creado\n"

    def test_fuera_de_una_peticion_la_correlacion_es_un_guion(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        _log.warning("trabajo de fondo")

        assert buffer.getvalue() == "WARNING tukit.prueba.registro [-] trabajo de fondo\n"

    def test_el_id_se_lee_en_cada_registro_no_al_configurar(self, raiz):
        """Si se congelara al configurar, todas las peticiones llevarian el mismo id."""
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        for cid in ("req-a", "req-b"):
            token = fijar_correlacion(cid)
            try:
                _log.info("hola")
            finally:
                reset_correlacion(token)
        _log.info("sin peticion")

        lineas = buffer.getvalue().splitlines()
        assert [linea.split("[")[1].split("]")[0] for linea in lineas] == ["req-a", "req-b", "-"]


class TestFormatoJSON:
    @pytest.fixture(autouse=True)
    def _json(self, raiz, monkeypatch):
        # Depende de `raiz` para que la variable se ponga DESPUES de limpiar el entorno.
        monkeypatch.setenv("TUKIT_LOG_JSON", "1")

    def test_una_linea_json_por_registro_con_nivel_logger_mensaje_y_correlacion(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        token = fijar_correlacion("req-json")
        try:
            _log.error("pago %s rechazado", "pg-7")
        finally:
            reset_correlacion(token)

        (linea,) = buffer.getvalue().splitlines()
        assert json.loads(linea) == {
            "nivel": "ERROR",
            "logger": "tukit.prueba.registro",
            "mensaje": "pago pg-7 rechazado",
            "correlacion": "req-json",
        }

    def test_los_acentos_se_conservan_y_cada_registro_es_una_sola_linea(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        _log.info("Año escolar\ncon salto de linea")

        (linea,) = buffer.getvalue().splitlines()  # el salto del mensaje va escapado
        assert "Año escolar" in linea
        assert json.loads(linea)["mensaje"] == "Año escolar\ncon salto de linea"

    def test_una_excepcion_se_adjunta_con_su_traza(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        try:
            raise RuntimeError("fallo de prueba")
        except RuntimeError:
            _log.exception("el pago reventó")

        cuerpo = json.loads(buffer.getvalue().splitlines()[0])
        assert cuerpo["nivel"] == "ERROR"
        assert cuerpo["excepcion"].startswith("Traceback (most recent call last):")
        assert cuerpo["excepcion"].rstrip().endswith("RuntimeError: fallo de prueba")

    def test_sin_excepcion_no_hay_clave_de_excepcion(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        _log.info("todo bien")

        assert "excepcion" not in json.loads(buffer.getvalue())

    def test_un_registro_que_no_paso_por_el_filtro_se_marca_sin_correlacion(self):
        registro = logging.LogRecord("tukit.x", logging.INFO, __file__, 1, "mensaje %s", ("suelto",), None)

        cuerpo = json.loads(_FormatoJSON().format(registro))

        assert cuerpo["correlacion"] == "-"
        assert cuerpo["mensaje"] == "mensaje suelto"

    @pytest.mark.xfail(
        strict=True,
        reason="H-C-09: el log JSON no lleva marca de tiempo (ts) ni nombre del servicio",
    )
    def test_cada_linea_dice_cuando_y_de_que_servicio_viene(self, raiz):
        """Un agregador que junta cinco servicios necesita ordenar por tiempo y
        filtrar por servicio. Evidencia: registro.py:34-39 arma el cuerpo solo con
        nivel, logger, mensaje y correlacion, y `configurar_registro(titulo)`
        (registro.py:45) recibe el nombre del servicio pero no lo usa."""
        configurar_registro("tukit-catalogo")
        buffer = _salida(raiz)

        _log.info("arranque")

        cuerpo = json.loads(buffer.getvalue())
        assert cuerpo.get("ts")
        assert cuerpo.get("servicio") == "tukit-catalogo"


class TestConfiguracion:
    def test_es_idempotente_cada_app_la_llama_y_hay_un_solo_handler(self, raiz):
        configurar_registro("Servicio Uno")
        configurar_registro("Servicio Dos")
        configurar_registro("Servicio Tres")

        assert len([h for h in raiz.handlers if getattr(h, "_tukit", False)]) == 1

    def test_el_filtro_deja_pasar_todos_los_registros(self, raiz):
        """El filtro anota; nunca descarta."""
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        for nivel in (logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            _log.log(nivel, "registro")

        assert len(buffer.getvalue().splitlines()) == 4

    def test_el_nivel_por_omision_es_info(self, raiz):
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        _log.debug("ruido de depuracion")
        _log.info("dato util")

        assert raiz.level == logging.INFO
        assert buffer.getvalue().splitlines() == ["INFO tukit.prueba.registro [-] dato util"]

    def test_el_nivel_sale_del_entorno(self, raiz, monkeypatch):
        monkeypatch.setenv("TUKIT_LOG_NIVEL", "DEBUG")
        configurar_registro("Servicio Ficticio")
        buffer = _salida(raiz)

        _log.debug("ruido de depuracion")

        assert raiz.level == logging.DEBUG
        assert buffer.getvalue() == "DEBUG tukit.prueba.registro [-] ruido de depuracion\n"

    def test_con_un_handler_de_tukit_ya_puesto_no_pisa_el_nivel(self, raiz, monkeypatch):
        configurar_registro("Servicio Ficticio")
        handler = _handler_de_tukit(raiz)
        monkeypatch.setenv("TUKIT_LOG_NIVEL", "ERROR")

        configurar_registro("Otro Servicio")

        assert _handler_de_tukit(raiz) is handler
        assert raiz.level == logging.INFO
