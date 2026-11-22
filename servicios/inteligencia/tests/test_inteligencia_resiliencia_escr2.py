"""Fase 6 de QA, NFR-DIS-05: cuanto tarda en abrirse el disyuntor de catalogo (ESC-R2).

ESC-R2 (ATAM v2.0) pide el «cortacircuito abierto en <= 30 s, contados desde la
primera llamada fallida». `test_remoto_clientes.py` ya fija que el circuito se
abre tras cinco fallos; aqui se mide CUANDO, con un catalogo que no contesta:

- cada peticion espera su timeout entero antes de fallar, que es lo que hace
  un destino colgado. El timeout es el del pool que `_arrancar` le inyecta al
  cliente, `crear_pool(espera=ESPERA_SEGUNDOS)`: 60 s;
- los GET (`lista`) se reintentan tres veces con backoff, asi que cada llamada
  cuesta tres timeouts; los POST (`emparejar`) no se reintentan.

El reloj es falso: el destino lo adelanta el timeout de la peticion y el
`asyncio.sleep` del backoff lo adelanta lo que duerme. El disyuntor de
catalogo se crea con ese reloj. Nada duerme de verdad y nada sale de la maquina.

El control usa un catalogo que rechaza la conexion al instante: ahi el umbral
de cinco fallos cabe en menos de un segundo, y lo que sobra en el caso colgado
es el timeout de 60 s multiplicado por el reintento (H-A-55).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from tukit_comun import resiliencia
from tukit_comun.resiliencia import Disyuntor
from tukit_inteligencia.remoto import ESPERA_SEGUNDOS, ClienteCatalogo, RemotoCaido

pytestmark = pytest.mark.nfr("NFR-DIS-05")

TOPE_ESC_R2 = 30.0  # segundos, ATAM v2.0, ESC-R2
BASE = "http://catalogo.prueba"
LLAMADAS = {
    "lista": lambda cliente: cliente.lista("lista-ficticia-qa"),
    "emparejar": lambda cliente: cliente.emparejar(["Cuaderno ficticio de 100 hojas"]),
}


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class CatalogoQueFalla:
    """Un catalogo que falla cada peticion, colgado (gasta el timeout) o rechazando la conexion."""

    def __init__(self, reloj: Reloj, *, colgado: bool) -> None:
        self.reloj = reloj
        self.colgado = colgado
        self.fin_de_cada_toque: list[float] = []
        self.esperas: list[float] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        if self.colgado:
            espera = peticion.extensions["timeout"]["read"]
            self.esperas.append(espera)
            self.reloj.t += espera
            self.fin_de_cada_toque.append(self.reloj.t)
            raise httpx.ReadTimeout("el catalogo no contesto", request=peticion)
        self.fin_de_cada_toque.append(self.reloj.t)
        raise httpx.ConnectError("conexion rechazada", request=peticion)


@pytest.fixture
def reloj(monkeypatch: pytest.MonkeyPatch) -> Reloj:
    """El reloj del disyuntor de catalogo, que tambien avanza con cada espera del backoff."""
    reloj = Reloj()
    monkeypatch.setattr(resiliencia, "_disyuntores", {"catalogo": Disyuntor("catalogo", reloj=reloj)})
    dormir_de_verdad = asyncio.sleep

    async def dormir(segundos: float, *args, **kwargs) -> None:
        reloj.t += segundos
        await dormir_de_verdad(0)

    monkeypatch.setattr(asyncio, "sleep", dormir)
    return reloj


async def _hasta_que_abre(reloj: Reloj, metodo: str, *, colgado: bool) -> tuple[CatalogoQueFalla, int]:
    catalogo = CatalogoQueFalla(reloj, colgado=colgado)
    disyuntor = resiliencia._disyuntores["catalogo"]
    llamadas = 0
    # El mismo timeout que el pool de `api._arrancar`; `MockTransport` en vez de sockets.
    async with httpx.AsyncClient(transport=httpx.MockTransport(catalogo), timeout=ESPERA_SEGUNDOS) as http:
        cliente = ClienteCatalogo(base=BASE, cliente=http)
        while not disyuntor.abierto and llamadas < 20:
            llamadas += 1
            with pytest.raises(RemotoCaido):
                await LLAMADAS[metodo](cliente)
    assert disyuntor.abierto is True
    return catalogo, llamadas


def _anotar(record_property, catalogo: CatalogoQueFalla, llamadas: int, segundos: float) -> None:
    record_property("segundos_hasta_abrir", round(segundos, 3))
    record_property("tope_esc_r2_s", TOPE_ESC_R2)
    record_property("toques_al_destino", len(catalogo.fin_de_cada_toque))
    record_property("llamadas_del_pipeline", llamadas)
    record_property("timeout_por_peticion_s", catalogo.esperas[0] if catalogo.esperas else 0)


@pytest.mark.parametrize("metodo", ["lista", "emparejar"], ids=["get-lista", "post-emparejar"])
class TestElCircuitoDeCatalogoSeAbreATiempo:
    @pytest.mark.xfail(
        strict=True,
        reason="H-A-55: con el catalogo colgado, el disyuntor de inteligencia tarda 300,8 s (GET, "
        "timeout de 60 s por tres intentos) o 300,0 s (POST) en abrir, frente a los 30 s de ESC-R2",
    )
    async def test_con_el_catalogo_colgado_abre_en_treinta_segundos_o_menos(
        self, reloj, metodo, record_property
    ):
        catalogo, llamadas = await _hasta_que_abre(reloj, metodo, colgado=True)
        segundos = catalogo.fin_de_cada_toque[resiliencia._disyuntores["catalogo"].umbral - 1]

        _anotar(record_property, catalogo, llamadas, segundos)
        assert catalogo.esperas[0] == ESPERA_SEGUNDOS
        assert segundos <= TOPE_ESC_R2, f"el circuito se abrio a los {segundos:.1f} s"

    async def test_con_la_conexion_rechazada_abre_en_menos_de_un_segundo(
        self, reloj, metodo, record_property
    ):
        catalogo, llamadas = await _hasta_que_abre(reloj, metodo, colgado=False)
        segundos = catalogo.fin_de_cada_toque[resiliencia._disyuntores["catalogo"].umbral - 1]

        _anotar(record_property, catalogo, llamadas, segundos)
        assert len(catalogo.fin_de_cada_toque) == 5
        assert segundos < 1.0 <= TOPE_ESC_R2
