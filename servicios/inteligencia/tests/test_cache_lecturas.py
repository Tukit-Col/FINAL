from __future__ import annotations

import json

import httpx
import pytest
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria
from tukit_inteligencia import cache_lecturas
from tukit_inteligencia.api import app
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida, Percepcion, percibir

COLEGIO = "11111111-1111-5111-8111-111111111111"
CORREO = "mama.prueba@ejemplo.com"
CELULAR = "+573009998877"


def _pagina(grados: list[str] | None = None, *, completa: bool = True) -> PaginaLeida:
    return PaginaLeida(
        grados=grados if grados is not None else ["Cuarto"],
        completa=completa,
        items=[
            ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.91),
            ItemExtraido(descripcion="1 caja de colores", cantidad=None, confianza=0.8),
        ],
    )


class Lector:
    def __init__(self) -> None:
        self.lecturas: list[int] = []
        self.pagina = _pagina()

    def __call__(self, _png: bytes, numero: int) -> PaginaLeida:
        self.lecturas.append(numero)
        return self.pagina


@pytest.fixture()
def lector() -> Lector:
    lector = Lector()
    app.state.renderizar = lambda _contenido: [b"p1"]
    app.state.leer = lector
    return lector


@pytest.fixture()
def leer_guardada(lector):

    async def leer(contenido: bytes) -> Percepcion:
        return await cache_lecturas.percibir_guardada(contenido, lambda archivo: _sin_cache(archivo, lector))

    return leer


@pytest.fixture()
def redis() -> RedisEnMemoria:
    motor = RedisEnMemoria()
    usar_cliente(cliente_en_memoria(motor))
    return motor


def _sin_cache(contenido: bytes, lector: Lector) -> Percepcion:
    return percibir(contenido, renderizar=lambda _c: [b"p1"], leer=lector)


async def test_el_mismo_archivo_dos_veces_se_lee_una(leer_guardada, lector, redis):
    primera = await leer_guardada(b"%PDF-lista-cuarto")
    segunda = await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1]
    assert segunda == primera
    assert segunda.aceptada


async def test_otro_archivo_se_lee_aparte(leer_guardada, lector, redis):
    await leer_guardada(b"%PDF-lista-cuarto")
    await leer_guardada(b"%PDF-lista-quinto")

    assert lector.lecturas == [1, 1]


async def test_un_rechazo_no_se_guarda(leer_guardada, lector, redis):
    lector.pagina = _pagina(["Cuarto", "Quinto"])

    for _ in range(2):
        percepcion = await leer_guardada(b"%PDF-dos-grados")
        assert percepcion.error == "lista_de_varios_grados"

    assert lector.lecturas == [1, 1]
    assert redis.operaciones("guardar") == []


async def test_una_pagina_incompleta_tampoco_se_guarda(leer_guardada, lector, redis):
    lector.pagina = _pagina(completa=False)

    await leer_guardada(b"%PDF-incompleta")
    await leer_guardada(b"%PDF-incompleta")

    assert lector.lecturas == [1, 1]
    assert redis.operaciones("guardar") == []


async def test_un_archivo_vacio_no_pregunta_a_redis(leer_guardada, lector, redis):
    percepcion = await leer_guardada(b"")

    assert percepcion.error == "archivo_vacio"
    assert redis.llamadas == []


async def test_otro_modelo_vuelve_a_leer(leer_guardada, lector, redis, monkeypatch):
    await leer_guardada(b"%PDF-lista-cuarto")
    monkeypatch.setenv("GEMINI_MODELO", "gemini-otro-modelo")

    await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1, 1]


async def test_un_cambio_en_el_codigo_que_lee_vuelve_a_leer(leer_guardada, lector, redis, monkeypatch):
    await leer_guardada(b"%PDF-lista-cuarto")
    monkeypatch.setattr(cache_lecturas, "_huella_del_codigo", lambda: "otro-prompt-u-otro-render")

    await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1, 1]


def test_la_version_cambia_con_cada_pieza(monkeypatch):
    base = cache_lecturas.version()
    monkeypatch.setenv("GEMINI_MODELO", "gemini-otro-modelo")
    otro_modelo = cache_lecturas.version()
    monkeypatch.delenv("GEMINI_MODELO")
    monkeypatch.setattr(cache_lecturas, "_huella_del_codigo", lambda: "otra-huella")
    otro_codigo = cache_lecturas.version()

    assert len({base, otro_modelo, otro_codigo}) == 3
    assert len(base) == 16


def test_la_huella_cubre_render_prompt_y_reglas():
    assert cache_lecturas._PIEZAS == ("paginas.py", "gemini.py", "percepcion.py")
    cache_lecturas._huella_del_codigo.cache_clear()
    assert len(cache_lecturas._huella_del_codigo()) == 64


async def test_con_redis_caido_lee_como_hoy_y_responde_igual(leer_guardada, lector, redis):
    redis.caido = True

    primera = await leer_guardada(b"%PDF-lista-cuarto")
    segunda = await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1, 1]
    assert primera == segunda == _sin_cache(b"%PDF-lista-cuarto", Lector())


