"""Fase 6 de QA, NFR-DIS-05: los patrones de resiliencia de Comercio (ADR 0020).

`test_checkout.py` fija el camino feliz del cobro y que el mismo webhook dos
veces seguidas mueve el pedido una vez. Aqui se prueba lo que ese camino no
cubre:

- **Disyuntor a tiempo (ESC-R2).** Con Catalogo colgado, cuanto tarda en abrirse
  el circuito de `resolver`: 30 s de timeout por tres intentos (H-A-55). El
  control, con la conexion rechazada, abre en menos de un segundo.
- **Idempotencia de la orden.** `REVISION_ARQUITECTURA.md` (ADR 0020) dice que
  las escrituras «se protegen con idempotencia de aplicacion» y nombra la
  cabecera `Idempotency-Key`. Un `POST /v1/ordenes` reenviado con la misma
  clave no deberia crear un segundo pedido (H-A-56).
- **Idempotencia del webhook.** El candado es solo el `evento_id` (desde
  7c2ae19, `transaccion:ESTADO` y no el id del sobre). Dos casos: la pasarela
  falsa (la de omision) reinicia su contador con el proceso y repite ids de
  transaccion; y dos entregas simultaneas del mismo evento, donde el indice unico salva
  el efecto pero la que pierde responde 500 (H-A-57). La carrera se simula
  haciendo que el SELECT del candado no vea la primera entrega, que es lo que
  pasa cuando las dos transacciones se cruzan.
- **Degradacion honesta.** Sin `WOMPI_MODO` el servicio cobra con la pasarela
  falsa y no lo dice (H-A-58).

SQLite en memoria, `ASGITransport` y dobles de Catalogo: ni red ni procesos.
El `asyncio.sleep` del backoff adelanta un reloj falso y no duerme. Los datos
de las ordenes son ficticios.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from _ayudas_comercio import PRODUCTO, CatalogoFalso
from tukit_comercio import api
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPago, EstadoPedido
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comercio.remoto import ESPERA_SEGUNDOS, CatalogoCaido, ClienteCatalogo
from tukit_comercio.repositorios import RepoPedidos
from tukit_comercio.routers import comercio as rutas
from tukit_comun import resiliencia
from tukit_comun.bd import MotorServicio
from tukit_comun.resiliencia import Disyuntor

pytestmark = pytest.mark.nfr("NFR-DIS-05")

TOPE_ESC_R2 = 30.0  # segundos, ATAM v2.0, ESC-R2
USUARIO = "33333333-3333-5333-8333-333333333333"
PEDIDO = Base.metadata.tables["pedido"]
EVENTO_PROCESADO = Base.metadata.tables["evento_pasarela_procesado"]
BANDEJA = Base.metadata.tables["bandeja_salida"]


def _orden_ficticia() -> dict:
    return {
        "usuario_id": USUARIO,
        "hijos": 1,
        "colegios": ["Colegio Ficticio QA"],
        "lineas": [
            {
                "producto_canonico_id": PRODUCTO,
                "sku": "TK-C001-ECO",
                "nombre": "Cuaderno cuadriculado",
                "cantidad": 1,
                "precio_unitario": 4500,
            }
        ],
        "entrega": {
            "destinatario": "Acudiente Ficticio QA",
            "direccion": "Calle Ficticia 1 # 2-3",
            "ciudad": "Bogota",
        },
    }


# --- ESC-R2: el disyuntor de Catalogo en `resolver` --------------------------


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class CatalogoQueFalla:
    """Catalogo que falla cada peticion: colgado (gasta el timeout) o rechazando la conexion."""

    def __init__(self, reloj: Reloj, *, colgado: bool) -> None:
        self.reloj = reloj
        self.colgado = colgado
        self.fin_de_cada_toque: list[float] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        if self.colgado:
            self.reloj.t += peticion.extensions["timeout"]["read"]
            self.fin_de_cada_toque.append(self.reloj.t)
            raise httpx.ReadTimeout("catalogo no contesto", request=peticion)
        self.fin_de_cada_toque.append(self.reloj.t)
        raise httpx.ConnectError("conexion rechazada", request=peticion)


@pytest.fixture
def reloj(monkeypatch: pytest.MonkeyPatch) -> Reloj:
    reloj = Reloj()
    monkeypatch.setattr(resiliencia, "_disyuntores", {"catalogo": Disyuntor("catalogo", reloj=reloj)})
    dormir_de_verdad = asyncio.sleep

    async def dormir(segundos: float, *args, **kwargs) -> None:
        reloj.t += segundos
        await dormir_de_verdad(0)

    monkeypatch.setattr(asyncio, "sleep", dormir)
    return reloj


async def _segundos_hasta_abrir(reloj: Reloj, record_property, *, colgado: bool) -> float:
    catalogo = CatalogoQueFalla(reloj, colgado=colgado)
    disyuntor = resiliencia._disyuntores["catalogo"]
    llamadas = 0
    # El mismo timeout que el pool de `api._arrancar`; `MockTransport` en vez de sockets.
    async with httpx.AsyncClient(transport=httpx.MockTransport(catalogo), timeout=ESPERA_SEGUNDOS) as http:
        cliente = ClienteCatalogo(base="http://catalogo.prueba", cliente=http)
        while not disyuntor.abierto and llamadas < 20:
            llamadas += 1
            with pytest.raises(CatalogoCaido):
                await cliente.resolver("TK-C001-ECO")
    assert disyuntor.abierto is True
    segundos = catalogo.fin_de_cada_toque[disyuntor.umbral - 1]
    record_property("segundos_hasta_abrir", round(segundos, 3))
    record_property("tope_esc_r2_s", TOPE_ESC_R2)
    record_property("toques_al_destino", len(catalogo.fin_de_cada_toque))
    record_property("llamadas_del_checkout", llamadas)
    return segundos


class TestElCircuitoDeCatalogoSeAbreATiempo:
    # H-A-55 (comercio): corregido en fix/hallazgos-qa, sale XPASS(strict) y se quita el xfail.
    async def test_con_catalogo_colgado_abre_en_treinta_segundos_o_menos(self, reloj, record_property):
        segundos = await _segundos_hasta_abrir(reloj, record_property, colgado=True)
        assert segundos <= TOPE_ESC_R2, f"el circuito se abrio a los {segundos:.1f} s"

    async def test_con_la_conexion_rechazada_abre_en_menos_de_un_segundo(self, reloj, record_property):
        segundos = await _segundos_hasta_abrir(reloj, record_property, colgado=False)
        assert segundos < 1.0 <= TOPE_ESC_R2


# --- Idempotencia de la orden y del webhook ----------------------------------


class Comercio:
    """La app de Comercio sobre SQLite en memoria, con lo que hace falta para contar efectos."""

    def __init__(self, http: httpx.AsyncClient, motor: MotorServicio) -> None:
        self.http = http
        self.motor = motor
        self.pagos_contados = 0

    async def contar(self, tabla, *condiciones) -> int:
        async with self.motor.sesion() as db:
            conexion = await db.connection()
            return await conexion.scalar(select(func.count()).select_from(tabla).where(*condiciones))

    async def pedido_con_pago(self) -> tuple[str, dict]:
        pedido_id = (await self.http.post("/v1/ordenes", json=_orden_ficticia())).json()["pedido_id"]
        pago = await self.http.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={"correo_cliente": "acudiente@example.test", "metodo": "pse"},
        )
        assert pago.status_code == 201
        return pedido_id, pago.json()

    async def estado(self, pedido_id: str) -> tuple[str, str]:
        pedido = (await self.http.get(f"/v1/ordenes/{pedido_id}")).json()
        return pedido["estado"], pedido["pago"]["estado"]


@pytest_asyncio.fixture
async def comercio(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Comercio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    monkeypatch.setattr(app.state, "motor", motor, raising=False)
    monkeypatch.setattr(app.state, "pasarela", PasarelaFalsa(), raising=False)
    monkeypatch.setattr(app.state, "catalogo", CatalogoFalso({"TK-C001-ECO": 4500}), raising=False)
    # Un 500 se ve como respuesta, igual que lo veria la pasarela, en vez de subir a la prueba.
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        servicio = Comercio(http, motor)

        def contar_pago() -> None:
            servicio.pagos_contados += 1

        monkeypatch.setattr(rutas, "contar_pago_aprobado", contar_pago)
        yield servicio
    await engine.dispose()


class TestUnaOrdenReenviadaNoSeDuplica:
    @pytest.mark.xfail(
        strict=True,
        reason="H-A-56: POST /v1/ordenes no tiene idempotencia de aplicacion; el reenvio con la misma "
        "Idempotency-Key crea un segundo pedido",
    )
    async def test_la_misma_idempotency_key_dos_veces_crea_un_solo_pedido(self, comercio, record_property):
        clave = {"Idempotency-Key": uuid.uuid4().hex}
        primera = await comercio.http.post("/v1/ordenes", json=_orden_ficticia(), headers=clave)
        segunda = await comercio.http.post("/v1/ordenes", json=_orden_ficticia(), headers=clave)
        pedidos = await comercio.contar(PEDIDO, PEDIDO.c.usuario_id == uuid.UUID(USUARIO))

        record_property("estados_http", f"{primera.status_code} {segunda.status_code}")
        record_property("pedidos_creados", pedidos)
        assert primera.status_code == 201
        assert pedidos == 1, f"la misma Idempotency-Key creo {pedidos} pedidos"


class TestElWebhookAplicaUnaSolaVez:
    @pytest.mark.xfail(
        strict=True,
        reason="H-A-57: el candado del webhook es solo el evento_id (`transaccion:ESTADO`, "
        "pasarela.py:142); tras reiniciar Comercio la pasarela falsa repite `falsa-1` y el pago del "
        "pedido nuevo se responde `repetido` y se pierde",
    )
    async def test_tras_reiniciar_la_pasarela_falsa_el_pago_nuevo_no_se_toma_por_repetido(
        self, comercio, record_property
    ):
        antes, pago_antes = await comercio.pedido_con_pago()
        evento_antes = app.state.pasarela.emitir_evento(
            referencia=pago_antes["referencia_wompi"],
            transaccion_id=pago_antes["transaccion_wompi"],
            estado_wompi="APPROVED",
            monto_centavos=app.state.pasarela.montos[pago_antes["referencia_wompi"]],
        )
        assert (await comercio.http.post("/v1/webhooks/wompi", json=evento_antes)).json()[
            "estado"
        ] == "aplicado"

        app.state.pasarela = PasarelaFalsa()  # Comercio se reinicia: la base sigue, el contador no
        despues, pago_despues = await comercio.pedido_con_pago()
        evento = app.state.pasarela.emitir_evento(
            referencia=pago_despues["referencia_wompi"],
            transaccion_id=pago_despues["transaccion_wompi"],
            estado_wompi="APPROVED",
            monto_centavos=app.state.pasarela.montos[pago_despues["referencia_wompi"]],
        )
        respuesta = await comercio.http.post("/v1/webhooks/wompi", json=evento)
        estado_pedido, estado_pago = await comercio.estado(despues)

        record_property("transaccion_antes", pago_antes["transaccion_wompi"])
        record_property("transaccion_despues", pago_despues["transaccion_wompi"])
        record_property("respuesta_webhook", respuesta.json().get("estado"))
        record_property("estado_pedido_nuevo", estado_pedido)
        record_property("estado_pago_nuevo", estado_pago)
        assert respuesta.json()["estado"] != "repetido", (
            f"el evento {evento['id']} de la referencia {pago_despues['referencia_wompi']} se tomo por el "
            f"de {pago_antes['referencia_wompi']}"
        )
        assert estado_pedido == EstadoPedido.PAGADO.value

    async def _carrera(
        self, comercio: Comercio, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[str, dict, httpx.Response]:
        """Dos entregas del mismo evento cruzadas: la segunda no ve la primera en el SELECT del candado."""
        pedido_id, pago = await comercio.pedido_con_pago()
        evento = app.state.pasarela.emitir_evento(
            referencia=pago["referencia_wompi"],
            transaccion_id=f"qa-{uuid.uuid4().hex}",
            estado_wompi="APPROVED",
            monto_centavos=app.state.pasarela.montos[pago["referencia_wompi"]],
        )
        primera = await comercio.http.post("/v1/webhooks/wompi", json=evento)
        assert primera.json()["estado"] == "aplicado"

        async def no_lo_ve(self, evento_id: str) -> bool:
            return False

        monkeypatch.setattr(RepoPedidos, "evento_ya_procesado", no_lo_ve)
        segunda = await comercio.http.post("/v1/webhooks/wompi", json=evento)
        return pedido_id, evento, segunda

    async def test_dos_entregas_cruzadas_del_mismo_evento_tienen_un_solo_efecto(
        self, comercio, monkeypatch, record_property
    ):
        pedido_id, evento, segunda = await self._carrera(comercio, monkeypatch)
        # La clave de idempotencia es `transaccion:ESTADO` desde 7c2ae19, no el id del sobre.
        clave = f"{evento['data']['transaction']['id']}:APPROVED"
        eventos = await comercio.contar(EVENTO_PROCESADO, EVENTO_PROCESADO.c.evento_id == clave)
        avisos = await comercio.contar(
            BANDEJA, BANDEJA.c.tipo == "pedido_pagado", BANDEJA.c.agregado_id == uuid.UUID(pedido_id)
        )

        record_property("estado_http_segunda_entrega", segunda.status_code)
        record_property("eventos_registrados", eventos)
        record_property("avisos_pedido_pagado", avisos)
        record_property("pagos_contados", comercio.pagos_contados)
        assert (eventos, avisos, comercio.pagos_contados) == (1, 1, 1)
        assert await comercio.estado(pedido_id) == (EstadoPedido.PAGADO.value, EstadoPago.APROBADO.value)

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-57: la entrega que pierde la carrera choca con el indice unico y responde 500, "
        "no 200 `repetido`",
    )
    async def test_la_entrega_que_pierde_la_carrera_responde_repetido(
        self, comercio, monkeypatch, record_property
    ):
        _, _, segunda = await self._carrera(comercio, monkeypatch)

        record_property("estado_http_segunda_entrega", segunda.status_code)
        assert segunda.status_code == 200, f"la segunda entrega respondio {segunda.status_code}"
        assert segunda.json()["estado"] == "repetido"


# --- Degradacion honesta -----------------------------------------------------


@pytest.fixture
def estado_de_la_app_restaurado(monkeypatch: pytest.MonkeyPatch) -> None:
    for nombre in ("motor", "pasarela", "catalogo", "pool_catalogo"):
        monkeypatch.setattr(app.state, nombre, getattr(app.state, nombre, None), raising=False)


@pytest.mark.usefixtures("estado_de_la_app_restaurado")
class TestLaPasarelaFalsaSeAnuncia:
    @pytest.mark.xfail(
        strict=True,
        reason="H-A-58: sin WOMPI_MODO Comercio arranca con la pasarela falsa (nunca cobra) y no lo "
        "dice en el registro ni en la consola",
    )
    async def test_sin_wompi_modo_el_arranque_dice_que_la_pasarela_es_falsa(
        self, monkeypatch, caplog, capsys, record_property
    ):
        monkeypatch.setenv("TUKIT_COMERCIO_DB_URL", "sqlite+aiosqlite:///:memory:")
        monkeypatch.delenv("WOMPI_MODO", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.setattr(api, "instrumentar_motor", lambda _engine: None)

        with caplog.at_level(logging.DEBUG):
            async with app.router.lifespan_context(app):
                pasarela = app.state.pasarela
        salida = capsys.readouterr()
        lineas = [r.getMessage() for r in caplog.records] + (salida.out + salida.err).splitlines()
        dicho = [linea for linea in lineas if any(p in linea.lower() for p in ("wompi", "pasarela", "falsa"))]

        record_property("pasarela", type(pasarela).__name__)
        record_property("lineas_sobre_la_pasarela", len(dicho))
        assert isinstance(pasarela, PasarelaFalsa)
        assert dicho, "el arranque no dice que los pagos van a la pasarela falsa"
