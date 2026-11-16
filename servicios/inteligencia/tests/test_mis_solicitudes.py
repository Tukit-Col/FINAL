"""El panel "Mis solicitudes" del acudiente: listas subidas + trabajos, unidas.

Dos capas se prueban aquí. La FUNCIÓN de dominio (`trabajos.mis_solicitudes`)
sobre el SQLite del conftest y un doble de catálogo en memoria: la unión de una
lista aprobada con su trabajo en una sola fila, la lista sin aprobar como
`recibida`, el trabajo sin lista como `trabajo`, el orden por fecha (que ejercita
la normalización naive/aware) y la degradación parcial cuando el catálogo cae. Y
la PUERTA HTTP (`GET /v1/mis-solicitudes`): 401 sin token o token inválido, 503
si identidad no responde (falla cerrada), y que el `usuario_id` que llega al
catálogo es SIEMPRE el de la sesión, nunca uno del navegador.

Con `ASGITransport`, sin uvicorn ni Postgres: se inyectan el motor, el doble de
identidad y el de catálogo por `app.state`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from _ayudas_inteligencia import IdentidadFalsa, lista_del_catalogo, sembrar_trabajo
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import Base, EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido

TRABAJO = Base.metadata.tables["trabajo_pipeline"]

COLEGIO = "22222222-2222-5222-8222-222222222222"
# Dos acudientes reales (UUID válidos): el token resuelve a uno de ellos.
PADRE = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
OTRO_PADRE = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")


@dataclass
class CatalogoListasFalso:
    """Doble del puerto hacia catálogo: `listas_por_contacto`, registrando el
    contacto pedido. `caida=True` lanza `RemotoCaido` (degradación parcial)."""

    por_contacto: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    caida: bool = False
    contactos_pedidos: list[str] = field(default_factory=list)

    async def listas_por_contacto(self, contacto_referencia: str) -> list[dict[str, Any]]:
        self.contactos_pedidos.append(contacto_referencia)
        if self.caida:
            raise RemotoCaido("catalogo", "simulada")
        return list(self.por_contacto.get(contacto_referencia, ()))


# --------------------------------------------------------------------------
# La función de dominio
# --------------------------------------------------------------------------


async def test_lista_aprobada_y_su_trabajo_se_unen(motor):
    # Una lista aprobada y el trabajo que engendró (mismo version_id) salen como
    # UNA sola solicitud `aprobada`, no como dos filas.
    version_id = str(uuid.uuid4())
    trabajo_id = await sembrar_trabajo(
        motor,
        usuario_id=PADRE,
        origen="lista_verificada",
        estado=EstadoTrabajo.PUBLICADO.value,
        hijos=[{"colegio_id": COLEGIO, "grado": "Quinto", "version_id": version_id}],
    )
    catalogo = CatalogoListasFalso(
        por_contacto={
            str(PADRE): [
                lista_del_catalogo(
                    version_id=version_id, revisada=True, creada_en="2026-01-01T10:00:00+00:00"
                )
            ]
        }
    )

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert resultado["listas_disponibles"] is True
    assert len(resultado["solicitudes"]) == 1
    solicitud = resultado["solicitudes"][0]
    assert solicitud["tipo"] == "aprobada"
    assert solicitud["trabajo_id"] == str(trabajo_id)
    assert solicitud["colegio_id"] == COLEGIO


async def test_lista_sin_aprobar_es_recibida(motor):
    catalogo = CatalogoListasFalso(
        por_contacto={
            str(PADRE): [
                lista_del_catalogo(
                    version_id=str(uuid.uuid4()),
                    revisada=False,
                    colegio_nombre="Colegio Nuevo",
                    creada_en="2026-01-01T10:00:00+00:00",
                )
            ]
        }
    )

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert len(resultado["solicitudes"]) == 1
    solicitud = resultado["solicitudes"][0]
    assert solicitud["tipo"] == "recibida"
    assert solicitud["colegio_nombre"] == "Colegio Nuevo"
    assert "trabajo_id" not in solicitud


async def test_trabajo_sin_lista_es_trabajo(motor):
    trabajo_id = await sembrar_trabajo(
        motor,
        usuario_id=PADRE,
        estado=EstadoTrabajo.ESPERA_REVISION.value,
        hijos=[{"colegio_id": COLEGIO, "grado": "Tercero"}],
    )
    catalogo = CatalogoListasFalso(por_contacto={})

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert len(resultado["solicitudes"]) == 1
    solicitud = resultado["solicitudes"][0]
    assert solicitud["tipo"] == "trabajo"
    assert solicitud["trabajo_id"] == str(trabajo_id)
    assert solicitud["estado"] == EstadoTrabajo.ESPERA_REVISION.value
    assert solicitud["grado"] == "Tercero"


async def test_solo_devuelve_datos_del_portador(motor):
    # Un trabajo de OTRO padre no debe aparecer en las solicitudes del portador.
    await sembrar_trabajo(motor, usuario_id=OTRO_PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    mio = await sembrar_trabajo(motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    catalogo = CatalogoListasFalso(por_contacto={})

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    ids = {s.get("trabajo_id") for s in resultado["solicitudes"]}
    assert ids == {str(mio)}
    # Y el catálogo se consultó con el usuario_id del portador, jamás con otro.
    assert catalogo.contactos_pedidos == [str(PADRE)]


async def test_orden_mas_reciente_primero(motor):
    # Un trabajo naive (SQLite) y una lista con fecha ISO aware: ordenar mezclando
    # ambos no debe lanzar TypeError, y la más reciente va primero.
    viejo = datetime(2026, 1, 1, 8, 0, 0)  # naive, como vuelve de SQLite
    await sembrar_trabajo(
        motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Primero"}], creado_en=viejo
    )
    reciente = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    catalogo = CatalogoListasFalso(
        por_contacto={
            str(PADRE): [lista_del_catalogo(version_id=str(uuid.uuid4()), revisada=False, creada_en=reciente)]
        }
    )

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    tipos = [s["tipo"] for s in resultado["solicitudes"]]
    assert tipos == ["recibida", "trabajo"]  # la lista reciente antes que el trabajo viejo


async def test_catalogo_caido_devuelve_trabajos_y_marca_listas_no_disponibles(motor):
    trabajo_id = await sembrar_trabajo(
        motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}]
    )
    catalogo = CatalogoListasFalso(caida=True)

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert resultado["listas_disponibles"] is False
    assert [s["trabajo_id"] for s in resultado["solicitudes"]] == [str(trabajo_id)]


# --------------------------------------------------------------------------
# La puerta HTTP
# --------------------------------------------------------------------------

RUTA = "/v1/mis-solicitudes"


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(usuario_por_token={"tok-padre": PADRE})
    app.state.catalogo = CatalogoListasFalso(por_contacto={})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    for attr in ("identidad", "catalogo"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer no-existe"}],
    ids=["sin_token", "token_invalido"],
)
async def test_sin_sesion_valida_es_401(cliente, cabeceras):
    respuesta = await cliente.get(RUTA, headers=cabeceras)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_identidad_caida_falla_cerrada_503(motor):
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(caida=True)
    app.state.catalogo = CatalogoListasFalso(por_contacto={})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.get(RUTA, headers={"Authorization": "Bearer tok-padre"})
        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "identidad_no_disponible"
    finally:
        for attr in ("identidad", "catalogo"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)


async def test_portador_usa_el_usuario_de_la_sesion(motor):
    # Un trabajo del portador y otro de un tercero: la puerta solo devuelve el del
    # portador, y consulta al catálogo con SU usuario_id (el de la sesión).
    await sembrar_trabajo(motor, usuario_id=OTRO_PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    mio = await sembrar_trabajo(motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(usuario_por_token={"tok-padre": PADRE})
    catalogo = CatalogoListasFalso(por_contacto={})
    app.state.catalogo = catalogo
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.get(RUTA, headers={"Authorization": "Bearer tok-padre"})
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert [s["trabajo_id"] for s in cuerpo["solicitudes"]] == [str(mio)]
        assert catalogo.contactos_pedidos == [str(PADRE)]
    finally:
        for attr in ("identidad", "catalogo"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)