async def test_con_redis_lento_lee_como_hoy_y_responde_igual(leer_guardada, lector, redis):
    redis.demora = 1.0

    percepcion = await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1]
    assert percepcion == _sin_cache(b"%PDF-lista-cuarto", Lector())


async def test_sin_redis_lee_cada_vez_como_hoy(leer_guardada, lector):
    await leer_guardada(b"%PDF-lista-cuarto")
    await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1, 1]


async def test_la_duracion_es_de_treinta_dias_y_se_configura(leer_guardada, lector, redis, monkeypatch):
    await leer_guardada(b"%PDF-a")
    monkeypatch.setenv("TUKIT_CACHE_PERCEPCION_SEGUNDOS", "3600")
    await leer_guardada(b"%PDF-b")

    assert redis.vence_en("tukit:" + cache_lecturas.clave(b"%PDF-a")) == pytest.approx(30 * 24 * 3600, abs=5)
    assert redis.vence_en("tukit:" + cache_lecturas.clave(b"%PDF-b")) == pytest.approx(3600, abs=5)


async def test_con_duracion_cero_no_hay_cache(leer_guardada, lector, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_CACHE_PERCEPCION_SEGUNDOS", "0")

    await leer_guardada(b"%PDF-lista-cuarto")
    await leer_guardada(b"%PDF-lista-cuarto")

    assert lector.lecturas == [1, 1]
    assert redis.llamadas == []


async def test_un_valor_ilegible_cuenta_como_no_guardado(leer_guardada, lector, redis):
    await redis.guardar_varias({"tukit:" + cache_lecturas.clave(b"%PDF-roto"): b"{no es json"}, 60)

    percepcion = await leer_guardada(b"%PDF-roto")

    assert lector.lecturas == [1]
    assert percepcion.aceptada


class Catalogo:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    async def importar_lista(self, **campos) -> dict:
        self.llamadas.append(campos)
        n = len(self.llamadas)
        return {
            "version_id": f"ver-{n}",
            "tarea_id": f"tar-{n}",
            "items": len(campos["items"]),
            "revisada": False,
        }


class Identidad:
    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        return "usr-1"

    async def usuario_del_token(self, token: str) -> str | None:
        return None

    async def datos_directorio(self, dane: str) -> dict | None:
        return None

    async def sesion(self, token: str) -> dict | None:
        if token != "tok-operador":
            return None
        return {"usuario_id": "u-operador", "roles": [{"rol": "operador", "ambito": None}]}


@pytest.fixture()
async def http(motor, lector, redis):
    app.state.motor = motor
    app.state.catalogo = Catalogo()
    app.state.identidad = Identidad()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
        yield cliente


def _subida(pdf: bytes, referencia: str = "hijo-sofia-rojas") -> dict:
    hijos = [{"referencia": referencia, "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}]
    return {
        "data": {"hijos": json.dumps(hijos), "contacto": json.dumps({"correo": CORREO, "celular": CELULAR})},
        "files": [
            ("archivo", (f"{referencia}.pdf", pdf, "application/pdf")),
            ("referencia", (None, referencia)),
        ],
    }


async def test_dos_familias_suben_la_misma_lista_y_se_lee_una_vez(http, lector):
    pdf = b"%PDF-lista-del-colegio"

    primera = await http.post("/v1/listas/subir", **_subida(pdf, "hijo-1"))
    segunda = await http.post("/v1/listas/subir", **_subida(pdf, "hijo-2"))

    assert primera.status_code == segunda.status_code == 202
    assert lector.lecturas == [1]
    importadas = app.state.catalogo.llamadas
    assert [ll["items"] for ll in importadas[:1]] == [ll["items"] for ll in importadas[1:]]
    assert importadas[0]["percepcion_cruda"] == importadas[1]["percepcion_cruda"]


async def test_el_onboarding_reaprovecha_la_lectura_de_la_subida(http, lector):
    pdf = b"%PDF-lista-del-colegio"
    await http.post("/v1/listas/subir", **_subida(pdf))

    respuesta = await http.post(
        "/v1/admin/onboarding",
        data={"colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": "2026"},
        files={"archivo": ("lista.pdf", pdf, "application/pdf")},
        headers={"Authorization": "Bearer tok-operador"},
    )

    assert respuesta.status_code == 200
    assert lector.lecturas == [1]


async def test_lo_guardado_no_trae_datos_de_la_persona_ni_del_hijo(http, redis):
    respuesta = await http.post(
        "/v1/listas/subir",
        **_subida(b"%PDF-lista-del-colegio", "hijo-sofia-rojas"),
        headers={"Authorization": "Bearer tok-de-la-familia"},
    )
    assert respuesta.status_code == 202

    claves = redis.claves()
    assert len(claves) == 1
    valor = redis.guardado(claves[0])
    assert valor is not None
    assert set(json.loads(valor)) == {"grados", "paginas", "items"}
    for dato in (CORREO, CELULAR, "sofia", "hijo-sofia-rojas", "tok-de-la-familia", "usr-1", COLEGIO, "PDF"):
        assert dato.lower() not in claves[0].lower()
        assert dato.lower().encode() not in valor.lower()
