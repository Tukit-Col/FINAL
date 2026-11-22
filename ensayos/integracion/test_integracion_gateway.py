"""La puerta contra el stack vivo: ruteo por prefijo, rutas internas y destino caido.

Lo que caracterizan las pruebas unitarias del gateway con un transporte falso se
repite aqui con los seis procesos de verdad: cada prefijo de `RUTAS` llega al
servicio que lo atiende, la ruta interna `/v1/comercio/pedidos-pagados` no se
distingue de una que no existe, y un servicio caido se responde con un 503 claro.

Para cortar un destino no se apaga el stack compartido: se levanta una segunda
puerta en otro puerto con la URL de comercio apuntando a un servidor que el
ensayo controla (cerrado, que corta la conexion o que nunca contesta).
"""

from __future__ import annotations

import http.client
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from stack_vivo import GATEWAY, como_json, instancia, puerto_libre
from tukit_comun.http import CABECERA_CORRELACION
from tukit_gateway.api import RUTAS, RUTAS_BLOQUEADAS

pytestmark = pytest.mark.integracion

# Un pedido que no existe: lo que importa es quien contesta, no el pedido.
_PEDIDO_QA = "00000000-0000-0000-0000-000000000000"

# Una ruta GET que existe en cada servicio y no necesita sesion ni datos. Para
# los prefijos de escritura o con sesion basta con que conteste el servicio y
# no la puerta: el 404 de la puerta trae `ruta_desconocida`.
_RUTA_DE_PRUEBA = {
    "/v1/catalogo": "/v1/catalogo/categorias",
    "/v1/listas": "/v1/listas",
    "/v1/colegios": "/v1/colegios",
    "/v1/grados": "/v1/grados",
    "/v1/comercio": "/v1/comercio/pedidos",
    "/v1/operacion": "/v1/operacion/metricas",
    # Desde 173ee80 la puerta solo expone el avance bajo `/v1/ordenes` (CONTRATO_API §9);
    # un GET ahi lo contesta comercio (405), no la puerta.
    "/v1/ordenes": f"/v1/ordenes/{_PEDIDO_QA}/avanzar",
}


def _lo_atendio_la_puerta(respuesta: httpx.Response) -> bool:
    cuerpo = como_json(respuesta.content)
    return isinstance(cuerpo, dict) and cuerpo.get("error") == "ruta_desconocida"


def _crudo(camino: str) -> tuple[int, dict[str, str], bytes]:
    """GET sin normalizar el camino: httpx colapsa `.` y `..` antes de mandar."""
    partes = urlsplit(GATEWAY)
    conexion = http.client.HTTPConnection(partes.hostname, partes.port, timeout=30)
    try:
        conexion.request("GET", camino)
        respuesta = conexion.getresponse()
        return respuesta.status, dict(respuesta.getheaders()), respuesta.read()
    finally:
        conexion.close()


# --------------------------------------------------------------- contrato


@pytest.mark.nfr("NFR-SEG-05")
@pytest.mark.parametrize("prefijo", sorted(RUTAS))
def test_cada_prefijo_llega_al_servicio_que_lo_atiende(cliente: httpx.Client, prefijo: str):
    """Ningun prefijo del mapa se queda en la puerta: lo contesta el servicio."""
    camino = _RUTA_DE_PRUEBA.get(prefijo, prefijo)
    respuesta = cliente.get(camino)

    assert respuesta.status_code != 503, respuesta.text
    assert not _lo_atendio_la_puerta(respuesta), f"{camino}: {respuesta.text[:200]}"


@pytest.mark.nfr("NFR-SEG-05")
@pytest.mark.parametrize("bloqueada", sorted(RUTAS_BLOQUEADAS))
def test_la_ruta_interna_se_responde_igual_que_una_desconocida(cliente: httpx.Client, bloqueada: str):
    """Mismo estado, mismas cabeceras y mismo cuerpo (salvo el camino que cita)."""
    desconocida = "/v1/no-existe-qa"
    interna = cliente.get(bloqueada)
    ajena = cliente.get(desconocida)

    assert interna.status_code == ajena.status_code == 404
    variables = {"date", "content-length", CABECERA_CORRELACION}
    assert sorted(set(interna.headers) - variables) == sorted(set(ajena.headers) - variables)
    cuerpo_interna = como_json(interna.content)
    cuerpo_ajena = como_json(ajena.content)
    cuerpo_ajena["mensaje"] = cuerpo_ajena["mensaje"].replace(desconocida, bloqueada)
    assert cuerpo_interna == cuerpo_ajena
    assert bloqueada not in cuerpo_interna["rutas"]


