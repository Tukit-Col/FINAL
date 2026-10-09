"""NFR-MAN-01: lo que Operacion pide a otros servicios por HTTP y como degrada si no responden (`remoto.py`).

`ClienteIdentidad` (resolver un contacto a un `usuario_id` y al reves) y
`ClienteMetricas` (los agregados del snapshot diario) devuelven `None`/`[]` en
vez de lanzar cuando el destino esta caido: abrir una PQRS o repartir un aviso no
puede fallar porque otro servicio no conteste. Se prueba con destinos de mentira
(`httpx.MockTransport`, sin red): que ruta y cuerpo se piden, que valor vuelve en
el camino feliz y que todo fallo de transporte o de estado degrada en silencio.

Importa porque estas son las unicas dependencias sincronas de Operacion hacia
afuera: una que lance rompe el alta de la PQRS del acudiente, y una que no tenga
disyuntor (ADR 0020, `tukit_comun.resiliencia`) vuelve a golpear al destino
caido en cada llamada, esperando 30 s cada vez. Se caracteriza ese defecto y el
de una respuesta sin `usuario_id`, que se convierte en el texto "None".
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
import pytest_asyncio
from tukit_comun import resiliencia
from tukit_comun.resiliencia import UMBRAL_POR_OMISION, CircuitoAbierto
from tukit_operacion.remoto import (
    ESPERA_SEGUNDOS,
    ClienteIdentidad,
    ClienteMetricas,
    url_catalogo,
    url_identidad,
    url_inteligencia,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

USUARIO = "22222222-2222-5222-8222-222222222222"
CORREO = "acudiente.ficticio@example.test"
CELULAR = "3000000000"


class Destino:
    """El servicio de atras de mentira: anota cada peticion y responde lo que se le diga."""

    def __init__(self) -> None:
        self.peticiones: list[httpx.Request] = []
        self.responder: Callable[[httpx.Request], httpx.Response] = lambda peticion: httpx.Response(
            200, json={}
        )
        self.cliente: httpx.AsyncClient

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        return self.responder(peticion)


def _caido(peticion: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("conexion rechazada")


@pytest_asyncio.fixture
async def destino() -> Any:
    doble = Destino()
    async with httpx.AsyncClient(transport=httpx.MockTransport(doble)) as cliente:
        doble.cliente = cliente
        yield doble


@pytest.fixture(autouse=True)
def _entorno_y_disyuntores_limpios(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin URLs en el entorno (valen las de desarrollo) y sin disyuntores heredados de otra prueba."""
    for nombre in ("TUKIT_IDENTIDAD_URL", "TUKIT_CATALOGO_URL", "TUKIT_INTELIGENCIA_URL"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setattr(resiliencia, "_disyuntores", {})


class TestLasUrlsSalenDelEntorno:
    def test_sin_entorno_cada_servicio_usa_su_puerto_de_desarrollo(self):
        assert url_identidad() == "http://127.0.0.1:8011"
        assert url_catalogo() == "http://127.0.0.1:8012"
        assert url_inteligencia() == "http://127.0.0.1:8013"

    @pytest.mark.parametrize(
        ("variable", "funcion"),
        [
            ("TUKIT_IDENTIDAD_URL", url_identidad),
            ("TUKIT_CATALOGO_URL", url_catalogo),
            ("TUKIT_INTELIGENCIA_URL", url_inteligencia),
        ],
    )
    def test_la_url_del_entorno_gana_y_pierde_la_barra_final(self, monkeypatch, variable, funcion):
        monkeypatch.setenv(variable, "http://servicio.example.test:9000///")

        assert funcion() == "http://servicio.example.test:9000"


class TestClienteIdentidad:
    async def test_resolver_contacto_pide_el_alta_idempotente_y_devuelve_el_id(self, destino, monkeypatch):
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://identidad.example.test")
        destino.responder = lambda p: httpx.Response(201, json={"usuario_id": USUARIO, "creado": True})

        resultado = await ClienteIdentidad(cliente=destino.cliente).resolver_contacto(CORREO, CELULAR)

        (peticion,) = destino.peticiones
        assert resultado == USUARIO
        assert (peticion.method, str(peticion.url)) == ("POST", "http://identidad.example.test/v1/contactos")
        assert peticion.content == f'{{"correo":"{CORREO}","celular":"{CELULAR}"}}'.encode()

    async def test_sin_celular_viaja_null_y_no_se_inventa_uno(self, destino):
        destino.responder = lambda p: httpx.Response(201, json={"usuario_id": USUARIO})

        await ClienteIdentidad(cliente=destino.cliente).resolver_contacto(CORREO)

        assert destino.peticiones[0].content == f'{{"correo":"{CORREO}","celular":null}}'.encode()

    async def test_la_base_explicita_gana_sobre_el_entorno(self, destino, monkeypatch):
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://del-entorno.example.test")
        destino.responder = lambda p: httpx.Response(200, json={"usuario_id": USUARIO})

        await ClienteIdentidad(
            base="http://explicita.example.test", cliente=destino.cliente
        ).resolver_contacto(CORREO)

        assert destino.peticiones[0].url.host == "explicita.example.test"

    async def test_contacto_de_pide_el_id_y_devuelve_solo_correo_y_celular(self, destino):
        destino.responder = lambda p: httpx.Response(
            200, json={"usuario_id": USUARIO, "correo": CORREO, "celular": None, "otro": "ignorado"}
        )

        contacto = await ClienteIdentidad(cliente=destino.cliente).contacto_de(USUARIO)

        (peticion,) = destino.peticiones
        assert (peticion.method, peticion.url.path) == ("GET", f"/v1/contactos/{USUARIO}")
        assert contacto == {"correo": CORREO, "celular": None}

    async def test_contacto_de_con_campos_ausentes_los_devuelve_vacios(self, destino):
        destino.responder = lambda p: httpx.Response(200, json={})

        assert await ClienteIdentidad(cliente=destino.cliente).contacto_de(USUARIO) == {
            "correo": None,
            "celular": None,
        }

    @pytest.mark.parametrize(
        "fallo",
        [
            pytest.param(lambda p: httpx.Response(404, json={"error": "usuario_no_existe"}), id="404"),
            pytest.param(lambda p: httpx.Response(422, json={"error": "correo_invalido"}), id="422"),
            pytest.param(lambda p: httpx.Response(500), id="500"),
            pytest.param(lambda p: httpx.Response(503), id="503"),
            pytest.param(_caido, id="conexion-rechazada"),
            pytest.param(lambda p: (_ for _ in ()).throw(httpx.ReadTimeout("sin respuesta")), id="timeout"),
        ],
    )
    async def test_cualquier_fallo_degrada_a_none_en_las_dos_llamadas(self, destino, fallo):
        """Si Identidad no esta, el caso se abre sin titular y el aviso se reintenta:
        ni el alta ni el repartidor pueden reventar por esto."""
        destino.responder = fallo
        identidad = ClienteIdentidad(cliente=destino.cliente)

        assert await identidad.resolver_contacto(CORREO, CELULAR) is None
        assert await identidad.contacto_de(USUARIO) is None
        assert len(destino.peticiones) == 2  # se intento de verdad, no se saltaron las llamadas

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-25: resolver_contacto convierte un 2xx sin usuario_id en el texto 'None'",
    )
    async def test_una_respuesta_sin_usuario_id_no_se_vuelve_el_texto_none(self, destino):
        """La docstring promete el id "o `None` si Identidad no esta". Evidencia:
        remoto.py:63 hace `str(respuesta.json().get("usuario_id"))`, y `str(None)`
        es la cadena "None": el router (`abrir_caso`) la trata como un id valido
        (verdadera) y `uuid.UUID("None")` revienta, asi que la PQRS termina en 500
        en vez de abrirse sin titular."""
        destino.responder = lambda p: httpx.Response(200, json={"creado": False})

        resultado = await ClienteIdentidad(cliente=destino.cliente).resolver_contacto(CORREO, CELULAR)

        assert resultado in (None, "")


