from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from sqlalchemy import insert
from tukit_inteligencia.api import app
from tukit_inteligencia.metricas import resumen_pedidos_de_colegio
from tukit_inteligencia.modelos import Base, EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido

TRABAJO = Base.metadata.tables["trabajo_pipeline"]

COLEGIO = "22222222-2222-5222-8222-222222222222"
OTRO_COLEGIO = "33333333-3333-5333-8333-333333333333"


@dataclass
class ComercioFalso:

    pagados: list[dict[str, Any]] = field(default_factory=list)

    async def pedidos_pagados(self) -> list[dict[str, Any]]:
        return self.pagados


async def _sembrar_trabajo(
    motor,
    *,
    estado: str = EstadoTrabajo.PUBLICADO.value,
    hijos: list[dict[str, Any]],
) -> uuid.UUID:
    trabajo_id = uuid.uuid4()
    error = "prueba" if estado == EstadoTrabajo.FALLIDO.value else None
    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            insert(TRABAJO).values(
                id=trabajo_id, estado=estado, origen="colegio_grado", hijos=hijos, error=error
            )
        )
    return trabajo_id


def _pagado(trabajo_id: uuid.UUID, usuario_id: str) -> dict[str, Any]:
    return {"trabajo_id": str(trabajo_id), "usuario_id": usuario_id, "estado": "pagado"}


async def test_cuenta_por_colegio_ignorando_otros(motor):
    t = await _sembrar_trabajo(
        motor,
        hijos=[
            {"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"},
            {"referencia": "h2", "colegio_id": OTRO_COLEGIO, "grado": "Quinto"},
        ],
    )
    comercio = ComercioFalso([_pagado(t, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_padres"] == 1
    assert resumen["total_ninos"] == 1
    assert resumen["por_padre"] == [{"usuario_id": "padre-1", "ninos": 1}]


async def test_por_grado_y_por_padre(motor):
    t = await _sembrar_trabajo(
        motor,
        hijos=[
            {"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"},
            {"referencia": "h2", "colegio_id": COLEGIO, "grado": "Quinto"},
        ],
    )
    comercio = ComercioFalso([_pagado(t, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_ninos"] == 2
    quinto = next(g for g in resumen["por_grado"] if g["grado"] == "Quinto")
    assert quinto["padres"] == 1
    assert quinto["ninos"] == 2
    assert quinto["por_padre"] == [{"usuario_id": "padre-1", "ninos": 2}]


async def test_solo_pedidos_pagados_entran(motor):
    pagado = await _sembrar_trabajo(
        motor, hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"}]
    )
    await _sembrar_trabajo(motor, hijos=[{"referencia": "h9", "colegio_id": COLEGIO, "grado": "Cuarto"}])
    comercio = ComercioFalso([_pagado(pagado, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_padres"] == 1
    assert resumen["total_ninos"] == 1
    assert [g["grado"] for g in resumen["por_grado"]] == ["Quinto"]


async def test_dedupe_por_trabajo(motor):
    t = await _sembrar_trabajo(motor, hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"}])
    comercio = ComercioFalso([_pagado(t, "padre-1"), _pagado(t, "padre-1")])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["total_ninos"] == 1


async def test_estados_de_trabajos_del_colegio(motor):
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.ESPERA_REVISION.value,
        hijos=[{"referencia": "h1", "colegio_id": COLEGIO, "grado": "Quinto"}],
    )
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.PUBLICADO.value,
        hijos=[{"referencia": "h2", "colegio_id": COLEGIO, "grado": "Cuarto"}],
    )
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.FALLIDO.value,
        hijos=[{"referencia": "h3", "colegio_id": COLEGIO, "grado": "Tercero"}],
    )
    await _sembrar_trabajo(
        motor,
        estado=EstadoTrabajo.PUBLICADO.value,
        hijos=[{"referencia": "h4", "colegio_id": OTRO_COLEGIO, "grado": "Quinto"}],
    )
    comercio = ComercioFalso([])

    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, comercio)
    assert resumen["estados_trabajos"] == {
        "espera_revision": 1,
        "publicado": 1,
        "fallido": 1,
    }


async def test_colegio_sin_pedidos_da_vacio(motor):
    resumen = await resumen_pedidos_de_colegio(motor, COLEGIO, ComercioFalso([]))
    assert resumen == {
        "colegio_id": COLEGIO,
        "total_padres": 0,
        "total_ninos": 0,
        "por_padre": [],
        "por_grado": [],
        "estados_trabajos": {"espera_revision": 0, "publicado": 0, "fallido": 0},
    }


COLEGIO = "22222222-2222-5222-8222-222222222222"


@dataclass
class IdentidadFalsa:

    roles_por_token: dict[str, list[str]] = field(default_factory=dict)
    caida: bool = False

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if self.caida:
            raise RemotoCaido("identidad", "simulada")
        if token not in self.roles_por_token:
            return None
        return {
            "usuario_id": f"u-{token}",
            "correo": f"{token}@tukit.co",
            "nombre": token,
            "roles": [{"rol": r, "ambito": None} for r in self.roles_por_token[token]],
            "version_permisos": 1,
        }


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    app.state.comercio = ComercioFalso([])
    app.state.identidad = IdentidadFalsa(
        roles_por_token={
            "tok-operador": ["operador"],
            "tok-admin": ["admin"],
            "tok-acudiente": ["acudiente"],
        }
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    for attr in ("identidad", "comercio"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


RUTA = f"/v1/metricas/colegios/{COLEGIO}/pedidos"


@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer no-existe"}],
    ids=["sin_token", "token_invalido"],
)
async def test_sin_sesion_valida_es_401(cliente, cabeceras):
    respuesta = await cliente.get(RUTA, headers=cabeceras)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_rol_acudiente_es_403(cliente):
    respuesta = await cliente.get(RUTA, headers={"Authorization": "Bearer tok-acudiente"})
    assert respuesta.status_code == 403
    assert respuesta.json()["error"] == "acceso_denegado"


@pytest.mark.parametrize("token", ["tok-operador", "tok-admin"], ids=["operador", "admin"])
async def test_solo_staff_ve_el_resumen(cliente, token):
    respuesta = await cliente.get(RUTA, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["colegio_id"] == COLEGIO
    assert set(cuerpo) >= {"total_padres", "total_ninos", "por_padre", "por_grado", "estados_trabajos"}


async def test_identidad_caida_falla_cerrada_503(motor):
    app.state.motor = motor
    app.state.comercio = ComercioFalso([])
    app.state.identidad = IdentidadFalsa(caida=True)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.get(RUTA, headers={"Authorization": "Bearer tok-operador"})
        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "identidad_no_disponible"
    finally:
        for attr in ("identidad", "comercio"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)
