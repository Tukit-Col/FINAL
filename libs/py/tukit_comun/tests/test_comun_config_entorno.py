"""NFR-MAN-01: la URL de cada base sale del entorno y solo del entorno (`config.py`).

El contrato que protege la funcion de aptitud "ningun servicio nombra la base de
otro": la URL completa de un servicio gana sobre las piezas, las piezas tienen
valores de desarrollo, y el nombre de la base se deriva del argumento. Se fija
esa precedencia y cada pieza por separado, porque un `TUKIT_DB_PORT` ignorado no
falla en la prueba sino en la maquina de otro.

Tambien se caracteriza un defecto: la URL se arma por interpolacion, sin escapar
las credenciales, asi que una clave con `@` o `/` produce una URL que apunta a
OTRO host. Los datos son ficticios.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url
from tukit_comun.config import ConfigBD, url_desde_entorno

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PIEZAS = ("TUKIT_DB_HOST", "TUKIT_DB_PORT", "TUKIT_DB_USER", "TUKIT_DB_PASSWORD")
SERVICIOS = ("identidad", "catalogo", "comercio", "inteligencia", "operacion", "gateway")


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una maquina de desarrollo puede tener estas variables puestas: se parte de cero."""
    for nombre in PIEZAS:
        monkeypatch.delenv(nombre, raising=False)
    for servicio in SERVICIOS:
        monkeypatch.delenv(f"TUKIT_{servicio.upper()}_DB_URL", raising=False)


class TestLaUrlCompletaGanaSobreLasPiezas:
    def test_se_devuelve_tal_cual_sin_tocarla(self, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_DB_URL", "postgresql+asyncpg://u:c@bd.example.test:6543/otra")
        monkeypatch.setenv("TUKIT_DB_HOST", "ignorado.example.test")

        assert url_desde_entorno("catalogo") == "postgresql+asyncpg://u:c@bd.example.test:6543/otra"

    def test_cada_servicio_lee_solo_la_suya(self, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_DB_URL", "postgresql+asyncpg://u:c@catalogo.example.test/x")

        assert url_desde_entorno("catalogo").endswith("/x")
        assert (
            url_desde_entorno("identidad")
            == "postgresql+asyncpg://tukit:tukit@localhost:5432/tukit_identidad"
        )

    def test_una_variable_vacia_cuenta_como_ausente(self, monkeypatch):
        monkeypatch.setenv("TUKIT_COMERCIO_DB_URL", "")

        assert (
            url_desde_entorno("comercio") == "postgresql+asyncpg://tukit:tukit@localhost:5432/tukit_comercio"
        )


class TestLasPiezasComunesArmanLaUrlDeDesarrollo:
    def test_sin_nada_en_el_entorno_usa_los_valores_de_desarrollo(self):
        assert (
            url_desde_entorno("catalogo") == "postgresql+asyncpg://tukit:tukit@localhost:5432/tukit_catalogo"
        )

    @pytest.mark.parametrize("servicio", SERVICIOS)
    def test_el_nombre_de_la_base_se_deriva_del_servicio(self, servicio):
        assert url_desde_entorno(servicio).endswith(f"/tukit_{servicio}")

    def test_cada_pieza_del_entorno_llega_a_su_lugar_en_la_url(self, monkeypatch):
        monkeypatch.setenv("TUKIT_DB_HOST", "bd.example.test")
        monkeypatch.setenv("TUKIT_DB_PORT", "6543")
        monkeypatch.setenv("TUKIT_DB_USER", "usuario_ficticio")
        monkeypatch.setenv("TUKIT_DB_PASSWORD", "clave_ficticia")

        url = make_url(url_desde_entorno("operacion"))

        assert (url.host, url.port, url.username, url.password, url.database) == (
            "bd.example.test",
            6543,
            "usuario_ficticio",
            "clave_ficticia",
            "tukit_operacion",
        )

    def test_el_puerto_llega_como_entero_aunque_el_entorno_sea_texto(self, monkeypatch):
        monkeypatch.setenv("TUKIT_DB_PORT", "15432")

        assert make_url(url_desde_entorno("catalogo")).port == 15432

    def test_un_puerto_que_no_es_numero_falla_al_armar_la_url_no_al_conectar(self, monkeypatch):
        monkeypatch.setenv("TUKIT_DB_PORT", "cinco-mil")

        with pytest.raises(ValueError, match="cinco-mil"):
            url_desde_entorno("catalogo")

    def test_el_driver_sincrono_se_elige_con_async_falso(self):
        assert url_desde_entorno("catalogo", async_=False).startswith("postgresql+psycopg://")
        assert url_desde_entorno("catalogo", async_=True).startswith("postgresql+asyncpg://")


class TestConfigBD:
    def test_los_valores_por_omision_son_los_de_desarrollo_local(self):
        cfg = ConfigBD()

        assert (cfg.host, cfg.puerto, cfg.usuario, cfg.clave, cfg.base) == (
            "localhost",
            5432,
            "tukit",
            "tukit",
            "",
        )

    def test_url_arma_driver_credenciales_host_puerto_y_base(self):
        cfg = ConfigBD(host="bd.example.test", puerto=6543, usuario="u", clave="c", base="tukit_x")

        assert cfg.url() == "postgresql+asyncpg://u:c@bd.example.test:6543/tukit_x"
        assert cfg.url(async_=False) == "postgresql+psycopg://u:c@bd.example.test:6543/tukit_x"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-04: ConfigBD.url() no escapa las credenciales: una clave con @ o / "
            "produce una URL que apunta a otro host"
        ),
    )
    def test_una_clave_con_caracteres_reservados_no_cambia_el_destino(self):
        """Evidencia: config.py:33 interpola `usuario` y `clave` en crudo. Con la
        clave ficticia `p@ss/w:rd` la URL resultante se interpreta como host `ss`,
        usuario `tukit`, clave `p`: la conexion iria a otro servidor y la clave
        real quedaria en el nombre de la base. Una clave generada con simbolos es
        lo normal en un gestor de secretos."""
        cfg = ConfigBD(host="bd.example.test", usuario="usuario_ficticio", clave="p@ss/w:rd", base="tukit_x")

        url = make_url(cfg.url())

        assert (url.host, url.password, url.database) == ("bd.example.test", "p@ss/w:rd", "tukit_x")

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-04: ConfigBD se documenta como inmutable pero admite asignar sus campos",
    )
    def test_es_inmutable_una_vez_armada(self):
        """Evidencia: config.py:23 dice "Inmutable una vez armada" y el modelo
        (config.py:22) no esta congelado: `cfg.host = ...` cambia el destino de
        una configuracion ya compartida."""
        cfg = ConfigBD(host="bd.example.test")

        with pytest.raises(ValueError, match="frozen"):
            cfg.host = "otro.example.test"