class TestClienteMetricas:
    async def test_cada_agregado_se_pide_a_su_servicio_y_ruta(self, destino, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://catalogo.example.test")
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://identidad.example.test")
        monkeypatch.setenv("TUKIT_INTELIGENCIA_URL", "http://inteligencia.example.test")
        destino.responder = lambda p: httpx.Response(
            200, json={"colegios": [{"colegio_id": "col-1"}], "conceptos": 3, "kits_armados": 2}
        )
        metricas = ClienteMetricas(cliente=destino.cliente)

        resumen = await metricas.resumen_catalogo()
        colegios = await metricas.colegios()
        por_colegio = await metricas.metricas_colegio("col-1")

        assert [(p.method, str(p.url)) for p in destino.peticiones] == [
            ("GET", "http://catalogo.example.test/v1/catalogo/resumen"),
            ("GET", "http://identidad.example.test/v1/colegios"),
            ("GET", "http://inteligencia.example.test/v1/metricas/colegios/col-1"),
        ]
        assert resumen == {"colegios": [{"colegio_id": "col-1"}], "conceptos": 3, "kits_armados": 2}
        assert colegios == [{"colegio_id": "col-1"}]
        assert por_colegio == resumen

    async def test_las_bases_explicitas_ganan_sobre_el_entorno(self, destino, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://del-entorno.example.test")
        metricas = ClienteMetricas(
            cliente=destino.cliente,
            base_catalogo="http://uno.example.test",
            base_identidad="http://dos.example.test",
            base_inteligencia="http://tres.example.test",
        )

        await metricas.resumen_catalogo()
        await metricas.colegios()
        await metricas.metricas_colegio("col-1")

        assert [p.url.host for p in destino.peticiones] == [
            "uno.example.test",
            "dos.example.test",
            "tres.example.test",
        ]

    async def test_sin_la_clave_colegios_la_lista_es_vacia(self, destino):
        destino.responder = lambda p: httpx.Response(200, json={})

        assert await ClienteMetricas(cliente=destino.cliente).colegios() == []

    async def test_cuando_el_servicio_cae_cada_llamada_degrada_a_su_valor_vacio(self, destino):
        """Un snapshot parcial es una respuesta valida: resumen `None`, colegios `[]`."""
        destino.responder = _caido
        metricas = ClienteMetricas(cliente=destino.cliente)

        assert await metricas.resumen_catalogo() is None
        assert await metricas.colegios() == []
        assert await metricas.metricas_colegio("col-1") is None
        assert len(destino.peticiones) == 3

    @pytest.mark.parametrize("estado", [404, 500, 503])
    async def test_un_estado_de_error_tambien_degrada(self, destino, estado):
        destino.responder = lambda p: httpx.Response(estado)
        metricas = ClienteMetricas(cliente=destino.cliente)

        assert await metricas.resumen_catalogo() is None
        assert await metricas.colegios() == []
        assert await metricas.metricas_colegio("col-1") is None


LlamadaCaida = Callable[[httpx.AsyncClient], Awaitable[Any]]

LLAMADAS: dict[str, LlamadaCaida] = {
    "identidad.resolver_contacto": lambda c: ClienteIdentidad(cliente=c).resolver_contacto(CORREO, CELULAR),
    "identidad.contacto_de": lambda c: ClienteIdentidad(cliente=c).contacto_de(USUARIO),
    "metricas.resumen_catalogo": lambda c: ClienteMetricas(cliente=c).resumen_catalogo(),
    "metricas.colegios": lambda c: ClienteMetricas(cliente=c).colegios(),
    "metricas.metricas_colegio": lambda c: ClienteMetricas(cliente=c).metricas_colegio("col-1"),
}


class TestElDisyuntor:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-26: remoto.py no usa disyuntor (ADR 0020): un destino caido se vuelve a "
            "golpear en cada llamada"
        ),
    )
    @pytest.mark.parametrize("llamada", LLAMADAS.values(), ids=LLAMADAS.keys())
    async def test_un_destino_caido_abre_el_circuito_y_la_siguiente_llamada_no_lo_toca(
        self, destino, llamada
    ):
        """Componente obligatorio de todo cliente remoto: tras `UMBRAL_POR_OMISION`
        fallos seguidos, la siguiente llamada falla rapido (`CircuitoAbierto`, o la
        degradacion vacia que ya promete el cliente) SIN llegar al destino. Evidencia:
        ningun metodo de remoto.py (56-65, 77-84, 105-134) importa
        `tukit_comun.resiliencia`, a diferencia de inteligencia/remoto.py:99 y
        comercio/remoto.py:66, que envuelven cada llamada en `disyuntor_de(...)`. Con un
        Identidad caido, cada PQRS espera ESPERA_SEGUNDOS (30 s) en vez de fallar rapido."""
        destino.responder = _caido
        assert ESPERA_SEGUNDOS == 30.0

        for _ in range(UMBRAL_POR_OMISION):
            await llamada(destino.cliente)
        tocadas = len(destino.peticiones)
        assert tocadas == UMBRAL_POR_OMISION  # hasta el umbral el destino SI se intenta

        with contextlib.suppress(CircuitoAbierto):
            await llamada(destino.cliente)

        assert len(destino.peticiones) == tocadas  # el circuito abierto no toca al destino