@pytest.mark.nfr("NFR-SEG-05")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-31: una ruta desconocida bajo /v1/comercio la contesta comercio con "
        '{"detail":"Not Found"} y cabeceras duplicadas; la interna, la puerta con ruta_desconocida'
    ),
)
@pytest.mark.parametrize("bloqueada", sorted(RUTAS_BLOQUEADAS))
def test_la_ruta_interna_no_se_distingue_de_una_hermana_inexistente(cliente: httpx.Client, bloqueada: str):
    """Desde fuera no debe poder saberse que la ruta interna existe."""
    prefijo = bloqueada.rsplit("/", 1)[0]
    hermana = f"{prefijo}/no-existe-qa"
    interna = cliente.get(bloqueada)
    vecina = cliente.get(hermana)

    assert interna.status_code == vecina.status_code == 404
    assert como_json(vecina.content).get("error") == como_json(interna.content).get("error"), vecina.text[
        :200
    ]
    assert sorted(vecina.headers.keys()) == sorted(interna.headers.keys())


@pytest.mark.nfr("NFR-SEG-05")
@pytest.mark.parametrize(
    "camino",
    ["/v1/comercio/x/../pedidos-pagados", "/v1/comercio/./pedidos-pagados"],
    ids=["punto-punto", "punto"],
)
def test_los_segmentos_de_punto_no_esquivan_el_bloqueo(stack: dict[str, Any], camino: str):
    """Control de no regresion de H-A-06: desde 173ee80 `ambigua` (`tukit_gateway/api.py:178`)
    rechaza cualquier camino con un segmento `.` o `..` antes de comparar con las bloqueadas."""
    estado, _, datos = _crudo(camino)

    assert estado == 404
    cuerpo = como_json(datos)
    assert isinstance(cuerpo, dict) and cuerpo.get("error") == "ruta_desconocida", datos[:200]


@pytest.mark.nfr("NFR-SEG-05")
@pytest.mark.parametrize(
    ("metodo", "camino"),
    [
        ("POST", "/v1/ordenes"),
        ("GET", f"/v1/ordenes/{_PEDIDO_QA}"),
        ("POST", f"/v1/ordenes/{_PEDIDO_QA}/pago"),
        ("POST", f"/v1/ordenes/{_PEDIDO_QA}/cancelar"),
        ("POST", f"/v1/ordenes/{_PEDIDO_QA}/retracto"),
    ],
    ids=["crear", "leer", "pagar", "cancelar", "retractar"],
)
def test_bajo_ordenes_la_puerta_solo_expone_el_avance(cliente: httpx.Client, metodo: str, camino: str):
    """CONTRATO_API §9 (173ee80, `bloqueada` en `tukit_gateway/api.py:191`): crear, leer, pagar,
    cancelar y retractar una orden son llamadas internas; la puerta las contesta como desconocidas."""
    respuesta = cliente.request(metodo, camino, json={})

    assert respuesta.status_code == 404, respuesta.text[:200]
    assert _lo_atendio_la_puerta(respuesta), respuesta.text[:200]


@pytest.mark.nfr("NFR-SEG-05")
def test_el_correlacion_id_del_borde_vuelve_en_la_respuesta(cliente: httpx.Client, correlacion_id: str):
    respuesta = cliente.get("/v1/grados")

    assert respuesta.status_code == 200
    assert respuesta.headers[CABECERA_CORRELACION] == correlacion_id


# --------------------------------------------------------------- destino caido


class _Servidor:
    """Un servidor TCP que cuenta conexiones y o las corta o no contesta nunca."""

    def __init__(self, modo: str) -> None:
        self.modo = modo
        self.conexiones = 0
        self._abiertas: list[socket.socket] = []
        self._oyente = socket.socket()
        self._oyente.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._oyente.bind(("127.0.0.1", 0))
        self._oyente.listen(64)
        self._oyente.settimeout(0.2)
        self.puerto = self._oyente.getsockname()[1]
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._atender, daemon=True)

    def _atender(self) -> None:
        while not self._parar.is_set():
            try:
                conexion, _ = self._oyente.accept()
            except OSError:
                continue
            self.conexiones += 1
            if self.modo == "corta":
                conexion.close()
            else:
                self._abiertas.append(conexion)

    def __enter__(self) -> _Servidor:
        self._hilo.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._parar.set()
        self._hilo.join(timeout=2)
        for conexion in self._abiertas:
            conexion.close()
        self._oyente.close()


