"""NFR-MAN-01: `python -m` de la API, el trabajador y el poller: el codigo de `main` llega al proceso.

Los tres modulos se lanzan como proceso (`python -m tukit_inteligencia.api`,
`.trabajador`, `.poller`) y terminan con `raise SystemExit(main())`. Lo que el
orquestador (Makefile, supervisor, Compose) lee es ese codigo de salida, y en la
API ademas hay un detalle que solo existe bajo `-m`: el modulo corre como
`__main__` y se registra a si mismo en `sys.modules` bajo su nombre de paquete
para que el `from .. import api` del router no lo cargue una segunda vez (un
`ImportError` circular en produccion que ninguna prueba que importe el modulo
normalmente puede ver).

`runpy.run_module(..., run_name="__main__")` ejecuta el modulo como lo hace
`python -m`, pero dentro del proceso de prueba: por eso `uvicorn.run` y
`asyncio.run` se sustituyen por dobles (no se levanta un servidor ni se abre un
bucle ni una conexion), y los modulos que `runpy` re-ejecuta se retiran de
`sys.modules` con `monkeypatch`, que los restaura al terminar.
"""

from __future__ import annotations

import asyncio
import runpy
import sys
from typing import Any

import pytest
import uvicorn

pytestmark = pytest.mark.nfr("NFR-MAN-01")


def _ejecutar_como_modulo(monkeypatch, nombre: str, *argumentos: str) -> int | None:
    """Corre `python -m <nombre> <argumentos>` sin proceso aparte y devuelve el codigo de salida."""
    monkeypatch.setattr(sys, "argv", [nombre, *argumentos])
    monkeypatch.delitem(sys.modules, nombre, raising=False)  # que runpy lo ejecute limpio, sin aviso
    with pytest.raises(SystemExit) as salida:
        runpy.run_module(nombre, run_name="__main__", alter_sys=True)
    return salida.value.code


class TestApi:
    def test_sale_con_el_codigo_de_main_y_levanta_uvicorn_con_lo_pedido(self, monkeypatch):
        llamadas: list[dict[str, Any]] = []
        monkeypatch.setattr(uvicorn, "run", lambda _app, **kw: llamadas.append(kw))

        codigo = _ejecutar_como_modulo(monkeypatch, "tukit_inteligencia.api", "--puerto", "9100")

        assert codigo == 0
        assert llamadas == [{"host": "127.0.0.1", "port": 9100, "log_level": "info"}]

    def test_bajo_dash_m_el_modulo_se_registra_con_su_nombre_de_paquete(self, monkeypatch):
        """Sin ese registro el router vuelve a cargar `api` y cae en un ImportError circular."""
        monkeypatch.setattr(uvicorn, "run", lambda *_a, **_k: None)
        monkeypatch.setattr(sys, "argv", ["tukit_inteligencia.api"])
        monkeypatch.delitem(sys.modules, "tukit_inteligencia.api")

        with pytest.raises(SystemExit):
            runpy.run_module("tukit_inteligencia.api", run_name="__main__", alter_sys=True)

        assert "tukit_inteligencia.api" in sys.modules


class TestTrabajadorYPoller:
    @pytest.mark.parametrize(
        ("nombre", "linea"),
        [
            ("tukit_inteligencia.trabajador", "[trabajador] trabajos procesados: 3"),
            ("tukit_inteligencia.poller", "[poller] kits de ruta rapida arrancados: 3"),
        ],
    )
    def test_una_pasada_sale_con_0_e_imprime_lo_hecho(self, monkeypatch, capsys, nombre, linea):
        """`asyncio.run` es un doble: la corrutina de la pasada se cierra sin ejecutarse ni tocar una base."""
        recibidas: list[str] = []

        def _run(corrutina: Any) -> int:
            recibidas.append(corrutina.__name__)
            corrutina.close()
            return 3

        monkeypatch.setattr(asyncio, "run", _run)

        codigo = _ejecutar_como_modulo(monkeypatch, nombre)

        assert codigo == 0
        assert recibidas == ["correr_una_vez"]
        assert capsys.readouterr().out.strip() == linea

    @pytest.mark.parametrize("nombre", ["tukit_inteligencia.trabajador", "tukit_inteligencia.poller"])
    def test_seguir_corre_el_bucle_con_el_intervalo_pedido(self, monkeypatch, nombre):
        vistas: list[tuple[str, float]] = []

        def _run(corrutina: Any) -> None:
            vistas.append((corrutina.__name__, corrutina.cr_frame.f_locals["intervalo"]))
            corrutina.close()

        monkeypatch.setattr(asyncio, "run", _run)

        codigo = _ejecutar_como_modulo(monkeypatch, nombre, "--seguir", "--intervalo", "0.5")

        assert codigo == 0
        assert vistas == [("correr_en_bucle", 0.5)]
