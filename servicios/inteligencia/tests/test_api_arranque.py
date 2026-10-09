"""NFR-MAN-01: El ensamblado de la API de Inteligencia: clientes por omision, arranque, apagado y puerto.

`api.py` no tiene rutas (viven en `routers/`): ata el motor, los pools httpx y los
clientes remotos al `app.state`, y ese cableado es lo que las otras pruebas
sustituyen a mano. Si el cableado se rompe, ninguna de ellas lo nota, asi que
aqui se fija con dobles:

- `_catalogo/_identidad/_comercio` devuelven el cliente inyectado en
  `app.state` y, si no hay ninguno, construyen el real (que lee su URL del
  entorno);
- `_usuario_de_la_peticion` solo le pregunta a Identidad cuando llega un
  `Authorization: Bearer ...` (una cabecera de otro esquema o sin token es
  anonimo y no cuesta una llamada);
- `_arrancar` abre UN motor, tres pools (bulkhead por destino) y los clientes
  que los usan, y avisa a gritos si `TUKIT_AUTOPUBLICAR` salta la revision
  humana; `_apagar` cierra todo, tambien con un arranque a medias;
- el puerto por omision es el del contrato (8013) y `main` lo pasa a uvicorn.

Nada abre un socket: el motor es el SQLite de la fixture, los pools son
dobles que anotan `aclose`, `uvicorn.run` se sustituye y el `FastAPI` que se
arranca es uno nuevo (no se ensucia el `app.state` global del resto de pruebas).
"""

from __future__ import annotations

from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from starlette.requests import Request
from tukit_inteligencia import api
from tukit_inteligencia.remoto import (
    ESPERA_SEGUNDOS,
    ClienteCatalogo,
    ClienteComercio,
    ClienteIdentidad,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

USUARIO = "22222222-2222-5222-8222-222222222222"


def _peticion(autorizacion: str | None) -> Request:
    cabeceras = [(b"authorization", autorizacion.encode())] if autorizacion is not None else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": cabeceras})


class IdentidadDoble:
    """Resuelve tokens y anota a quien se le pregunto."""

    def __init__(self, usuario_por_token: dict[str, str] | None = None) -> None:
        self.usuario_por_token = usuario_por_token or {}
        self.preguntados: list[str] = []

    async def usuario_del_token(self, token: str) -> str | None:
        self.preguntados.append(token)
        return self.usuario_por_token.get(token)


@pytest.fixture()
def sin_inyecciones(monkeypatch):
    """Un `app.state` sin clientes inyectados, restaurado al terminar la prueba."""
    for nombre in ("catalogo", "identidad", "comercio"):
        monkeypatch.delattr(api.app.state, nombre, raising=False)


class TestClientesPorOmision:
    @pytest.mark.parametrize(
        ("funcion", "clase"),
        [("_catalogo", ClienteCatalogo), ("_identidad", ClienteIdentidad), ("_comercio", ClienteComercio)],
    )
    def test_sin_inyeccion_construye_el_cliente_real(self, sin_inyecciones, funcion, clase):
        """Sin doble en `app.state` el cliente real se arma al vuelo (su URL sale del entorno)."""
        cliente = getattr(api, funcion)()

        assert type(cliente) is clase

    @pytest.mark.parametrize(
        ("funcion", "atributo"),
        [("_catalogo", "catalogo"), ("_identidad", "identidad"), ("_comercio", "comercio")],
    )
    def test_el_cliente_inyectado_en_el_estado_gana(self, monkeypatch, funcion, atributo):
        doble = object()
        monkeypatch.setattr(api.app.state, atributo, doble, raising=False)

        assert getattr(api, funcion)() is doble

    def test_el_cliente_real_pide_a_la_url_del_entorno(self, sin_inyecciones, monkeypatch):
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://identidad.interna:9001/")

        assert api._identidad()._base() == "http://identidad.interna:9001"


class TestUsuarioDeLaPeticion:
    async def test_un_bearer_valido_resuelve_el_usuario_por_identidad(self, monkeypatch):
        identidad = IdentidadDoble({"tok-1": USUARIO})
        monkeypatch.setattr(api.app.state, "identidad", identidad, raising=False)

        usuario = await api._usuario_de_la_peticion(_peticion("Bearer tok-1"))

        assert usuario == USUARIO
        assert identidad.preguntados == ["tok-1"]  # el token viaja sin el prefijo "Bearer "

    async def test_un_token_que_identidad_no_conoce_es_anonimo(self, monkeypatch):
        identidad = IdentidadDoble()
        monkeypatch.setattr(api.app.state, "identidad", identidad, raising=False)

        assert await api._usuario_de_la_peticion(_peticion("Bearer caducado")) is None
        assert identidad.preguntados == ["caducado"]

    @pytest.mark.parametrize(
        "autorizacion",
        [None, "", "Bearer ", "Basic dXN1YXJpbzpjbGF2ZQ==", "tok-1"],
        ids=["sin_cabecera", "vacia", "bearer_sin_token", "otro_esquema", "token_pelado"],
    )
    async def test_sin_bearer_utilizable_es_anonimo_y_no_cuesta_una_llamada(self, monkeypatch, autorizacion):
        """El flujo anonimo cae de vuelta al contacto: no se le pregunta a Identidad por nada."""
        identidad = IdentidadDoble({"tok-1": USUARIO})
        monkeypatch.setattr(api.app.state, "identidad", identidad, raising=False)

        assert await api._usuario_de_la_peticion(_peticion(autorizacion)) is None
        assert identidad.preguntados == []


class Pool:
    """Doble de un pool httpx: anota el cierre."""

    def __init__(self, espera: float, **kw: Any) -> None:
        self.espera = espera
        self.kw = kw
        self.cerrado = False

    async def aclose(self) -> None:
        self.cerrado = True


class MotorPrestado:
    """El motor SQLite de la fixture, con el cierre anotado en vez de ejecutado."""

    def __init__(self, motor: Any) -> None:
        self._motor = motor
        self.cierres = 0

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._motor, nombre)

    async def cerrar(self) -> None:
        self.cierres += 1