@pytest.fixture
def puerta_con_comercio_en(tmp_path: Path):
    """Fabrica de puertas aparte cuyo comercio apunta al puerto que se le pase."""

    def _puerta(puerto: int):
        return instancia(
            "tukit_gateway.api",
            tmp_path / f"gateway-{puerto}.log",
            TUKIT_COMERCIO_URL=f"http://127.0.0.1:{puerto}",
        )

    return _puerta


@pytest.mark.nfr("NFR-DIS-05")
def test_con_el_servicio_caido_la_puerta_responde_503_y_rapido(puerta_con_comercio_en, correlacion_id: str):
    """Un destino que no escucha da 503 `servicio_no_disponible` en menos de 2 s."""
    with puerta_con_comercio_en(puerto_libre()) as base:
        inicio = time.monotonic()
        respuesta = httpx.get(
            f"{base}/v1/comercio/pedidos", headers={CABECERA_CORRELACION: correlacion_id}, timeout=30
        )
        segundos = time.monotonic() - inicio

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "servicio_no_disponible"
    assert "comercio" in respuesta.json()["mensaje"]
    assert segundos < 2.0


@pytest.mark.nfr("NFR-DIS-05")
def test_los_demas_servicios_siguen_atendiendo_con_uno_caido(puerta_con_comercio_en):
    with puerta_con_comercio_en(puerto_libre()) as base:
        caido = httpx.get(f"{base}/v1/comercio/pedidos", timeout=30)
        sano = httpx.get(f"{base}/v1/grados", timeout=30)
        estado = httpx.get(f"{base}/v1/servicios", timeout=30).json()

    assert caido.status_code == 503
    assert sano.status_code == 200
    assert estado["todos_arriba"] is False
    assert estado["servicios"]["comercio"]["arriba"] is False
    assert estado["servicios"]["identidad"]["arriba"] is True


@pytest.mark.nfr("NFR-DIS-05")
# H-A-33 (disyuntor): corregido en fix/hallazgos-qa; sale XPASS(strict) en la corrida del Mac y se quita el xfail.
def test_tras_cinco_fallos_la_puerta_deja_de_tocar_el_destino(puerta_con_comercio_en):
    """Con el umbral del disyuntor de FINAL (5, `resiliencia.py:33`), la sexta no conecta."""
    with _Servidor("corta") as servidor, puerta_con_comercio_en(servidor.puerto) as base:
        estados = [httpx.get(f"{base}/v1/comercio/pedidos", timeout=30).status_code for _ in range(8)]
        conexiones = servidor.conexiones

    assert estados == [503] * 8
    assert conexiones <= 5, f"el destino recibio {conexiones} conexiones en 8 peticiones"


# ESC-R2 (ATAM:1209): circuito abierto en <= 30 s y ninguna pantalla sin mensaje.
_TOPE_ESC_R2_SEGUNDOS = 30.0


@pytest.fixture
def servidor_mudo() -> Iterator[_Servidor]:
    with _Servidor("mudo") as servidor:
        yield servidor


@pytest.mark.nfr("NFR-DIS-05")
# H-A-33 (espera corta): corregido en fix/hallazgos-qa; sale XPASS(strict) en la corrida del Mac y se quita el xfail.
def test_un_destino_que_no_contesta_se_corta_antes_del_tope_de_esc_r2(puerta_con_comercio_en, servidor_mudo):
    with puerta_con_comercio_en(servidor_mudo.puerto) as base:
        inicio = time.monotonic()
        try:
            respuesta = httpx.get(f"{base}/v1/comercio/pedidos", timeout=_TOPE_ESC_R2_SEGUNDOS + 5)
        except httpx.TimeoutException:
            pytest.fail(f"sin respuesta de la puerta en {_TOPE_ESC_R2_SEGUNDOS + 5:.0f} s")
        segundos = time.monotonic() - inicio

    assert respuesta.status_code in (503, 504)
    assert segundos <= _TOPE_ESC_R2_SEGUNDOS
