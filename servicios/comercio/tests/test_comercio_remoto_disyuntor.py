"""NFR-MAN-01: el cliente remoto de Catalogo con su disyuntor (ADR 0020): destino caido, falla rapido.

`ClienteCatalogo.resolver` es la unica llamada de Comercio a otro servicio y va protegida: reintento
con backoff solo porque es un GET idempotente, y un disyuntor por destino. Lo que se defiende aqui es
la promesa de degradar sin tumbar: con Catalogo caido el circuito se abre y la llamada siguiente
falla en el acto con `CatalogoCaido` (causa `CircuitoAbierto`) SIN tocar al destino ni dormir; pasado
el TTL entra UNA prueba que cierra o reabre el circuito; y el checkout lo traduce a `503
catalogo_no_disponible` sin crear pedido ni reserva ni cobrar.

Sin red: el destino es un `httpx.MockTransport` que cuenta golpes. El reloj del disyuntor y el
`sleep` del backoff son inyectados (ninguna espera real), y el registro global de disyuntores se
reemplaza por uno vacio en cada prueba para no contaminar a las demas.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio import remoto
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, Pedido, ReservaInventario
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comercio.remoto import CatalogoCaido, ClienteCatalogo
from tukit_comun import resiliencia
from tukit_comun.bd import MotorServicio
from tukit_comun.http import fijar_correlacion, reset_correlacion
from tukit_comun.resiliencia import CircuitoAbierto, Disyuntor, disyuntor_de

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PRODUCTO = "11111111-1111-5111-8111-111111111111"
BASE = "http://catalogo.test"


class Destino:
    """Servidor falso de Catalogo: guarda cada peticion y responde segun el guion vigente."""

    def __init__(
        self,
        respuesta: httpx.Response | Exception,
        *,
        primeros: tuple[httpx.Response | Exception, ...] = (),
    ) -> None:
        self.respuesta = respuesta
        self.primeros = list(primeros)  # se consumen en orden antes de caer en `respuesta`
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        siguiente = self.primeros.pop(0) if self.primeros else self.respuesta
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    @property
    def golpes(self) -> int:
        return len(self.peticiones)


def _ok(precio: int | None = 4500) -> httpx.Response:
    return httpx.Response(200, json={"producto_canonico_id": PRODUCTO, "precio_desde": precio})


def _caido() -> Exception:
    return httpx.ConnectError("catalogo no responde")


class Reloj:
    """Reloj monotono controlado por la prueba."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture(autouse=True)
def registro_limpio(monkeypatch) -> None:
    """Un registro de disyuntores vacio por prueba: el global es de proceso y se compartiria."""
    monkeypatch.setattr(resiliencia, "_disyuntores", {})


@pytest.fixture(autouse=True)
def dormidos(monkeypatch) -> list[float]:
    """El backoff de tenacity duerme con `asyncio.sleep`: se registra y no se espera."""
    pausas: list[float] = []

    async def _no_dormir(segundos: float) -> None:
        pausas.append(segundos)

    monkeypatch.setattr(asyncio, "sleep", _no_dormir)
    return pausas


def _cliente(destino: Destino) -> ClienteCatalogo:
    http = httpx.AsyncClient(transport=httpx.MockTransport(destino))
    return ClienteCatalogo(base=BASE, cliente=http)


# --- lectura normal -----------------------------------------------------------------------------


async def test_resolver_devuelve_id_y_precio_pegandole_al_endpoint_interno():
    """Va a `/interno/resolver-sku/{sku}` (no a la superficie publica) y trae id canonico + precio."""
    destino = Destino(_ok(4500))
    catalogo = _cliente(destino)

    assert await catalogo.resolver("TK-C001-ECO") == (uuid.UUID(PRODUCTO), 4500)

    assert destino.golpes == 1
    assert str(destino.peticiones[0].url) == f"{BASE}/interno/resolver-sku/TK-C001-ECO"
    assert destino.peticiones[0].method == "GET"
    await catalogo.cliente.aclose()


