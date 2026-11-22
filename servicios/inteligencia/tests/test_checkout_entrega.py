from __future__ import annotations

import uuid

import httpx
import pytest
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app

TRABAJO = uuid.UUID("44444444-4444-5444-8444-444444444444")
ENTREGA_MINIMA = {"destinatario": "Ana Perez", "direccion": "Calle 72 # 10-34", "ciudad": "Bogotá"}


@pytest.fixture()
async def cliente_y_entregas(monkeypatch):
    entregas: list[dict] = []

    async def _ordenar(_motor, _trabajo_id, *, entrega, **_resto):
        entregas.append(entrega)
        return {"pedido_id": "ped-1", "url_redireccion": "https://pasarela/xy"}

    monkeypatch.setattr(trabajos, "ordenar", _ordenar)
    monkeypatch.setattr(app.state, "motor", None, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, entregas


def _cuerpo(entrega: dict) -> dict:
    return {"perfil": "Ahorrador", "correo": "ana@ejemplo.com", "entrega": entrega}


async def test_una_entrega_sin_localidad_ni_indicaciones_viaja_tal_cual(cliente_y_entregas):
    cliente, entregas = cliente_y_entregas
    respuesta = await cliente.post(f"/v1/trabajos/{TRABAJO}/ordenar", json=_cuerpo(ENTREGA_MINIMA))
    assert respuesta.status_code == 201
    assert entregas == [ENTREGA_MINIMA]


async def test_localidad_e_indicaciones_llegan_a_comercio(cliente_y_entregas):
    cliente, entregas = cliente_y_entregas
    completa = {
        **ENTREGA_MINIMA,
        "departamento": "Bogotá, D.C.",
        "indicaciones": "Apto 502, torre 2",
        "localidad": "Chapinero",
    }
    respuesta = await cliente.post(f"/v1/trabajos/{TRABAJO}/ordenar", json=_cuerpo(completa))
    assert respuesta.status_code == 201
    assert entregas == [completa]


async def test_el_pin_de_openstreetmap_llega_a_comercio(cliente_y_entregas):
    cliente, entregas = cliente_y_entregas
    con_pin = {**ENTREGA_MINIMA, "latitud": 4.651818, "longitud": -74.051003}
    respuesta = await cliente.post(f"/v1/trabajos/{TRABAJO}/ordenar", json=_cuerpo(con_pin))
    assert respuesta.status_code == 201
    assert entregas == [con_pin]


@pytest.mark.parametrize(
    "coordenadas",
    [{"latitud": 4.65}, {"latitud": 40.4, "longitud": -3.7}],
)
async def test_un_pin_incompleto_o_fuera_de_colombia_no_llega_a_comercio(cliente_y_entregas, coordenadas):
    cliente, entregas = cliente_y_entregas
    entrega = {**ENTREGA_MINIMA, **coordenadas}
    respuesta = await cliente.post(f"/v1/trabajos/{TRABAJO}/ordenar", json=_cuerpo(entrega))
    assert respuesta.status_code in (400, 422)
    assert entregas == []


async def test_un_campo_desconocido_no_cruza(cliente_y_entregas):
    cliente, entregas = cliente_y_entregas
    respuesta = await cliente.post(
        f"/v1/trabajos/{TRABAJO}/ordenar", json=_cuerpo({**ENTREGA_MINIMA, "lat": 4.65, "lng": -74.05})
    )
    assert respuesta.status_code == 201
    assert entregas == [ENTREGA_MINIMA]


@pytest.mark.parametrize(("campo", "largo"), [("localidad", 65), ("indicaciones", 513)])
async def test_un_campo_demasiado_largo_no_llega_a_comercio(cliente_y_entregas, campo, largo):
    cliente, entregas = cliente_y_entregas
    respuesta = await cliente.post(
        f"/v1/trabajos/{TRABAJO}/ordenar", json=_cuerpo({**ENTREGA_MINIMA, campo: "x" * largo})
    )
    assert respuesta.status_code in (400, 422)
    assert entregas == []
