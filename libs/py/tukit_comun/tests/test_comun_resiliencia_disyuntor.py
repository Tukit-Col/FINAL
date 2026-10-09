"""NFR-MAN-01: conducta del disyuntor y de la politica de reintento (ADR 0020).

Caracteriza lo que las pruebas basicas de `test_resiliencia.py` no fijan: que un
circuito abierto NO toca al destino (se cuentan las llamadas que llegan), que el
TTL se mide con el reloj inyectado y no con el de pared, que un exito intermedio
reinicia la cuenta de fallos, que cada destino tiene su propio disyuntor (la
frontera del bulkhead) y que el reintento de transporte solo existe para GET.

Importa porque el disyuntor es lo unico que evita que un destino caido consuma a
todos sus llamadores en una tormenta de timeouts, y el reintento ciego de una
escritura es el doble cobro, el modo de falla mas caro. Ningun sleep real: los
relojes y las esperas del reintento se inyectan.
"""

from __future__ import annotations

import pytest
from tukit_comun import resiliencia
from tukit_comun.resiliencia import (
    TTL_POR_OMISION,
    UMBRAL_POR_OMISION,
    CircuitoAbierto,
    Disyuntor,
    disyuntor_de,
    llamada_protegida,
    reintentar_get,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class Reloj:
    """Reloj falso: el tiempo solo avanza cuando la prueba lo dice."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class Destino:
    """Un destino remoto de mentira que cuenta cuantas veces lo tocaron."""

    def __init__(self, *, caido: bool = True) -> None:
        self.caido = caido
        self.toques = 0

    async def llamar(self, disyuntor: Disyuntor) -> str:
        async with disyuntor:
            self.toques += 1
            if self.caido:
                raise ConnectionError("destino caido")
            return "ok"


@pytest.fixture(autouse=True)
def _registro_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """El registro de disyuntores es global al proceso: cada prueba parte de cero
    para no heredar un circuito abierto de otra."""
    monkeypatch.setattr(resiliencia, "_disyuntores", {})


def _sin_espera(funcion) -> list[float]:
    """Sustituye la espera real del reintento por una que solo anota el valor."""
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)

    funcion.retry.sleep = dormir
    return esperas


class TestElCircuitoAbiertoNoTocaAlDestino:
    async def test_tras_el_umbral_las_llamadas_se_rechazan_sin_llegar_al_destino(self):
        destino = Destino()
        d = Disyuntor("catalogo", umbral=3, ttl=30.0, reloj=Reloj())

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await destino.llamar(d)
        assert destino.toques == 3
        assert d.abierto is True

        for _ in range(10):
            with pytest.raises(CircuitoAbierto):
                await destino.llamar(d)

        # Falla rapido: ninguna de las diez rechazadas llego al destino.
        assert destino.toques == 3

    async def test_antes_del_umbral_el_circuito_sigue_cerrado_y_el_destino_se_toca(self):
        destino = Destino()
        d = Disyuntor("catalogo", umbral=3, ttl=30.0, reloj=Reloj())

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await destino.llamar(d)

        assert d.abierto is False
        with pytest.raises(ConnectionError):  # no CircuitoAbierto: la 3a si llega al destino
            await destino.llamar(d)
        assert destino.toques == 3

    async def test_el_rechazo_nombra_el_destino_y_es_un_runtime_error(self):
        d = Disyuntor("identidad", umbral=1, reloj=Reloj())
        with pytest.raises(ConnectionError):
            await Destino().llamar(d)

        with pytest.raises(CircuitoAbierto) as info:
            await Destino().llamar(d)

        assert isinstance(info.value, RuntimeError)
        assert "identidad" in str(info.value)

    async def test_nunca_traga_la_excepcion_del_destino(self):
        """El llamador decide como degradar: el disyuntor solo cuenta."""
        d = Disyuntor("catalogo", umbral=5, reloj=Reloj())
        error = TimeoutError("lento")

        with pytest.raises(TimeoutError) as info:
            async with d:
                raise error

        assert info.value is error


class TestElTiempoSeMideConElRelojInyectado:
    async def test_justo_antes_del_ttl_sigue_rechazando_y_en_el_ttl_deja_pasar_una_prueba(self):
        reloj = Reloj()
        destino = Destino()
        d = Disyuntor("catalogo", umbral=1, ttl=30.0, reloj=reloj)
        with pytest.raises(ConnectionError):
            await destino.llamar(d)

        reloj.t = 29.999
        with pytest.raises(CircuitoAbierto):
            await destino.llamar(d)
        assert destino.toques == 1

        reloj.t = 30.0  # `>=`: el TTL cumplido basta
        with pytest.raises(ConnectionError):
            await destino.llamar(d)
        assert destino.toques == 2  # la prueba SI llego al destino

    async def test_el_exito_de_la_prueba_cierra_y_reinicia_la_cuenta_de_fallos(self):
        reloj = Reloj()
        destino = Destino()
        d = Disyuntor("catalogo", umbral=2, ttl=10.0, reloj=reloj)
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await destino.llamar(d)
        assert d.abierto is True

        reloj.t = 11.0
        destino.caido = False
        assert await destino.llamar(d) == "ok"
        assert d.abierto is False

        # La cuenta volvio a cero: un solo fallo no reabre (umbral 2).
        destino.caido = True
        with pytest.raises(ConnectionError):
            await destino.llamar(d)
        assert d.abierto is False
        with pytest.raises(ConnectionError):
            await destino.llamar(d)
        assert d.abierto is True

    async def test_la_prueba_fallida_reinicia_el_reloj_del_ttl(self):
        reloj = Reloj()
        destino = Destino()
        d = Disyuntor("catalogo", umbral=1, ttl=30.0, reloj=reloj)
        with pytest.raises(ConnectionError):
            await destino.llamar(d)

        reloj.t = 31.0  # medio-abierto: la prueba falla y reabre DESDE AHORA
        with pytest.raises(ConnectionError):
            await destino.llamar(d)
        assert d.abierto is True

        reloj.t = 60.0  # 29 s despues de la reapertura: aun dentro del nuevo TTL
        with pytest.raises(CircuitoAbierto):
            await destino.llamar(d)

        reloj.t = 61.0  # 30 s despues: otra prueba
        with pytest.raises(ConnectionError):
            await destino.llamar(d)
        assert destino.toques == 3


class TestSoloLosFallosConsecutivosAbren:
    async def test_un_exito_intermedio_reinicia_la_cuenta(self):
        destino = Destino()
        d = Disyuntor("catalogo", umbral=3, reloj=Reloj())

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await destino.llamar(d)
        destino.caido = False
        await destino.llamar(d)  # exito: la cuenta vuelve a cero

        destino.caido = True
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await destino.llamar(d)
        assert d.abierto is False  # 2 + 2 no suman 4: no son consecutivos

        with pytest.raises(ConnectionError):
            await destino.llamar(d)  # el tercero consecutivo
        assert d.abierto is True

    def test_los_valores_por_omision_son_los_generosos_del_adr(self):
        d = Disyuntor("catalogo")
        assert (d.umbral, d.ttl) == (UMBRAL_POR_OMISION, TTL_POR_OMISION) == (5, 30.0)
        assert d.abierto is False


class TestUnDisyuntorPorDestino:
    async def test_el_registro_devuelve_el_mismo_disyuntor_para_el_mismo_destino(self):
        assert disyuntor_de("catalogo") is disyuntor_de("catalogo")
        assert disyuntor_de("catalogo").destino == "catalogo"

    async def test_un_catalogo_caido_no_abre_el_circuito_de_identidad(self):
        """La frontera del bulkhead: cada destino cae solo."""
        catalogo = disyuntor_de("catalogo")
        for _ in range(UMBRAL_POR_OMISION):
            with pytest.raises(ConnectionError):
                await Destino().llamar(catalogo)

        assert catalogo.abierto is True
        assert disyuntor_de("identidad") is not catalogo
        assert disyuntor_de("identidad").abierto is False
        assert await Destino(caido=False).llamar(disyuntor_de("identidad")) == "ok"


class TestLlamadaProtegidaGuardaLaPoliticaDeReintento:
    def test_devuelve_el_disyuntor_compartido_del_destino(self):
        assert llamada_protegida("catalogo", metodo="GET", reintentable=True) is disyuntor_de("catalogo")
        assert llamada_protegida("catalogo", metodo="POST") is disyuntor_de("catalogo")

    @pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE", "post"])
    def test_ninguna_escritura_puede_ser_reintentable(self, metodo):
        with pytest.raises(ValueError, match="solo se permite en GET"):
            llamada_protegida("comercio", metodo=metodo, reintentable=True)
        # Y el rechazo es al construir: no deja un disyuntor a medio registrar.
        assert "comercio" not in resiliencia._disyuntores

    @pytest.mark.parametrize("metodo", ["GET", "get", "Get"])
    def test_get_reintentable_se_acepta_sin_importar_la_capitalizacion(self, metodo):
        assert llamada_protegida("catalogo", metodo=metodo, reintentable=True).destino == "catalogo"

    def test_una_escritura_no_reintentable_pasa_por_el_disyuntor(self):
        assert llamada_protegida("wompi", metodo="POST", reintentable=False).destino == "wompi"


class TestReintentarGet:
    async def test_se_recupera_de_un_fallo_transitorio_con_backoff_exponencial(self):
        intentos = {"n": 0}

        @reintentar_get
        async def lectura() -> str:
            intentos["n"] += 1
            if intentos["n"] < 3:
                raise TimeoutError("red lenta")
            return "datos"

        esperas = _sin_espera(lectura)

        assert await lectura() == "datos"
        assert intentos["n"] == 3
        assert esperas == [0.2, 0.4]  # exponencial, sin dormir de verdad

    async def test_no_insiste_con_el_circuito_abierto(self):
        d = Disyuntor("catalogo", umbral=1, reloj=Reloj())
        destino = Destino()
        with pytest.raises(ConnectionError):
            await destino.llamar(d)

        @reintentar_get
        async def lectura() -> str:
            return await destino.llamar(d)

        esperas = _sin_espera(lectura)
        with pytest.raises(CircuitoAbierto):
            await lectura()

        assert esperas == []  # ni un reintento: insistir con el circuito abierto no sirve
        assert destino.toques == 1

    async def test_con_el_disyuntor_compartido_el_reintento_se_corta_cuando_el_circuito_abre(self):
        """Composicion real (`llamada_protegida` + `reintentar_get`): cada intento
        cuenta como un fallo; al llegar al umbral el siguiente intento recibe
        `CircuitoAbierto` y el reintento se detiene sin tocar al destino."""
        destino = Destino()

        @reintentar_get
        async def lectura() -> str:
            return await destino.llamar(llamada_protegida("catalogo", metodo="GET", reintentable=True))

        _sin_espera(lectura)

        with pytest.raises(ConnectionError):  # llamada 1: 3 intentos, 3 fallos
            await lectura()
        assert destino.toques == 3

        with pytest.raises(CircuitoAbierto):  # llamada 2: 2 intentos mas abren; el 3o se rechaza
            await lectura()
        assert destino.toques == UMBRAL_POR_OMISION
        assert disyuntor_de("catalogo").abierto is True

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-02: reintentar_get reintenta ValueError (3 intentos) aunque su contrato "
            "dice que no reintenta errores de argumento"
        ),
    )
    async def test_no_reintenta_los_errores_de_argumento(self):
        """El comentario de `reintentar_get` promete no reintentar `ValueError` de
        argumentos: un argumento invalido no se arregla insistiendo, solo
        multiplica la carga sobre el destino. Evidencia: resiliencia.py:119-120
        lo promete y resiliencia.py:126 solo excluye `CircuitoAbierto`."""
        intentos = {"n": 0}

        @reintentar_get
        async def lectura() -> str:
            intentos["n"] += 1
            raise ValueError("argumento invalido")

        _sin_espera(lectura)
        with pytest.raises(ValueError):
            await lectura()

        assert intentos["n"] == 1