async def test_resolver_sku_inexistente_es_none_y_no_se_reintenta():
    """404 es una respuesta, no un fallo: `None`, un solo golpe y el circuito sigue cerrado."""
    destino = Destino(httpx.Response(404))
    catalogo = _cliente(destino)

    assert await catalogo.resolver("NO-EXISTE") is None

    assert destino.golpes == 1
    assert disyuntor_de("catalogo").abierto is False
    await catalogo.cliente.aclose()


async def test_resolver_sin_precio_vigente_devuelve_el_id_con_precio_none():
    """`precio_desde: null` es el "sin precio vigente" del contrato: el id llega, el precio no."""
    catalogo = _cliente(Destino(_ok(None)))

    assert await catalogo.resolver("TK-SIN-PRECIO") == (uuid.UUID(PRODUCTO), None)
    await catalogo.cliente.aclose()


# --- reintento con backoff (solo GET idempotente) -----------------------------------------------


async def test_un_5xx_se_reintenta_tres_veces_con_backoff_exponencial_y_cae_en_catalogo_caido(dormidos):
    """3 intentos, esperas de 0.2 s y 0.4 s entre ellos, y al final `CatalogoCaido` (causa: el 5xx).

    Es lo que el checkout sabe manejar (503): nunca un traceback ni un cobro a ciegas."""
    destino = Destino(httpx.Response(503))
    catalogo = _cliente(destino)

    with pytest.raises(CatalogoCaido) as caida:
        await catalogo.resolver("TK-C001-ECO")

    assert destino.golpes == 3
    assert dormidos == [0.2, 0.4]
    assert isinstance(caida.value.__cause__, httpx.HTTPStatusError)
    await catalogo.cliente.aclose()


async def test_un_fallo_transitorio_se_recupera_en_el_reintento_sin_abrir_el_circuito(dormidos):
    """Falla el primer golpe y el segundo responde: la lectura sale bien tras UNA espera de 0.2 s y el
    contador de fallos se limpia con el exito (el circuito sigue cerrado)."""
    destino = Destino(_ok(7000), primeros=(_caido(),))
    catalogo = _cliente(destino)

    assert await catalogo.resolver("TK-C001-ECO") == (uuid.UUID(PRODUCTO), 7000)

    assert destino.golpes == 2
    assert dormidos == [0.2]
    assert disyuntor_de("catalogo").abierto is False
    await catalogo.cliente.aclose()


# --- el disyuntor: destino caido abre el circuito y la siguiente llamada falla rapido -----------


async def test_destino_caido_abre_el_circuito_y_la_siguiente_llamada_falla_rapido(dormidos):
    """Con Catalogo caido: 3 golpes en la primera lectura, 2 en la segunda (el quinto fallo abre el
    circuito y el tercer intento ya es rechazado), y desde ahi CERO golpes y CERO esperas."""
    destino = Destino(_caido())
    catalogo = _cliente(destino)

    with pytest.raises(CatalogoCaido):
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 3
    assert disyuntor_de("catalogo").abierto is False

    with pytest.raises(CatalogoCaido) as segunda:
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 5
    assert disyuntor_de("catalogo").abierto is True
    assert isinstance(segunda.value.__cause__, CircuitoAbierto)
    assert "circuito abierto" in str(segunda.value)

    golpes, pausas = destino.golpes, list(dormidos)
    with pytest.raises(CatalogoCaido) as rapida:
        await catalogo.resolver("OTRO-SKU")
    assert isinstance(rapida.value.__cause__, CircuitoAbierto)
    assert destino.golpes == golpes  # no toco al destino caido
    assert dormidos == pausas  # ni durmio reintentando contra un circuito abierto
    await catalogo.cliente.aclose()