@pytest.fixture()
def cableado(motor, monkeypatch):
    """Sustituye motor, pools e instrumentacion de `_arrancar` por dobles que anotan lo que reciben."""
    visto: dict[str, Any] = {"servicios": [], "pools": [], "instrumentados": []}
    prestado = MotorPrestado(motor)

    def _crear_motor(servicio: str, **_kw: Any) -> MotorPrestado:
        visto["servicios"].append(servicio)
        return prestado

    def _crear_pool(*, espera: float, **kw: Any) -> Pool:
        pool = Pool(espera, **kw)
        visto["pools"].append(pool)
        return pool

    monkeypatch.setattr(api, "crear_motor", _crear_motor)
    monkeypatch.setattr(api, "crear_pool", _crear_pool)
    monkeypatch.setattr(api, "instrumentar_motor", visto["instrumentados"].append)
    monkeypatch.delenv("TUKIT_AUTOPUBLICAR", raising=False)
    visto["motor"] = prestado
    return visto


class TestArranque:
    async def test_abre_un_motor_tres_pools_y_los_clientes_que_los_usan(self, cableado, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://catalogo.interno:9000")
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://identidad.interna:9001")
        aplicacion = FastAPI()

        await api._arrancar(aplicacion)

        estado = aplicacion.state
        assert cableado["servicios"] == ["inteligencia"]
        assert estado.motor is cableado["motor"]
        # La telemetria se instrumenta sobre el engine del motor recien creado.
        assert cableado["instrumentados"] == [cableado["motor"].engine]
        # Un pool por destino (bulkhead), con la espera generosa del contrato.
        assert len(cableado["pools"]) == 3
        assert {p.espera for p in cableado["pools"]} == {ESPERA_SEGUNDOS}
        pools = (estado.pool_catalogo, estado.pool_identidad, estado.pool_comercio)
        assert len({id(p) for p in pools}) == 3
        # Cada cliente usa SU pool, no uno compartido.
        assert (
            isinstance(estado.catalogo, ClienteCatalogo) and estado.catalogo.cliente is estado.pool_catalogo
        )
        assert (
            isinstance(estado.identidad, ClienteIdentidad)
            and estado.identidad.cliente is estado.pool_identidad
        )
        assert (
            isinstance(estado.comercio, ClienteComercio) and estado.comercio.cliente is estado.pool_comercio
        )

    async def test_anuncia_a_que_catalogo_e_identidad_apunta(self, cableado, monkeypatch, capsys):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://catalogo.interno:9000")
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://identidad.interna:9001")

        await api._arrancar(FastAPI())

        assert (
            "[inteligencia] catalogo en http://catalogo.interno:9000, identidad en http://identidad.interna:9001"
            in capsys.readouterr().out
        )

    async def test_sin_autopublicar_no_hay_aviso_de_atajo(self, cableado, capsys):
        await api._arrancar(FastAPI())

        assert "AUTOPUBLICAR" not in capsys.readouterr().out

    @pytest.mark.parametrize("valor", ["1", "true", "si", " TRUE "])
    async def test_con_autopublicar_lo_anuncia_a_gritos(self, cableado, monkeypatch, capsys, valor):
        """Una valvula silenciosa que salta la revision humana acaba puesta en produccion."""
        monkeypatch.setenv("TUKIT_AUTOPUBLICAR", valor)

        await api._arrancar(FastAPI())

        salida = capsys.readouterr().out
        assert "TUKIT_AUTOPUBLICAR esta activo" in salida
        assert "SIN revision humana" in salida


class TestApagado:
    async def test_cierra_los_tres_pools_y_el_motor(self, cableado):
        aplicacion = FastAPI()
        await api._arrancar(aplicacion)

        await api._apagar(aplicacion)

        assert all(pool.cerrado for pool in cableado["pools"])
        assert len(cableado["pools"]) == 3
        assert cableado["motor"].cierres == 1

    async def test_tolera_un_arranque_a_medias_sin_pools(self, motor):
        """Si `_arrancar` murio antes de crear los pools, apagar igual cierra el motor."""
        aplicacion = FastAPI()
        aplicacion.state.motor = MotorPrestado(motor)

        await api._apagar(aplicacion)

        assert aplicacion.state.motor.cierres == 1

    async def test_cierra_solo_los_pools_que_existen(self, motor):
        aplicacion = FastAPI()
        aplicacion.state.motor = MotorPrestado(motor)
        aplicacion.state.pool_identidad = Pool(1.0)

        await api._apagar(aplicacion)

        assert aplicacion.state.pool_identidad.cerrado
        assert aplicacion.state.motor.cierres == 1


class TestPuntoDeEntrada:
    def test_el_puerto_por_omision_es_el_del_contrato(self):
        """CONTRATO_API: identidad 8011, catalogo 8012, inteligencia 8013."""
        assert api.PUERTO_POR_OMISION == 8013

    def test_main_levanta_la_app_en_localhost_con_el_puerto_por_omision(self, monkeypatch):
        llamadas: list[tuple[Any, dict[str, Any]]] = []
        monkeypatch.setattr(uvicorn, "run", lambda aplicacion, **kw: llamadas.append((aplicacion, kw)))

        assert api.main([]) == 0

        assert llamadas == [(api.app, {"host": "127.0.0.1", "port": 8013, "log_level": "info"})]

    def test_main_respeta_host_y_puerto_pedidos(self, monkeypatch):
        llamadas: list[tuple[Any, dict[str, Any]]] = []
        monkeypatch.setattr(uvicorn, "run", lambda aplicacion, **kw: llamadas.append((aplicacion, kw)))

        api.main(["--puerto", "9100", "--host", "10.0.0.7"])

        assert llamadas[0][1]["port"] == 9100
        assert llamadas[0][1]["host"] == "10.0.0.7"

    def test_un_puerto_que_no_es_entero_sale_con_codigo_2(self, monkeypatch, capsys):
        monkeypatch.setattr(uvicorn, "run", lambda *_a, **_k: pytest.fail("no debe arrancar"))

        with pytest.raises(SystemExit) as salida:
            api.main(["--puerto", "ocho-mil"])

        assert salida.value.code == 2
        assert "--puerto" in capsys.readouterr().err


class TestPuertosDePercepcion:
    def test_el_envoltorio_usa_los_puertos_del_modulo_y_se_pueden_sustituir(self, monkeypatch):
        """`_RENDERIZAR` y `_LEER` se leen en cada llamada: es el punto de inyeccion del onboarding."""
        from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida

        leidas: list[tuple[bytes, int]] = []

        def _leer(png: bytes, numero: int) -> PaginaLeida:
            leidas.append((png, numero))
            return PaginaLeida(grados=["Cuarto"], items=[ItemExtraido(descripcion="2 lapices", cantidad=2)])

        monkeypatch.setattr(api, "_RENDERIZAR", lambda contenido: [contenido, contenido])
        monkeypatch.setattr(api, "_LEER", _leer)

        percepcion = api._percibir_onboarding(b"imagen-ficticia")

        assert percepcion.aceptada is True
        assert percepcion.paginas == 2
        assert percepcion.grados == ("Cuarto",)
        assert leidas == [(b"imagen-ficticia", 1), (b"imagen-ficticia", 2)]