async def test_el_circuito_de_catalogo_no_corta_a_los_demas_destinos():
    """Bulkhead: un destino caido no gasta los slots de otro. Identidad sigue cerrado y usable."""
    destino = Destino(_caido())
    catalogo = _cliente(destino)
    for _ in range(2):
        with pytest.raises(CatalogoCaido):
            await catalogo.resolver("TK-C001-ECO")
    assert disyuntor_de("catalogo").abierto is True

    assert disyuntor_de("identidad").abierto is False
    async with disyuntor_de("identidad"):
        pass  # no levanta CircuitoAbierto
    with pytest.raises(CircuitoAbierto):
        async with disyuntor_de("catalogo"):
            pytest.fail("el cuerpo no debe ejecutarse con el circuito abierto")
    await catalogo.cliente.aclose()


async def test_pasado_el_ttl_entra_una_prueba_y_si_responde_el_circuito_se_cierra(monkeypatch):
    """Medio-abierto: antes del TTL se rechaza sin golpear; al cumplirlo pasa UNA lectura, y si el
    destino ya se levanto el circuito se cierra y el trafico normal vuelve."""
    reloj = Reloj()
    monkeypatch.setitem(
        resiliencia._disyuntores, "catalogo", Disyuntor("catalogo", umbral=2, ttl=30.0, reloj=reloj)
    )
    destino = Destino(_caido())
    catalogo = _cliente(destino)

    with pytest.raises(CatalogoCaido):
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 2
    assert disyuntor_de("catalogo").abierto is True

    reloj.t = 29.9
    with pytest.raises(CatalogoCaido):
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 2  # aun dentro del TTL: rechazo sin golpear

    reloj.t = 30.0
    destino.respuesta = _ok(4500)
    assert await catalogo.resolver("TK-C001-ECO") == (uuid.UUID(PRODUCTO), 4500)
    assert destino.golpes == 3  # exactamente una prueba
    assert disyuntor_de("catalogo").abierto is False

    assert await catalogo.resolver("TK-C001-ECO") == (uuid.UUID(PRODUCTO), 4500)
    assert destino.golpes == 4
    await catalogo.cliente.aclose()


async def test_si_la_prueba_del_medio_abierto_falla_el_circuito_se_reabre_y_reinicia_el_ttl(monkeypatch):
    """La prueba falla: UN solo golpe, el circuito vuelve a abrirse con el reloj reiniciado, y hay que
    esperar otro TTL completo antes de la siguiente prueba."""
    reloj = Reloj()
    monkeypatch.setitem(
        resiliencia._disyuntores, "catalogo", Disyuntor("catalogo", umbral=2, ttl=30.0, reloj=reloj)
    )
    destino = Destino(_caido())
    catalogo = _cliente(destino)
    with pytest.raises(CatalogoCaido):
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 2

    reloj.t = 30.0
    with pytest.raises(CatalogoCaido) as prueba:
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 3  # una prueba, no tres reintentos
    assert isinstance(prueba.value.__cause__, CircuitoAbierto)
    assert disyuntor_de("catalogo").abierto is True

    reloj.t = 59.9  # 29.9 s despues de la reapertura: sigue cerrado el paso
    with pytest.raises(CatalogoCaido):
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 3

    reloj.t = 60.0  # otro TTL completo: entra la siguiente prueba
    with pytest.raises(CatalogoCaido):
        await catalogo.resolver("TK-C001-ECO")
    assert destino.golpes == 4
    await catalogo.cliente.aclose()


# --- el checkout ante Catalogo caido ------------------------------------------------------------


@pytest_asyncio.fixture
async def checkout() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio, PasarelaFalsa]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    app.state.motor = motor
    app.state.pasarela = PasarelaFalsa()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor, app.state.pasarela
    await engine.dispose()


def _orden() -> dict:
    return {
        "usuario_id": "22222222-2222-5222-8222-222222222222",
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 2, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }


async def _contar(motor: MotorServicio, modelo: type) -> int:
    async with motor.sesion() as db:
        return int(await db.scalar(select(func.count()).select_from(modelo)))


async def test_checkout_con_catalogo_caido_da_503_y_con_el_circuito_abierto_sigue_dando_503_sin_golpear(
    checkout,
):
    """El 503 `catalogo_no_disponible` no cambia al abrirse el circuito; lo que cambia es que ya no se
    golpea al destino. En ningun caso hay pedido, reserva ni intento de cobro."""
    http, motor, pasarela = checkout
    destino = Destino(_caido())
    app.state.catalogo = _cliente(destino)
    try:
        primera = await http.post("/v1/ordenes", json=_orden())
        assert primera.status_code == 503
        assert primera.json()["error"] == "catalogo_no_disponible"
        assert destino.golpes == 3

        segunda = await http.post("/v1/ordenes", json=_orden())
        assert segunda.status_code == 503
        assert destino.golpes == 5
        assert disyuntor_de("catalogo").abierto is True

        tercera = await http.post("/v1/ordenes", json=_orden())
        assert tercera.status_code == 503
        assert tercera.json()["error"] == "catalogo_no_disponible"
        assert destino.golpes == 5  # circuito abierto: no se toco al destino
    finally:
        await app.state.catalogo.cliente.aclose()

    assert await _contar(motor, Pedido) == 0
    assert await _contar(motor, ReservaInventario) == 0
    assert pasarela.creadas == []


# --- configuracion y cliente efimero ------------------------------------------------------------


def test_url_catalogo_sale_del_entorno_sin_barra_final_y_tiene_valor_por_omision(monkeypatch):
    monkeypatch.delenv("TUKIT_CATALOGO_URL", raising=False)
    assert remoto.url_catalogo() == "http://127.0.0.1:8012"
    assert ClienteCatalogo()._base() == "http://127.0.0.1:8012"

    monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://catalogo.interno:9000/")
    assert remoto.url_catalogo() == "http://catalogo.interno:9000"
    assert ClienteCatalogo()._base() == "http://catalogo.interno:9000"
    # Una base explicita en el cliente gana sobre el entorno.
    assert ClienteCatalogo(base="http://otro.test")._base() == "http://otro.test"


async def test_sin_cliente_inyectado_abre_uno_efimero_con_la_correlacion_y_lo_cierra(monkeypatch):
    """Produccion: no hay pool inyectado y la lectura abre un cliente propio que viaja con el id de
    correlacion de la peticion en curso y se cierra al terminar (no se filtran conexiones)."""
    vistas: list[str | None] = []

    def _destino(peticion: httpx.Request) -> httpx.Response:
        vistas.append(peticion.headers.get("x-correlation-id"))
        return _ok(4500)

    original = httpx.AsyncClient
    abiertos: list[httpx.AsyncClient] = []

    def _fabrica(*args, **kwargs) -> httpx.AsyncClient:
        cliente = original(*args, transport=httpx.MockTransport(_destino), **kwargs)
        abiertos.append(cliente)
        return cliente

    monkeypatch.setattr(httpx, "AsyncClient", _fabrica)
    monkeypatch.setenv("TUKIT_CATALOGO_URL", BASE)
    ficha = fijar_correlacion("cid-ficticio-0001")
    try:
        assert await ClienteCatalogo().resolver("TK-C001-ECO") == (uuid.UUID(PRODUCTO), 4500)
    finally:
        reset_correlacion(ficha)

    assert vistas == ["cid-ficticio-0001"]
    assert len(abiertos) == 1
    assert abiertos[0].is_closed is True


def test_la_espera_por_omision_hacia_catalogo_es_de_30_segundos():
    """El timeout acotado es parte del bulkhead: sin el, un Catalogo lento retiene el checkout."""
    assert remoto.ESPERA_SEGUNDOS == 30.0
